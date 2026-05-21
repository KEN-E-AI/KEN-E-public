#!/usr/bin/env bash
# E2E stack bootstrap for Playwright tests.
#
# Starts the Firestore emulator, Firebase Auth emulator, and the FastAPI backend
# with short cache TTL so the kill-switch scenario runs in <5s instead of 60s.
# Seeds two Firebase Auth emulator users and their Firestore user documents:
#   alice@ken-e.ai  (super-admin — Firestore users/alice-uid with roles:["super_admin"])
#   bob@example.com (external user — Firestore users/bob-uid with empty roles)
#
# Uses `firebase emulators:start` (bundles its own JRE) instead of gcloud so
# this script works on the playwright:jammy CI image which has no gcloud or JRE.
#
# Usage (sourced or executed):
#   bash deployment/ci/scripts/start_e2e_stack.sh
#
# Caller contract:
#   - Run from the repo root.
#   - After this script returns, the following are live:
#       Firestore emulator : 127.0.0.1:8090
#       Auth emulator      : 127.0.0.1:9099
#       FastAPI backend    : 127.0.0.1:8000  (GET /health → 200)
#   - Cleanup is handled by a trap on EXIT.

set -euo pipefail

FIRESTORE_HOST="${FIRESTORE_HOST:-127.0.0.1:8090}"
AUTH_HOST="${AUTH_HOST:-127.0.0.1:9099}"
API_PORT="${API_PORT:-8000}"

# ---------------------------------------------------------------------------
# Install uv if not present (needed on cloud-sdk emulator image).
# ---------------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# Install firebase-tools if not present.
# The playwright:jammy image includes Node.js; gcloud is not available there.
# firebase-tools bundles its own JRE — no external Java installation needed.
# ---------------------------------------------------------------------------
if ! command -v firebase &>/dev/null; then
  npm install -g firebase-tools
fi

# ---------------------------------------------------------------------------
# Cleanup trap — kill all background processes on exit.
# ---------------------------------------------------------------------------
cleanup() {
  echo "[e2e-stack] Cleaning up background processes..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Start Firebase emulators (Firestore + Auth) via the Firebase CLI.
#    The CLI bundles its own Java binary so no external JRE is required.
#    A minimal firebase.json is written to a temp dir to configure the ports
#    (Firestore default is 8080; we need 8090 to match the rest of the stack).
# ---------------------------------------------------------------------------
FIREBASE_TMP=$(mktemp -d)
cat > "${FIREBASE_TMP}/firebase.json" <<'EOF'
{
  "emulators": {
    "auth": {
      "host": "127.0.0.1",
      "port": 9099
    },
    "firestore": {
      "host": "127.0.0.1",
      "port": 8090
    },
    "ui": {
      "enabled": false
    }
  }
}
EOF

echo "[e2e-stack] Starting Firebase emulators (auth + firestore) on ${AUTH_HOST} and ${FIRESTORE_HOST}..."
(cd "${FIREBASE_TMP}" && firebase emulators:start --only auth,firestore --project test-project) &

# Wait for Firestore emulator.
# The root path "/" returns 200 "Ok"; the documents endpoint returns 404 before
# any documents exist, so we use "/" as the health-check URL.
for _ in $(seq 1 60); do
  curl -sf "http://${FIRESTORE_HOST}/" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://${FIRESTORE_HOST}/" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Firestore emulator failed to start"; exit 1; }
echo "[e2e-stack] Firestore emulator ready."

# Wait for Auth emulator.
for _ in $(seq 1 60); do
  curl -sf "http://${AUTH_HOST}/" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://${AUTH_HOST}/" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Firebase Auth emulator failed to start"; exit 1; }
echo "[e2e-stack] Firebase Auth emulator ready."

# ---------------------------------------------------------------------------
# 2. Seed test users in the Auth emulator.
#    Uses the Auth emulator REST API:
#    POST http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/projects/{PROJECT}/accounts
#    (project name is arbitrary in emulator context — use "test-project")
# ---------------------------------------------------------------------------
PROJECT="test-project"
AUTH_BASE="http://${AUTH_HOST}/identitytoolkit.googleapis.com/v1/projects/${PROJECT}"

echo "[e2e-stack] Seeding Alice (alice@ken-e.ai)..."
curl -sf -X POST "${AUTH_BASE}/accounts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer owner" \
  -d '{
    "localId": "alice-uid",
    "email": "alice@ken-e.ai",
    "password": "password123",
    "emailVerified": true
  }' >/dev/null

echo "[e2e-stack] Seeding Bob (bob@example.com)..."
curl -sf -X POST "${AUTH_BASE}/accounts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer owner" \
  -d '{
    "localId": "bob-uid",
    "email": "bob@example.com",
    "password": "password123",
    "emailVerified": true
  }' >/dev/null

echo "[e2e-stack] Auth emulator users seeded."

# ---------------------------------------------------------------------------
# 3. Seed Alice's super_admin role in Firestore.
#    is_super_admin derives from an explicit "super_admin" role in
#    users/{uid}.roles[] (api/src/kene_api/auth/models.py SUPER_ADMIN_ROLE).
#    If this doc is absent, the API auto-creates it with empty roles on first
#    sign-in, so we must write it before the first API call.
# ---------------------------------------------------------------------------
FIRESTORE_REST="http://${FIRESTORE_HOST}/v1/projects/${PROJECT}/databases/(default)/documents"
echo "[e2e-stack] Seeding Alice's super_admin role in Firestore..."
curl -sf -X PATCH "${FIRESTORE_REST}/users/alice-uid" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "uid":   {"stringValue": "alice-uid"},
      "email": {"stringValue": "alice@ken-e.ai"},
      "roles": {
        "arrayValue": {
          "values": [{"stringValue": "super_admin"}]
        }
      }
    }
  }' >/dev/null
echo "[e2e-stack] Alice super_admin role seeded."

# ---------------------------------------------------------------------------
# 4. Seed Bob's user document in Firestore.
#    The frontend's fetchUserDataAndSettings calls GET /api/v1/firestore/documents/users/{uid}
#    before the auth middleware's _get_or_create_user_document runs. Without this
#    doc, the API returns 404 and the frontend shows "Failed to sign in."
# ---------------------------------------------------------------------------
echo "[e2e-stack] Seeding Bob's user document in Firestore..."
curl -sf -X PATCH "${FIRESTORE_REST}/users/bob-uid" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "uid":   {"stringValue": "bob-uid"},
      "email": {"stringValue": "bob@example.com"},
      "profile": {
        "mapValue": {
          "fields": {
            "email": {"stringValue": "bob@example.com"}
          }
        }
      },
      "roles": {
        "arrayValue": { "values": [] }
      },
      "permissions": {
        "mapValue": {
          "fields": {
            "organizations":        {"mapValue": {"fields": {}}},
            "account_permissions":  {"mapValue": {"fields": {}}}
          }
        }
      }
    }
  }' >/dev/null
echo "[e2e-stack] Bob user document seeded."

# ---------------------------------------------------------------------------
# 5. Start FastAPI backend with emulator env vars and short cache TTL.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Starting FastAPI backend on port ${API_PORT}..."
cd api
uv sync --frozen

FIRESTORE_EMULATOR_HOST="${FIRESTORE_HOST}" \
FIREBASE_AUTH_EMULATOR_HOST="${AUTH_HOST}" \
KENE_FF_CACHE_TTL_SECONDS=0 \
GOOGLE_CLOUD_PROJECT_ID="test-project" \
GOOGLE_CLOUD_PROJECT="test-project" \
  uv run uvicorn src.kene_api.main:app --host 127.0.0.1 --port "${API_PORT}" &

cd ..

# ---------------------------------------------------------------------------
# 6. Wait for the backend /health to return 200.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Waiting for backend /health..."
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Backend failed to start"; exit 1; }

echo "[e2e-stack] Full E2E stack is ready."
echo "[e2e-stack]   Firestore emulator : http://${FIRESTORE_HOST}"
echo "[e2e-stack]   Auth emulator      : http://${AUTH_HOST}"
echo "[e2e-stack]   FastAPI backend    : http://127.0.0.1:${API_PORT}"

#!/usr/bin/env bash
# E2E stack bootstrap for Playwright tests.
#
# Starts the Firestore emulator, Firebase Auth emulator, and the FastAPI backend
# with short cache TTL so the kill-switch scenario runs in <5s instead of 60s.
# Seeds two Firebase Auth emulator users and their Firestore user documents:
#   alice@ken-e.ai  (super-admin — Firestore users/alice-uid with roles:["super_admin"])
#   bob@example.com (external user — Firestore users/bob-uid with empty roles)
#
# Uses `firebase emulators:start` instead of gcloud's emulators (which require
# the full Cloud SDK). The Firestore + Auth emulators are Java apps, so this
# script installs default-jre-headless if `java` is not already on PATH.
#
# Usage (executed in the background):
#   bash deployment/ci/scripts/start_e2e_stack.sh &
#
# Caller contract:
#   - Run from the repo root.
#   - The script supervises its children and BLOCKS after the stack is ready.
#     Once "[e2e-stack] Full E2E stack is ready." is logged, the following are live:
#       Firestore emulator : 127.0.0.1:8090
#       Auth emulator      : 127.0.0.1:9099
#       FastAPI backend    : 127.0.0.1:8000  (GET /health → 200)
#   - The caller is responsible for tearing the stack down (e.g. by killing
#     this script's process group). The EXIT trap then reaps the children.

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
# Install JDK 21 if a sufficient Java is not present.
# firebase-tools >= 14 dropped support for JDK < 21 — using default-jre on
# Ubuntu 22.04 installs OpenJDK 11, which fails with:
#   "firebase-tools no longer supports Java version before 21."
# openjdk-21-jre-headless is available in jammy-updates (Feb 2024+).
# ---------------------------------------------------------------------------
need_jdk21() {
  command -v java &>/dev/null || return 0
  local major
  major=$(java -version 2>&1 | head -n1 | sed -E 's/.*"([0-9]+).*".*/\1/')
  [ -z "$major" ] || [ "$major" -lt 21 ]
}
if need_jdk21; then
  echo "[e2e-stack] Installing OpenJDK 21 (firebase-tools requires Java >= 21)..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless >/dev/null
fi

# ---------------------------------------------------------------------------
# Install firebase-tools if not present.
# The playwright:jammy image includes Node.js; gcloud is not available there.
# ---------------------------------------------------------------------------
if ! command -v firebase &>/dev/null; then
  npm install -g firebase-tools
fi

# ---------------------------------------------------------------------------
# Cleanup trap — kill background processes when this supervisor exits.
# Fires when the caller signals the script's process group (the script blocks
# on `wait` at the end, so the trap does NOT fire after the "ready" log line).
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
# 6. Wait for the backend to be responsive on /health.
#    We accept 200 (fully healthy) AND 503 (degraded — typically Neo4j down,
#    which is expected: Neo4j has no lightweight emulator and the feature-flag
#    endpoints don't need it). 5xx from FastAPI means the app is up and
#    serving requests; only connection-level failures count as "not ready".
# ---------------------------------------------------------------------------
echo "[e2e-stack] Waiting for backend to accept requests..."
backend_responsive() {
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://127.0.0.1:${API_PORT}/health" 2>/dev/null || echo "000")
  case "$code" in 200|503) return 0 ;; *) return 1 ;; esac
}
for _ in $(seq 1 60); do
  backend_responsive && break
  sleep 1
done
backend_responsive \
  || { echo "[e2e-stack] ERROR: Backend failed to start"; exit 1; }

echo "[e2e-stack] Full E2E stack is ready."
echo "[e2e-stack]   Firestore emulator : http://${FIRESTORE_HOST}"
echo "[e2e-stack]   Auth emulator      : http://${AUTH_HOST}"
echo "[e2e-stack]   FastAPI backend    : http://127.0.0.1:${API_PORT}"

# ---------------------------------------------------------------------------
# 7. Block as a supervisor so background children stay alive until the caller
#    tears the stack down. Without this, the script would exit here, fire its
#    EXIT trap, and kill the emulators + backend before Playwright could run.
#    `wait -n` returns when ANY child exits — propagate that as a failure so
#    the caller sees a dead stack instead of silently hanging.
# ---------------------------------------------------------------------------
if wait -n; then
  echo "[e2e-stack] ERROR: a background child exited unexpectedly (rc=0)"
  exit 1
else
  rc=$?
  # rc=143 (SIGTERM) means the caller signalled us — clean shutdown path.
  if [ "$rc" -eq 143 ]; then
    exit 0
  fi
  echo "[e2e-stack] ERROR: a background child exited unexpectedly (rc=$rc)"
  exit "$rc"
fi

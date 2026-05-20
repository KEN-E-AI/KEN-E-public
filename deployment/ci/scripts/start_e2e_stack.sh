#!/usr/bin/env bash
# E2E stack bootstrap for Playwright tests.
#
# Starts the Firestore emulator, Firebase Auth emulator, and the FastAPI backend
# with short cache TTL so the kill-switch scenario runs in <5s instead of 60s.
# Seeds two Firebase Auth emulator users:
#   alice@ken-e.ai  (super-admin by email-suffix convention)
#   bob@example.com (non-super-admin external user)
#
# Usage (sourced or executed):
#   bash deployment/ci/scripts/start_e2e_stack.sh
#
# Caller contract:
#   - Run from the repo root.
#   - After this script returns, the following are live:
#       Firestore emulator : 127.0.0.1:8090
#       Auth emulator      : 127.0.0.1:9099
#       FastAPI backend    : 127.0.0.1:8000  (GET /healthz → 200)
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
# Cleanup trap — kill all background processes on exit.
# ---------------------------------------------------------------------------
cleanup() {
  echo "[e2e-stack] Cleaning up background processes..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Start Firestore emulator.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Starting Firestore emulator on ${FIRESTORE_HOST}..."
gcloud emulators firestore start --host-port="${FIRESTORE_HOST}" &

for _ in $(seq 1 60); do
  curl -sf "http://${FIRESTORE_HOST}/" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://${FIRESTORE_HOST}/" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Firestore emulator failed to start"; exit 1; }
echo "[e2e-stack] Firestore emulator ready."

# ---------------------------------------------------------------------------
# 2. Start Firebase Auth emulator.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Starting Firebase Auth emulator on ${AUTH_HOST}..."
gcloud emulators auth start --host-port="${AUTH_HOST}" &

for _ in $(seq 1 60); do
  curl -sf "http://${AUTH_HOST}/" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://${AUTH_HOST}/" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Firebase Auth emulator failed to start"; exit 1; }
echo "[e2e-stack] Firebase Auth emulator ready."

# ---------------------------------------------------------------------------
# 3. Seed test users in the Auth emulator.
#    Uses the Auth emulator REST API:
#    POST http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1/projects/{PROJECT}/accounts
#    (project name is arbitrary in emulator context — use "test-project")
# ---------------------------------------------------------------------------
PROJECT="test-project"
AUTH_BASE="http://${AUTH_HOST}/identitytoolkit.googleapis.com/v1/projects/${PROJECT}"

echo "[e2e-stack] Seeding Alice (alice@ken-e.ai)..."
curl -sf -X POST "${AUTH_BASE}/accounts" \
  -H "Content-Type: application/json" \
  -d '{
    "localId": "alice-uid",
    "email": "alice@ken-e.ai",
    "password": "password123",
    "emailVerified": true
  }' >/dev/null

echo "[e2e-stack] Seeding Bob (bob@example.com)..."
curl -sf -X POST "${AUTH_BASE}/accounts" \
  -H "Content-Type: application/json" \
  -d '{
    "localId": "bob-uid",
    "email": "bob@example.com",
    "password": "password123",
    "emailVerified": true
  }' >/dev/null

echo "[e2e-stack] Auth emulator users seeded."

# ---------------------------------------------------------------------------
# 4. Start FastAPI backend with emulator env vars and short cache TTL.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Starting FastAPI backend on port ${API_PORT}..."
cd api
uv sync --frozen

FIRESTORE_EMULATOR_HOST="${FIRESTORE_HOST}" \
FIREBASE_AUTH_EMULATOR_HOST="${AUTH_HOST}" \
KENE_FF_CACHE_TTL_SECONDS=1 \
GOOGLE_CLOUD_PROJECT_ID="test-project" \
GOOGLE_CLOUD_PROJECT="test-project" \
  uv run uvicorn src.kene_api.main:app --host 127.0.0.1 --port "${API_PORT}" &

cd ..

# ---------------------------------------------------------------------------
# 5. Wait for the backend /healthz to return 200.
# ---------------------------------------------------------------------------
echo "[e2e-stack] Waiting for backend /healthz..."
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1 \
  || { echo "[e2e-stack] ERROR: Backend failed to start"; exit 1; }

echo "[e2e-stack] Full E2E stack is ready."
echo "[e2e-stack]   Firestore emulator : http://${FIRESTORE_HOST}"
echo "[e2e-stack]   Auth emulator      : http://${AUTH_HOST}"
echo "[e2e-stack]   FastAPI backend    : http://127.0.0.1:${API_PORT}"

# Shared CI bootstrap for steps that need a live Firestore emulator + uv.
#
# Sourced (not executed) by the `api-integration-tests` and `api-unit-tests`
# steps in deployment/ci/pr_checks.yaml so the started emulator and the
# exported PATH survive into the caller's shell.
#
# Both steps run on the cloud-sdk `:emulators` image — it bundles gcloud and
# the JRE the Firestore emulator requires; python:3.11-slim has neither.
# Cloud Build steps are separate containers, so each step MUST start its own
# emulator — a background process started in another step would not survive.
#
# Caller contract:
#   - Export EMULATOR_HOST_PORT before sourcing to override the default port.
#   - The emulator listens on the host:port in EMULATOR_HOST_PORT (default
#     127.0.0.1:8090); pass that value as FIRESTORE_EMULATOR_HOST to pytest.
#   - api/.venv is built by the separate api-install step; callers use
#     `uv run --no-sync` (not `uv sync --frozen`) after sourcing this file.
#
# Because this is a sourced script file (not inline YAML `args`), it is NOT
# subject to Cloud Build variable substitution — plain $HOME / $PATH here, no
# doubled dollar-signs needed.

set -euo pipefail

EMULATOR_HOST_PORT="${EMULATOR_HOST_PORT:-127.0.0.1:8090}"

# Start the Firestore emulator in the background.
gcloud emulators firestore start --host-port="${EMULATOR_HOST_PORT}" &

# Block until the emulator accepts connections; fail fast after ~60s.
for _ in $(seq 1 60); do
  curl -sf "http://${EMULATOR_HOST_PORT}/" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://${EMULATOR_HOST_PORT}/" >/dev/null 2>&1 \
  || { echo "Firestore emulator failed to start"; exit 1; }

# Install uv via the standalone installer — the cloud-sdk image is an
# externally-managed Python env where `pip install` is blocked (PEP 668).
# The installer drops uv under $HOME/.local/bin.
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

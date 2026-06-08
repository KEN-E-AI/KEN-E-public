#!/usr/bin/env bash
# cancel_stale_pending_prod_builds.sh
#
# Cancels all PENDING Cloud Build builds for the deploy-to-prod-pipeline trigger
# in the ken-e-cicd project.
#
# Context: AH-154 — before AH-154 converted the trigger to manual-invocation,
# every push to main auto-created a PENDING prod build awaiting approval.
# ~200+ such builds accumulated. This script cancels them in bulk.
#
# Usage:
#   DRY_RUN=1 ./cancel_stale_pending_prod_builds.sh   # enumerate without cancelling
#   ./cancel_stale_pending_prod_builds.sh              # live cancel (DRY_RUN defaults to 0)
#
# Idempotent: safe to re-run — already-cancelled builds are logged as skipped.
# Re-run until the script reports "0 builds cancelled" on two successive runs.

set -euo pipefail

# Hard-code constants and make them readonly to prevent accidental environment override.
# TRIGGER_NAME is the Cloud Build built-in substitution populated automatically;
# it is queryable via substitutions.TRIGGER_NAME in gcloud builds list filters.
readonly PROJECT="ken-e-cicd"
readonly TRIGGER_NAME="deploy-to-prod-pipeline"
readonly PAGE_SIZE=100
readonly MAX_PAGES=20  # safety cap: 20 × 100 = 2000 builds per run

# Normalise DRY_RUN to "0" or "1" so callers can use "true"/"yes" as well.
case "${DRY_RUN:-0}" in
  1|true|yes|dry) DRY_RUN=1 ;;
  0|false|no|"")  DRY_RUN=0 ;;
  *)
    echo "ERROR: DRY_RUN must be 0 or 1 (got: '${DRY_RUN}'). Aborting." >&2
    exit 1
    ;;
esac

# Counters
CANCELLED=0
WOULD_CANCEL=0  # used only in DRY_RUN mode so the summary is unambiguous
SKIPPED=0
FAILED=0

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY_RUN=1 — listing PENDING builds; no cancellations will be made"
fi

log "Querying PENDING builds for trigger '${TRIGGER_NAME}' in project '${PROJECT}'..."

page=0
while [[ $page -lt $MAX_PAGES ]]; do
  page=$((page + 1))

  # Fetch a page of PENDING build IDs.
  # Notes:
  #   - Do NOT pass --ongoing: that flag restricts to WORKING/QUEUED and silently
  #     excludes PENDING (approval-awaiting) builds, which is exactly what we target.
  #   - TRIGGER_NAME is a Cloud Build built-in substitution (no underscore prefix)
  #     stamped on every triggered build; it IS queryable as substitutions.TRIGGER_NAME.
  #   - Single-quote the trigger name value in the filter to prevent shell injection.
  mapfile -t BUILD_IDS < <(
    gcloud builds list \
      --project="${PROJECT}" \
      --filter="status=PENDING AND substitutions.TRIGGER_NAME='${TRIGGER_NAME}'" \
      --format="value(id)" \
      --page-size="${PAGE_SIZE}" \
      --limit="${PAGE_SIZE}" \
      2>/dev/null
  ) || true

  if [[ ${#BUILD_IDS[@]} -eq 0 ]]; then
    log "No more PENDING builds found (page ${page})."
    break
  fi

  log "Page ${page}: found ${#BUILD_IDS[@]} PENDING build(s)."

  for BUILD_ID in "${BUILD_IDS[@]}"; do
    if [[ -z "$BUILD_ID" ]]; then
      continue
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
      log "  [DRY_RUN] Would cancel: ${BUILD_ID}"
      WOULD_CANCEL=$((WOULD_CANCEL + 1))
      continue
    fi

    # Attempt cancellation; treat "already in terminal state" as a skip.
    cancel_output=$(gcloud builds cancel "${BUILD_ID}" --project="${PROJECT}" 2>&1) && cancel_rc=0 || cancel_rc=$?

    if [[ $cancel_rc -eq 0 ]]; then
      log "  Cancelled: ${BUILD_ID}"
      CANCELLED=$((CANCELLED + 1))
    elif echo "$cancel_output" | grep -qiE "already|terminal|CANCELLED|SUCCEEDED|FAILED|TIMEOUT"; then
      log "  Skipped (already terminal): ${BUILD_ID}"
      SKIPPED=$((SKIPPED + 1))
    else
      # Truncate output before logging to avoid log-injection from API error text.
      safe_output=$(echo "$cancel_output" | tr -d '\000-\010\013\014\016-\037' | head -c 500)
      log "  ERROR cancelling ${BUILD_ID}: ${safe_output}"
      FAILED=$((FAILED + 1))
    fi

    # Throttle to avoid Cloud Build API quota exhaustion (~10 req/s quota).
    sleep 0.2
  done

  # If the page returned fewer results than PAGE_SIZE, we've reached the end.
  if [[ ${#BUILD_IDS[@]} -lt $PAGE_SIZE ]]; then
    break
  fi

  # Brief pause between pages to stay under list-API quota.
  sleep 1
done

echo ""
log "Summary:"
if [[ "$DRY_RUN" == "1" ]]; then
  log "  Would cancel: ${WOULD_CANCEL} (DRY_RUN — no builds were actually cancelled)"
else
  log "  Cancelled : ${CANCELLED}"
  log "  Skipped   : ${SKIPPED} (already in terminal state)"
  log "  Failed    : ${FAILED}"
fi

if [[ $FAILED -gt 0 ]]; then
  log "Some cancellations failed. Re-run the script to retry."
  exit 1
fi

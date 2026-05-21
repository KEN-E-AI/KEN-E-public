// TODO(telemetry): swap the console.info impl for a real Weave/W&B SDK call when
// the backend telemetry collector endpoint is wired (separate PRD). This function
// is the single swap-point — callers never need to change.

/**
 * Emits a structured page-view event.
 *
 * In dev/test: writes `console.info({ event, ts, ...props })`.
 * In production: no-op.
 */
export function emitPageView(
  event: string,
  props?: Record<string, unknown>,
): void {
  if (!import.meta.env.DEV) return;
  console.info({ event, ts: Date.now(), ...props });
}

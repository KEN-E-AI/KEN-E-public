// FastAPI emits 422 validation failures as
//   { detail: [{ loc: ["body", "<field>"], msg, type, ctx? }, ...] }
// (loc may be longer for nested bodies, but the trailing element is always
// the field name). This helper extracts per-field error messages so forms
// can render them inline.

/**
 * Pull per-field error messages out of a FastAPI 422 response.
 *
 * Returns ``null`` when nothing maps — letting the caller fall back to a
 * generic toast rather than swallowing the response silently. ``allowed``
 * gates which ``loc`` entries are surfaced; anything else is dropped (so
 * unexpected server-side fields don't end up in the UI).
 */
export function mapServerErrors<F extends string>(
  err: unknown,
  allowed: readonly F[],
): Partial<Record<F, string>> | null {
  const detail = (err as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (!Array.isArray(detail)) return null;

  const allowedSet = new Set<string>(allowed);
  const result: Partial<Record<F, string>> = {};

  for (const item of detail) {
    const loc = (item as { loc?: unknown[] })?.loc;
    const msg = (item as { msg?: string })?.msg;
    const field =
      Array.isArray(loc) && typeof loc[loc.length - 1] === "string"
        ? (loc[loc.length - 1] as string)
        : undefined;
    if (field && allowedSet.has(field) && typeof msg === "string") {
      result[field as F] = msg;
    }
  }

  return Object.keys(result).length > 0 ? result : null;
}

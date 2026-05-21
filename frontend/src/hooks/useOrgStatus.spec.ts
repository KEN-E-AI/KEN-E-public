import { describe, test, expect } from "vitest";
import { useOrgStatus } from "./useOrgStatus";

describe("useOrgStatus (stub)", () => {
  test("returns active status", () => {
    const result = useOrgStatus();
    expect(result.status).toBe("active");
  });

  test("returns null reason_message and cta_url", () => {
    const result = useOrgStatus();
    expect(result.reason_message).toBeNull();
    expect(result.cta_url).toBeNull();
  });

  test("refetch is a no-op async function", async () => {
    const result = useOrgStatus();
    await expect(result.refetch()).resolves.toBeUndefined();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

// Tests verify the fixture-flag merge behaviour rather than asserting
// BASE_FLAGS contents directly — BASE_FLAGS changes whenever a new app flag
// is added, and those additions should not break these tests.

describe("KNOWN_FLAGS registry", () => {
  it("does not add fixture keys when VITE_FF_E2E_FIXTURE_FLAGS is unset", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS).not.toContain("e2e_test_flag");
  });

  it("appends a valid fixture key", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "e2e_test_flag");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS: baseline } = await import("./registry");

    vi.resetModules();
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "");
    const { KNOWN_FLAGS: empty } = await import("./registry");

    expect(baseline).toContain("e2e_test_flag");
    expect(baseline.length).toBe(empty.length + 1);
  });

  it("drops an invalid key and warns in dev", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "INVALID KEY!");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS).not.toContain("INVALID KEY!");
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("INVALID KEY!"),
    );
    warnSpy.mockRestore();
  });

  it("deduplicates a fixture key supplied twice", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "e2e_test_flag,e2e_test_flag");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS.filter((k) => k === "e2e_test_flag")).toHaveLength(1);
  });
});

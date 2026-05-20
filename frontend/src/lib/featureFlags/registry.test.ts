import { describe, it, expect, vi, beforeEach } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe("KNOWN_FLAGS registry", () => {
  it("returns base registry when VITE_FF_E2E_FIXTURE_FLAGS is unset", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS).toEqual([]);
  });

  it("appends a valid fixture key", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "e2e_test_flag");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS).toContain("e2e_test_flag");
    expect(KNOWN_FLAGS).toHaveLength(1);
  });

  it("drops an invalid key and warns in dev", async () => {
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "INVALID KEY!");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS).toEqual([]);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("INVALID KEY!"),
    );
    warnSpy.mockRestore();
  });

  it("deduplicates keys already in base flags", async () => {
    // With empty base flags, two identical valid keys become one entry
    vi.stubEnv("VITE_FF_E2E_FIXTURE_FLAGS", "e2e_test_flag,e2e_test_flag");
    vi.stubEnv("VITE_ENVIRONMENT", "development");
    const { KNOWN_FLAGS } = await import("./registry");
    expect(KNOWN_FLAGS.filter((k) => k === "e2e_test_flag")).toHaveLength(1);
  });
});

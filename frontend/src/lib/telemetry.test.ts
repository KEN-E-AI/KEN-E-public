import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { emitPageView } from "./telemetry";

describe("emitPageView", () => {
  let consoleSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  it("calls console.info exactly once in dev mode", () => {
    // vite.config.ts sets environment to 'jsdom' for tests; import.meta.env.DEV
    // is true in test runs (Vitest uses dev mode by default).
    emitPageView("chat.page.render");
    expect(consoleSpy).toHaveBeenCalledTimes(1);
  });

  it("includes the event name in the payload", () => {
    emitPageView("chat.page.render");
    const [payload] = consoleSpy.mock.calls[0] as [Record<string, unknown>];
    expect(payload.event).toBe("chat.page.render");
  });

  it("includes a numeric ts field", () => {
    emitPageView("chat.page.render");
    const [payload] = consoleSpy.mock.calls[0] as [Record<string, unknown>];
    expect(typeof payload.ts).toBe("number");
  });

  it("spreads extra props into the payload", () => {
    emitPageView("chat.page.render", { session_id: "abc123", view: "message" });
    const [payload] = consoleSpy.mock.calls[0] as [Record<string, unknown>];
    expect(payload.session_id).toBe("abc123");
    expect(payload.view).toBe("message");
  });

  it("works without props (undefined props)", () => {
    expect(() => emitPageView("chat.page.render")).not.toThrow();
  });
});

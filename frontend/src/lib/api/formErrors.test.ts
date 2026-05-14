import { describe, it, expect } from "vitest";
import { mapServerErrors } from "./formErrors";

const ALLOWED = ["title", "instruction", "description"] as const;

describe("mapServerErrors", () => {
  it("maps a single 422 detail entry onto its field", () => {
    const err = {
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: "string_too_short",
              loc: ["body", "instruction"],
              msg: "String should have at least 10 characters",
            },
          ],
        },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toEqual({
      instruction: "String should have at least 10 characters",
    });
  });

  it("maps multiple entries from one response", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "title"], msg: "Title too long" },
            { loc: ["body", "description"], msg: "Description too short" },
          ],
        },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toEqual({
      title: "Title too long",
      description: "Description too short",
    });
  });

  it("drops entries whose field is not in the allowed list", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "title"], msg: "ok" },
            { loc: ["body", "secret_field"], msg: "should be dropped" },
          ],
        },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toEqual({ title: "ok" });
  });

  it("uses the trailing loc element as the field name", () => {
    // FastAPI nests ``loc`` for nested bodies — only the last segment is
    // the actual field name, so the helper must read from the tail.
    const err = {
      response: {
        data: {
          detail: [{ loc: ["body", "wrapper", "title"], msg: "ok" }],
        },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toEqual({ title: "ok" });
  });

  it("returns null when detail is missing", () => {
    expect(mapServerErrors({ response: { data: {} } }, ALLOWED)).toBeNull();
    expect(mapServerErrors({ response: {} }, ALLOWED)).toBeNull();
    expect(mapServerErrors({}, ALLOWED)).toBeNull();
    expect(mapServerErrors(null, ALLOWED)).toBeNull();
  });

  it("returns null when detail is not an array", () => {
    expect(
      mapServerErrors(
        { response: { data: { detail: "unexpected string" } } },
        ALLOWED,
      ),
    ).toBeNull();
  });

  it("returns null when no entries match the allowed list", () => {
    const err = {
      response: {
        data: { detail: [{ loc: ["body", "unknown"], msg: "n/a" }] },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toBeNull();
  });

  it("skips malformed entries (missing loc or msg)", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "title"] }, // no msg
            { msg: "no loc" },
            { loc: ["body", "title"], msg: "valid" },
          ],
        },
      },
    };
    expect(mapServerErrors(err, ALLOWED)).toEqual({ title: "valid" });
  });
});

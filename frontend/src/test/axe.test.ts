import { describe, it, expect } from "vitest";
import { runAxe } from "./axe";

describe("runAxe helper", () => {
  it("returns no violations on a trivial accessible element", async () => {
    const div = document.createElement("div");
    document.body.appendChild(div);
    const results = await runAxe(div);
    document.body.removeChild(div);
    expect(results).toHaveNoViolations();
  });

  it("returns no violations on a labelled button", async () => {
    const btn = document.createElement("button");
    btn.textContent = "Click me";
    document.body.appendChild(btn);
    const results = await runAxe(btn);
    document.body.removeChild(btn);
    expect(results).toHaveNoViolations();
  });
});

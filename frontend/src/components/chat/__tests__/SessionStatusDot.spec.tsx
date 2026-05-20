import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionStatusDot } from "../SessionStatusDot";
import type { SessionStatusInput } from "../SessionStatusDot";
import { runAxe } from "@/test/axe";

const MSG = "2026-04-10T10:00:00Z";
const BEFORE_MSG = "2026-04-10T09:00:00Z";
const AFTER_MSG = "2026-04-10T11:00:00Z";

/**
 * 10-case component render table per CH-PRD-02 §7 AC-6 + §8 frontend unit tests.
 * Plus 1 axe-clean test on the active state.
 */
describe("SessionStatusDot", () => {
  const cases: [
    string,
    SessionStatusInput,
    "active" | "needs-review" | "idle",
  ][] = [
    [
      "running=true, msg=null, viewed=null → active",
      {
        is_agent_running: true,
        last_agent_message_at: null,
        last_viewed_at: null,
      },
      "active",
    ],
    [
      "running=true, msg=set, viewed=null → active",
      {
        is_agent_running: true,
        last_agent_message_at: MSG,
        last_viewed_at: null,
      },
      "active",
    ],
    [
      "running=true, msg=null, viewed=set → active",
      {
        is_agent_running: true,
        last_agent_message_at: null,
        last_viewed_at: MSG,
      },
      "active",
    ],
    [
      "running=true, msg=set, viewed=set → active",
      {
        is_agent_running: true,
        last_agent_message_at: MSG,
        last_viewed_at: BEFORE_MSG,
      },
      "active",
    ],
    [
      "running=false, msg=null, viewed=null → idle",
      {
        is_agent_running: false,
        last_agent_message_at: null,
        last_viewed_at: null,
      },
      "idle",
    ],
    [
      "running=false, msg=null, viewed=set → idle",
      {
        is_agent_running: false,
        last_agent_message_at: null,
        last_viewed_at: MSG,
      },
      "idle",
    ],
    [
      "running=false, msg=set, viewed=null → needs-review",
      {
        is_agent_running: false,
        last_agent_message_at: MSG,
        last_viewed_at: null,
      },
      "needs-review",
    ],
    [
      "running=false, msg=set, viewed=set: msg > viewed → needs-review",
      {
        is_agent_running: false,
        last_agent_message_at: MSG,
        last_viewed_at: BEFORE_MSG,
      },
      "needs-review",
    ],
    [
      "running=false, msg=set, viewed=set: msg < viewed → idle",
      {
        is_agent_running: false,
        last_agent_message_at: MSG,
        last_viewed_at: AFTER_MSG,
      },
      "idle",
    ],
    [
      "running=false, msg=set, viewed=set: msg === viewed → idle",
      {
        is_agent_running: false,
        last_agent_message_at: MSG,
        last_viewed_at: MSG,
      },
      "idle",
    ],
  ];

  test.each(cases)("%s", (_label, item, expectedStatus) => {
    const { container } = render(<SessionStatusDot item={item} />);

    if (expectedStatus === "active") {
      const dot = screen.getByTitle("Agent working");
      expect(dot).toBeInTheDocument();
      expect(dot).toHaveAttribute("aria-label", "Agent working");
      expect(dot.className).toContain("bg-[var(--color-teal-500)]");
      expect(dot.className).toContain("rounded-full");
      // Idle placeholder has no title
      expect(container.querySelector("[title]")).toBe(dot);
    } else if (expectedStatus === "needs-review") {
      const dot = screen.getByTitle("Unread reply");
      expect(dot).toBeInTheDocument();
      expect(dot).toHaveAttribute("aria-label", "Unread reply");
      expect(dot.className).toContain("bg-[#F97066]");
      expect(dot.className).toContain("rounded-full");
      expect(container.querySelector("[title]")).toBe(dot);
    } else {
      // idle: no title attribute on any element, just the empty placeholder
      expect(container.querySelector("[title]")).toBeNull();
      // The placeholder div should exist and have size-2.5 class
      const placeholder = container.firstElementChild;
      expect(placeholder).toBeInTheDocument();
      expect(placeholder?.className).toContain("size-2.5");
      // No colored rounded-full
      expect(placeholder?.className).not.toContain("rounded-full");
    }
  });

  test("active state passes axe accessibility check", async () => {
    const { container } = render(
      <SessionStatusDot
        item={{
          is_agent_running: true,
          last_agent_message_at: null,
          last_viewed_at: null,
        }}
      />,
    );
    const results = await runAxe(container);
    expect(results).toHaveNoViolations();
  });
});

import { describe, test, expect } from "vitest";
import { deriveSessionStatus } from "../SessionStatusDot";
import type { SessionStatusInput } from "../SessionStatusDot";

const MSG = "2026-04-10T10:00:00Z";
const BEFORE_MSG = "2026-04-10T09:00:00Z";
const AFTER_MSG = "2026-04-10T11:00:00Z";

/**
 * 10-case truth table per CH-PRD-02 §7 AC-6.
 * 8 boolean combinations of (is_agent_running, last_agent_message_at, last_viewed_at)
 * plus 2 sub-cases for the (false, set, set) timestamp-ordering branch.
 */
describe("deriveSessionStatus", () => {
  const cases: [
    string,
    SessionStatusInput,
    "active" | "needs-review" | "idle",
  ][] = [
    // ── is_agent_running = true (all 4 null/set combos → active) ──────────────
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
    // ── is_agent_running = false, msg=null (never needs-review) ───────────────
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
    // ── is_agent_running = false, msg=set, viewed=null → needs-review ─────────
    [
      "running=false, msg=set, viewed=null → needs-review",
      {
        is_agent_running: false,
        last_agent_message_at: MSG,
        last_viewed_at: null,
      },
      "needs-review",
    ],
    // ── is_agent_running = false, msg=set, viewed=set: timestamp ordering ─────
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

  test.each(cases)("%s", (_label, input, expected) => {
    expect(deriveSessionStatus(input)).toBe(expected);
  });
});

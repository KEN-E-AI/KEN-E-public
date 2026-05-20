import { cn } from "@/lib/utils";

// TODO(CH-18): replace with Pick<ChatSessionSidebarItem, "is_agent_running" | "last_agent_message_at" | "last_viewed_at">
// when ChatSessionSidebarItem ships. Structural compatibility is guaranteed — same three fields, same types.
export type SessionStatusInput = {
  is_agent_running: boolean;
  last_agent_message_at: string | null;
  last_viewed_at: string | null;
};

export type SessionStatus = "active" | "needs-review" | "idle";

/**
 * Canonical 3-state derivation per PRD §4.2 (CH-PRD-02).
 * Called by every renderer — sidebar expanded, sidebar collapsed, page header.
 * No ad-hoc derivation elsewhere.
 */
export function deriveSessionStatus(item: SessionStatusInput): SessionStatus {
  if (item.is_agent_running) return "active";
  if (
    item.last_agent_message_at &&
    (!item.last_viewed_at || item.last_agent_message_at > item.last_viewed_at)
  )
    return "needs-review";
  return "idle";
}

type SessionStatusDotProps = {
  item: SessionStatusInput;
  className?: string;
};

/**
 * Renders a 10×10px status dot (or empty placeholder for idle) matching the
 * figma design. Three states:
 *   active      — teal-500 fill + teal glow + tooltip "Agent working"
 *   needs-review — coral (#F97066) fill + coral glow + tooltip "Unread reply"
 *   idle        — empty size-2.5 placeholder (preserves row layout)
 *
 * Uses native `title=` for the hover tooltip (zero-dependency; matches figma
 * export). `aria-label` is added alongside `title` for screen-reader support.
 */
export function SessionStatusDot({ item, className }: SessionStatusDotProps) {
  const status = deriveSessionStatus(item);

  if (status === "active") {
    return (
      <div
        className={cn(
          "size-2.5 rounded-full bg-[var(--color-teal-500)]",
          className,
        )}
        style={{ boxShadow: "0 0 4px rgba(16, 185, 129, 0.5)" }}
        title="Agent working"
        aria-label="Agent working"
        role="img"
      />
    );
  }

  if (status === "needs-review") {
    return (
      <div
        className={cn("size-2.5 rounded-full bg-[#F97066]", className)}
        style={{ boxShadow: "0 0 4px rgba(249, 112, 102, 0.5)" }}
        title="Unread reply"
        aria-label="Unread reply"
        role="img"
      />
    );
  }

  // idle — empty placeholder preserves sidebar row alignment (matches figma line 191)
  return <div className={cn("size-2.5", className)} />;
}

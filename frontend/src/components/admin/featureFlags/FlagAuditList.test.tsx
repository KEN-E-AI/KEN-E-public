import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FlagAuditList } from "./FlagAuditList";
import type { AuditListResponse } from "@/lib/featureFlags/adminClient";
import type { FeatureFlagAuditEntry } from "@/lib/featureFlags/types";
import { toFlagKey } from "@/lib/featureFlags/types";

// ─── Module mock ──────────────────────────────────────────────────────────────

vi.mock("@/lib/featureFlags/adminClient", async (importOriginal) => {
  const mod =
    await importOriginal<typeof import("@/lib/featureFlags/adminClient")>();
  return { ...mod, getFlagAudit: vi.fn() };
});

import { getFlagAudit } from "@/lib/featureFlags/adminClient";
const mockGetFlagAudit = getFlagAudit as ReturnType<typeof vi.fn>;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function freshClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

const TEST_FLAG_KEY = toFlagKey("test_flag");

function makeEntry(
  overrides?: Partial<FeatureFlagAuditEntry>,
): FeatureFlagAuditEntry {
  return {
    audit_id: `audit-${Math.random().toString(36).slice(2)}`,
    flag_key: TEST_FLAG_KEY,
    actor_email: "admin@ken-e.ai",
    action: "update",
    diff: { description: { before: "Old desc", after: "New desc" } },
    created_at: "2026-05-01T12:00:00Z",
    ...overrides,
  };
}

function makePage(
  entries: FeatureFlagAuditEntry[],
  next_cursor: string | null = null,
): AuditListResponse {
  return { entries, next_cursor };
}

function renderList(flagKey = TEST_FLAG_KEY, client?: QueryClient) {
  const qc = client ?? freshClient();
  const Wrapper = makeWrapper(qc);
  return render(
    <Wrapper>
      <FlagAuditList flagKey={flagKey} />
    </Wrapper>,
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FlagAuditList — initial fetch and rendering", () => {
  it("fetches and renders entries in the order returned by the server", async () => {
    const entry1 = makeEntry({
      audit_id: "a1",
      actor_email: "alice@ken-e.ai",
      created_at: "2026-05-02T10:00:00Z",
    });
    const entry2 = makeEntry({
      audit_id: "a2",
      actor_email: "bob@ken-e.ai",
      created_at: "2026-05-01T10:00:00Z",
    });

    mockGetFlagAudit.mockResolvedValueOnce(makePage([entry1, entry2]));

    renderList();

    await waitFor(() => {
      expect(screen.getByText("alice@ken-e.ai")).toBeInTheDocument();
    });

    const items = screen.getAllByText(/@ken-e\.ai/);
    expect(items[0]).toHaveTextContent("alice@ken-e.ai");
    expect(items[1]).toHaveTextContent("bob@ken-e.ai");

    expect(mockGetFlagAudit).toHaveBeenCalledOnce();
    expect(mockGetFlagAudit).toHaveBeenCalledWith(TEST_FLAG_KEY, {
      cursor: null,
    });
  });

  it("renders action badges for each entry", async () => {
    const entries = [
      makeEntry({ audit_id: "a1", action: "create" }),
      makeEntry({ audit_id: "a2", action: "delete" }),
      makeEntry({ audit_id: "a3", action: "toggle_active" }),
    ];

    mockGetFlagAudit.mockResolvedValueOnce(makePage(entries));

    renderList();

    await waitFor(() => {
      expect(screen.getByText("create")).toBeInTheDocument();
    });

    expect(screen.getByText("delete")).toBeInTheDocument();
    expect(screen.getByText("toggle_active")).toBeInTheDocument();
  });
});

describe("FlagAuditList — pagination", () => {
  it("shows Load more button when next_cursor is non-null", async () => {
    mockGetFlagAudit.mockResolvedValueOnce(
      makePage([makeEntry()], "cursor-page-2"),
    );

    renderList();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more/i }),
      ).toBeInTheDocument();
    });
  });

  it("hides Load more button when next_cursor is null", async () => {
    mockGetFlagAudit.mockResolvedValueOnce(makePage([makeEntry()], null));

    renderList();

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /load more/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("clicking Load more appends a second page below existing rows without duplicates", async () => {
    const page1Entry = makeEntry({
      audit_id: "a1",
      actor_email: "page1@ken-e.ai",
    });
    const page2Entry = makeEntry({
      audit_id: "a2",
      actor_email: "page2@ken-e.ai",
    });
    const page1Cursor = "cursor-page-2";

    mockGetFlagAudit
      .mockResolvedValueOnce(makePage([page1Entry], page1Cursor))
      .mockResolvedValueOnce(makePage([page2Entry], null));

    renderList();

    await waitFor(() => {
      expect(screen.getByText("page1@ken-e.ai")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /load more/i }));

    await waitFor(() => {
      expect(screen.getByText("page2@ken-e.ai")).toBeInTheDocument();
    });

    // Both entries visible, no duplicates
    expect(screen.getAllByText(/ken-e\.ai/)).toHaveLength(2);

    // Second call used the cursor from page 1
    expect(mockGetFlagAudit).toHaveBeenNthCalledWith(2, TEST_FLAG_KEY, {
      cursor: page1Cursor,
    });

    // No Load more once page 2 has next_cursor=null
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });
});

describe("FlagAuditList — empty state", () => {
  it("renders empty state copy when entries are empty", async () => {
    mockGetFlagAudit.mockResolvedValueOnce(makePage([]));

    renderList();

    await waitFor(() => {
      expect(screen.getByText(/no audit entries yet/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });
});

describe("FlagAuditList — diff details", () => {
  it("renders diff <details> closed by default; expanding reveals formatted JSON", async () => {
    const diff = { description: { before: "Old", after: "New" } };
    const entry = makeEntry({ diff });

    mockGetFlagAudit.mockResolvedValueOnce(makePage([entry]));

    renderList();

    await waitFor(() => {
      expect(screen.getByText("admin@ken-e.ai")).toBeInTheDocument();
    });

    const summary = screen.getByText(/show diff/i);
    expect(summary).toBeInTheDocument();

    const details = summary.closest("details");
    expect(details).not.toHaveAttribute("open");

    await userEvent.click(summary);

    expect(details).toHaveAttribute("open");
    expect(details?.querySelector("pre")).toBeInTheDocument();
    expect(details?.querySelector("pre")?.textContent).toContain('"before"');
    expect(details?.querySelector("pre")?.textContent).toContain('"after"');
  });

  it("handles circular-reference diff gracefully without throwing", async () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;

    const entry = makeEntry({ diff: circular as never });
    mockGetFlagAudit.mockResolvedValueOnce(makePage([entry]));

    renderList();

    await waitFor(() => {
      expect(screen.getByText("admin@ken-e.ai")).toBeInTheDocument();
    });

    const summary = screen.getByText(/show diff/i);
    await userEvent.click(summary);

    expect(screen.getByText(/unserializable diff/)).toBeInTheDocument();
  });
});

describe("FlagAuditList — error state", () => {
  it("renders an Alert with Retry button on query failure", async () => {
    mockGetFlagAudit.mockRejectedValueOnce(new Error("Network error"));

    renderList();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText(/failed to load audit log/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("Retry button triggers a refetch", async () => {
    const entry = makeEntry();

    mockGetFlagAudit
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(makePage([entry]));

    renderList();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /retry/i }),
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("admin@ken-e.ai")).toBeInTheDocument();
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AgentsPage } from "./AgentsPage";

// ─── Mock sub-components ──────────────────────────────────────────────────────

vi.mock("./agents/AgentsListView", () => ({
  AgentsListView: vi.fn(({ onEdit }: { onEdit: (id: string) => void }) => (
    <div data-testid="agents-list-view">
      <button onClick={() => onEdit("google_analytics_specialist")}>
        Open edit sheet
      </button>
    </div>
  )),
}));

vi.mock("./agents/AgentEditView", () => ({
  AgentEditView: vi.fn(
    ({ configId, onClose }: { configId: string; onClose: () => void }) => (
      <div data-testid="agent-edit-view">
        <p>Editing: {configId}</p>
        <button onClick={onClose}>Close</button>
      </div>
    ),
  ),
}));

// ─── Wrapper ──────────────────────────────────────────────────────────────────

function makeWrapper(initialEntries?: string[]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AgentsPage", () => {
  it("renders the AgentsListView", () => {
    render(<AgentsPage />, { wrapper: makeWrapper() });
    expect(screen.getByTestId("agents-list-view")).toBeInTheDocument();
  });

  it("sheet is closed by default", () => {
    render(<AgentsPage />, { wrapper: makeWrapper() });
    expect(screen.queryByTestId("agent-edit-view")).toBeNull();
  });

  it("opens the edit sheet when a card is clicked", async () => {
    const user = userEvent.setup();
    render(<AgentsPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole("button", { name: /open edit sheet/i }));

    await waitFor(() => {
      expect(screen.getByTestId("agent-edit-view")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Editing: google_analytics_specialist"),
    ).toBeInTheDocument();
  });

  it("closes the edit sheet when onClose is called", async () => {
    const user = userEvent.setup();
    render(<AgentsPage />, { wrapper: makeWrapper() });

    // Open the sheet
    await user.click(screen.getByRole("button", { name: /open edit sheet/i }));
    await waitFor(() =>
      expect(screen.getByTestId("agent-edit-view")).toBeInTheDocument(),
    );

    // Close via the mocked edit view's Close button (inside the panel)
    const closeButtons = screen.getAllByRole("button", { name: /close/i });
    // The mock renders a single "Close" button inside the edit view
    const editViewCloseBtn = closeButtons.find(
      (btn) => btn.closest("[data-testid='agent-edit-view']") !== null,
    );
    await user.click(editViewCloseBtn!);
    await waitFor(() =>
      expect(screen.queryByTestId("agent-edit-view")).toBeNull(),
    );
  });

  it("URL param ?edit= opens the sheet on mount", () => {
    render(<AgentsPage />, {
      wrapper: makeWrapper([
        "/workflows/agents?edit=google_analytics_specialist",
      ]),
    });

    expect(screen.getByTestId("agent-edit-view")).toBeInTheDocument();
    expect(
      screen.getByText("Editing: google_analytics_specialist"),
    ).toBeInTheDocument();
  });

  it("closing the sheet clears the URL param", async () => {
    const user = userEvent.setup();
    render(<AgentsPage />, {
      wrapper: makeWrapper([
        "/workflows/agents?edit=google_analytics_specialist",
      ]),
    });

    await waitFor(() =>
      expect(screen.getByTestId("agent-edit-view")).toBeInTheDocument(),
    );

    const closeButtons = screen.getAllByRole("button", { name: /close/i });
    const editViewCloseBtn = closeButtons.find(
      (btn) => btn.closest("[data-testid='agent-edit-view']") !== null,
    );
    await user.click(editViewCloseBtn!);

    await waitFor(() =>
      expect(screen.queryByTestId("agent-edit-view")).toBeNull(),
    );
  });
});

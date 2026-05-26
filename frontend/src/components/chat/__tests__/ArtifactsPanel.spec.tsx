import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { ArtifactsPanel } from "../ArtifactsPanel";
import { runAxe } from "@/test/axe";
import type { ChatSessionId, ListArtifactsResponse } from "@/lib/chatApi";

vi.mock("@/hooks/useArtifacts", () => ({
  useArtifacts: vi.fn(),
}));

import { useArtifacts } from "@/hooks/useArtifacts";
const mockUseArtifacts = vi.mocked(useArtifacts);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

const SESSION_ID = "sess_abc" as ChatSessionId;

const ARTIFACTS_WITH_ITEMS: ListArtifactsResponse = {
  items: [
    {
      artifact_index: {
        artifact_id: "artifact_abc123",
        session_id: "sess_abc",
        filename: "campaign-report.pdf",
        mime_type: "application/pdf",
        size_bytes: 204800,
        version: 0,
        gcs_path: "gs://bucket/app/user/sess_abc/campaign-report.pdf/0",
        created_by_tool: "generate_report",
        created_at: "2026-05-01T09:00:00Z",
      },
      signed_url: "https://storage.googleapis.com/bucket/signed?token=abc",
      signed_url_expires_at: "2026-05-01T10:00:00Z",
    },
    {
      artifact_index: {
        artifact_id: "artifact_def456",
        session_id: "sess_abc",
        filename: "social-calendar.csv",
        mime_type: "text/csv",
        size_bytes: 1536,
        version: 0,
        gcs_path: "gs://bucket/app/user/sess_abc/social-calendar.csv/0",
        created_by_tool: "create_calendar",
        created_at: "2026-05-01T10:00:00Z",
      },
      signed_url: "https://storage.googleapis.com/bucket/signed?token=def",
      signed_url_expires_at: "2026-05-01T11:00:00Z",
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── TC-1: null sessionId renders nothing ───────────────────────────────────

describe("ArtifactsPanel", () => {
  it("TC-1: renders nothing when sessionId is null", () => {
    mockUseArtifacts.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      isSuccess: false,
    } as ReturnType<typeof useArtifacts>);
    const { container } = render(<ArtifactsPanel sessionId={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  // ─── TC-2: loading skeletons ───────────────────────────────────────────────

  it("TC-2: shows loading skeletons while fetching", () => {
    mockUseArtifacts.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      isSuccess: false,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByLabelText("Loading artifacts")).toBeInTheDocument();
  });

  // ─── TC-3: error state ────────────────────────────────────────────────────

  it("TC-3: shows error message on fetch failure", () => {
    mockUseArtifacts.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      isSuccess: false,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("Failed to load documents.")).toBeInTheDocument();
  });

  // ─── TC-4: empty state ────────────────────────────────────────────────────

  it("TC-4: shows empty state message when no artifacts", () => {
    mockUseArtifacts.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("No documents yet.")).toBeInTheDocument();
  });

  // ─── TC-5: renders filenames ──────────────────────────────────────────────

  it("TC-5: renders filenames for all artifacts", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("campaign-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("social-calendar.csv")).toBeInTheDocument();
  });

  // ─── TC-6: formats file size ──────────────────────────────────────────────

  it("TC-6: formats size_bytes as human-readable (200 KB for 204800 bytes)", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("200 KB")).toBeInTheDocument();
  });

  // ─── TC-7: count badge ────────────────────────────────────────────────────

  it("TC-7: renders count badge equal to items.length", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  // ─── TC-8: KEN-E badge rendered ───────────────────────────────────────────

  it("TC-8: renders KEN-E badge for each agent-created artifact", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    const keneBadges = screen.getAllByText("KEN-E");
    expect(keneBadges).toHaveLength(2);
  });

  // ─── TC-9: artifact row links to signed_url ───────────────────────────────

  it("TC-9: artifact row is an anchor linking to signed_url with noopener", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    const link = screen.getByRole("link", { name: "campaign-report.pdf" });
    expect(link).toHaveAttribute(
      "href",
      "https://storage.googleapis.com/bucket/signed?token=abc",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  // ─── TC-10: Documents heading ─────────────────────────────────────────────

  it("TC-10: renders Documents heading", () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    render(<ArtifactsPanel sessionId={SESSION_ID} />);
    expect(
      screen.getByRole("heading", { name: "Documents" }),
    ).toBeInTheDocument();
  });

  // ─── TC-11: axe accessibility ─────────────────────────────────────────────

  it("TC-11: passes axe accessibility check with populated artifacts", async () => {
    mockUseArtifacts.mockReturnValue({
      data: ARTIFACTS_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useArtifacts>);
    const { container } = render(<ArtifactsPanel sessionId={SESSION_ID} />, {
      wrapper: createWrapper(),
    });
    const results = await runAxe(container);
    expect(results).toHaveNoViolations();
  });
});

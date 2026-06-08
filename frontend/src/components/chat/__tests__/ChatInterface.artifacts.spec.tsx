/**
 * Integration tests for ChatInterface artifacts SSE integration.
 *
 * Covers:
 * - Single artifact renders ChatArtifactRenderer (data-testid="chat-artifact-renderer").
 * - Multiple artifacts in one event render in correct list order.
 * - Legacy text-only stream (no artifacts event) leaves ChatArtifactRenderer absent.
 * - Settings popover opens on "Chart settings" button click.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { StreamEvent } from "@/lib/chatApi";

// ---------------------------------------------------------------------------
// Mocks — mirror the pattern from ChatInterface.spec.tsx
// ---------------------------------------------------------------------------

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...p }: any) => <div {...p}>{children}</div>,
    p: ({ children, ...p }: any) => <p {...p}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("react-vega", () => ({
  VegaEmbed: ({ spec }: { spec: unknown }) => (
    <div data-testid="vega-embed" data-spec={JSON.stringify(spec)} />
  ),
}));

vi.mock("@/lib/chatApi", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/chatApi")>("@/lib/chatApi");
  return {
    ...actual,
    getConversationHistory: vi.fn().mockResolvedValue([]),
    streamChatCompletion: vi.fn(),
  };
});

vi.mock("@/lib/parseConversationHistory", () => ({
  parseConversationHistory: vi.fn().mockReturnValue([]),
}));

vi.mock("@/hooks/useOrgStatus", () => ({
  useOrgStatus: vi.fn().mockReturnValue({ status: "active" }),
}));

vi.mock("@/hooks/useMarkRead", () => ({
  useMarkRead: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { ChatInterface } from "../ChatInterface";
import { streamChatCompletion } from "@/lib/chatApi";

const mockStreamChatCompletion = vi.mocked(streamChatCompletion);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function* makeStream(events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  for (const ev of events) {
    yield ev;
  }
}

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

const sampleArtifact = {
  type: "visualization" as const,
  spec: {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    mark: "line",
    data: { values: [{ x: 1, y: 2 }] },
    encoding: { x: { field: "x" }, y: { field: "y" } },
  },
  metadata: {
    chart_type_suggestion: "line" as const,
    title: "Sessions",
    data_source: "ga",
  },
};

const sampleArtifact2 = {
  type: "visualization" as const,
  spec: {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    mark: "bar",
    data: { values: [{ x: 3, y: 4 }] },
    encoding: { x: { field: "x" }, y: { field: "y" } },
  },
  metadata: {
    chart_type_suggestion: "bar" as const,
    title: "Conversions",
    data_source: "ads",
  },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatInterface — artifacts SSE integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("single artifact renders ChatArtifactRenderer", async () => {
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([
        { type: "text", text: "Here is the chart:" },
        { type: "artifacts", artifacts: [sampleArtifact], author: "model" },
      ]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "show me a chart");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getAllByTestId("chat-artifact-renderer")).toHaveLength(1);
    });

    // Text message also renders.
    expect(screen.getByText("Here is the chart:")).toBeInTheDocument();
  });

  test("multiple artifacts render in list order", async () => {
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([
        {
          type: "artifacts",
          artifacts: [sampleArtifact, sampleArtifact2],
          author: "model",
        },
      ]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "show me two charts");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getAllByTestId("chat-artifact-renderer")).toHaveLength(2);
    });

    // Both vega-embed stubs appear in document order.
    const vegaEmbeds = screen.getAllByTestId("vega-embed");
    expect(vegaEmbeds).toHaveLength(2);

    // First embed's spec contains the first artifact's title ("Sessions" in the
    // spec config), second contains the second artifact's title ("Conversions").
    // We check the serialised data-spec attribute for a distinguishing field.
    const firstSpec = vegaEmbeds[0].getAttribute("data-spec") ?? "";
    const secondSpec = vegaEmbeds[1].getAttribute("data-spec") ?? "";
    expect(firstSpec).toContain('"line"');
    expect(secondSpec).toContain('"bar"');
  });

  test("legacy text-only stream: ChatArtifactRenderer absent", async () => {
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([{ type: "text", text: "Hello" }]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "hello");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("chat-artifact-renderer")).toBeNull();
  });

  test("settings popover opens on Chart settings button click", async () => {
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([
        { type: "artifacts", artifacts: [sampleArtifact], author: "model" },
      ]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "show me a chart");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getAllByTestId("chat-artifact-renderer")).toHaveLength(1);
    });

    // The settings button is present (opacity-0 by default but in the DOM).
    const settingsButton = screen.getByRole("button", {
      name: /chart settings/i,
    });

    await act(async () => {
      await userEvent.click(settingsButton);
    });

    // ChartSettingsPopover renders "View as" label and "Auto" button when open.
    await waitFor(() => {
      expect(screen.getByText("View as")).toBeInTheDocument();
    });
    expect(screen.getByText("Auto")).toBeInTheDocument();
    expect(screen.getByTestId("chart-settings-popover")).toBeInTheDocument();
  });
});

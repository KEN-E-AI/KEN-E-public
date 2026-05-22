import { describe, test, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { ChatInterface } from "./ChatInterface";

// ─── Module mocks ────────────────────────────────────────────────────────────

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...p }: any) => <div {...p}>{children}</div>,
    p: ({ children, ...p }: any) => <p {...p}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("@/lib/chatApi", () => ({
  streamChatCompletion: vi.fn(),
}));

vi.mock("@/hooks/useOrgStatus", () => ({
  useOrgStatus: vi.fn(() => ({
    status: "active",
    reason_message: null,
    cta_url: null,
    refetch: () => Promise.resolve(),
  })),
}));

vi.mock("@/hooks/useMarkRead", () => ({
  useMarkRead: vi.fn(),
}));

import { streamChatCompletion } from "@/lib/chatApi";
import { useOrgStatus } from "@/hooks/useOrgStatus";
import { useMarkRead } from "@/hooks/useMarkRead";

const mockStreamChatCompletion = vi.mocked(streamChatCompletion);
const mockUseOrgStatus = vi.mocked(useOrgStatus);
const mockUseMarkRead = vi.mocked(useMarkRead);

// Helper: build an async generator that yields chunks then completes
async function* makeStream(
  chunks: string[],
): AsyncGenerator<string, void, unknown> {
  for (const chunk of chunks) {
    yield chunk;
  }
}

describe("ChatInterface", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseOrgStatus.mockReturnValue({
      status: "active",
      reason_message: null,
      cta_url: null,
      refetch: () => Promise.resolve(),
    });
  });

  // ── TC-1: SSE stream appends chunks to the message list ─────────────────

  test("TC-1: SSE stream chunks are appended to the message list", async () => {
    mockStreamChatCompletion.mockReturnValue(makeStream(["Hello", " world"]));

    render(<ChatInterface />);

    const input = screen.getByRole("textbox", { name: /chat input/i });
    const sendBtn = screen.getByRole("button", { name: /send message/i });

    fireEvent.change(input, { target: { value: "Hi there" } });
    fireEvent.click(sendBtn);

    // User message appears
    await waitFor(() =>
      expect(screen.getByText("Hi there")).toBeInTheDocument(),
    );

    // Streamed content accumulates
    await waitFor(() =>
      expect(screen.getByText("Hello world")).toBeInTheDocument(),
    );
  });

  // ── TC-2: Thinking-block visible while stream in-flight ──────────────────

  test("TC-2: ThinkingBlock renders while SSE stream is in-flight", async () => {
    // A stream that never resolves until we tell it to
    let resolve!: () => void;
    const blockingStream = (async function* () {
      yield "partial";
      await new Promise<void>((r) => (resolve = r));
    })();
    mockStreamChatCompletion.mockReturnValue(blockingStream);

    render(<ChatInterface />);

    const input = screen.getByRole("textbox", { name: /chat input/i });
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    // ThinkingBlock appears while streaming
    await waitFor(() =>
      expect(screen.getByText("Reasoning...")).toBeInTheDocument(),
    );

    // Unblock stream so the component can clean up
    await act(async () => {
      resolve();
    });
  });

  // ── TC-3: Composer disabled when useOrgStatus returns inactive_* ─────────

  test("TC-3: composer is disabled when org status is inactive_overage", () => {
    mockUseOrgStatus.mockReturnValue({
      status: "inactive_overage",
      reason_message: "Overage limit reached.",
      cta_url: "/billing",
      refetch: () => Promise.resolve(),
    });

    render(<ChatInterface />);

    expect(screen.getByRole("textbox", { name: /chat input/i })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /send message/i }),
    ).toBeDisabled();
  });

  test("TC-3b: composer is enabled when org status is active", () => {
    render(<ChatInterface />);

    expect(
      screen.getByRole("textbox", { name: /chat input/i }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("button", { name: /send message/i }),
    ).not.toBeDisabled();
  });

  // ── TC-Stop: Ghost placeholder removed after Stop; stopped message shown ──

  test("TC-Stop: ghost placeholder removed and stopped message visible after Stop", async () => {
    let resolve!: () => void;
    const blockingStream = (async function* () {
      yield "partial";
      await new Promise<void>((r) => (resolve = r));
    })();
    mockStreamChatCompletion.mockReturnValue(blockingStream);

    render(<ChatInterface />);

    fireEvent.change(screen.getByRole("textbox", { name: /chat input/i }), {
      target: { value: "test abort" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    // Wait for ThinkingBlock stop button to appear (title="Stop generating")
    const stopBtn = await waitFor(() =>
      screen.getByRole("button", { name: /stop generating/i }),
    );

    fireEvent.click(stopBtn);

    // Stopped message should appear
    await waitFor(() =>
      expect(
        screen.getByText("Generation was stopped by the user."),
      ).toBeInTheDocument(),
    );

    // Ghost placeholder (empty assistant bubble) should NOT be in the DOM
    const allParagraphs = document.querySelectorAll("p");
    const emptyBubble = Array.from(allParagraphs).find(
      (p) =>
        p.textContent === "" && p.classList.contains("whitespace-pre-wrap"),
    );
    expect(emptyBubble).toBeUndefined();

    // Unblock the stream generator so it can GC
    await act(async () => {
      resolve();
    });
  });

  // ── TC-MarkRead-1: useMarkRead receives sessionId + populated ref after assistant message ──

  test("TC-MarkRead-1: useMarkRead called with sessionId and populated ref once assistant message renders", async () => {
    mockStreamChatCompletion.mockReturnValue(makeStream(["Hello"]));

    render(<ChatInterface sessionId="sess_123" />);

    // On first render: sessionId is passed but no non-intro assistant message yet
    expect(mockUseMarkRead).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: "sess_123" }),
    );

    // Send a message so we get a real assistant reply
    fireEvent.change(screen.getByRole("textbox", { name: /chat input/i }), {
      target: { value: "Hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    // Wait for the streamed reply to render
    await waitFor(() => expect(screen.getByText("Hello")).toBeInTheDocument());

    // The latest-assistant-message element should exist in the DOM
    const latestEl = screen.getByTestId("latest-assistant-message");
    expect(latestEl).toBeInTheDocument();

    // The most recent call to useMarkRead should have the ref wired to that element
    const lastCallArgs =
      mockUseMarkRead.mock.calls[mockUseMarkRead.mock.calls.length - 1][0];
    expect(lastCallArgs.sessionId).toBe("sess_123");
    expect(lastCallArgs.latestMessageRef.current).toBe(latestEl);
  });

  // ── TC-MarkRead-2: sessionId undefined → hook receives null ─────────────

  test("TC-MarkRead-2: useMarkRead called with sessionId: null when sessionId prop is undefined", () => {
    render(<ChatInterface />);

    expect(mockUseMarkRead).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: null }),
    );
  });

  // ── TC-4: Text-size CustomEvent re-renders messages at new size ──────────

  test("TC-4: kene-chat-text-size-change event changes message text size", async () => {
    mockStreamChatCompletion.mockReturnValue(makeStream(["Hello"]));

    render(<ChatInterface />);

    // Default size: intro message uses text-base
    const introMsg = screen.getByText(/I'm your KEN-E AI assistant/i);
    expect(introMsg.className).toContain("text-base");

    // Dispatch the text-size change event
    act(() => {
      window.dispatchEvent(
        new CustomEvent("kene-chat-text-size-change", { detail: "large" }),
      );
    });

    // Messages now use text-lg
    await waitFor(() => expect(introMsg.className).toContain("text-lg"));

    // Switch to small
    act(() => {
      window.dispatchEvent(
        new CustomEvent("kene-chat-text-size-change", { detail: "small" }),
      );
    });

    await waitFor(() => expect(introMsg.className).toContain("text-sm"));
  });
});

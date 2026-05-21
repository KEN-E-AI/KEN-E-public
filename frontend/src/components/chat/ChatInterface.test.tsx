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

import { streamChatCompletion } from "@/lib/chatApi";
import { useOrgStatus } from "@/hooks/useOrgStatus";

const mockStreamChatCompletion = vi.mocked(streamChatCompletion);
const mockUseOrgStatus = vi.mocked(useOrgStatus);

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

import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatInterface } from "./ChatInterface";

describe("ChatInterface (stub)", () => {
  test("renders compact mode without throwing", () => {
    render(<ChatInterface compact />);

    expect(screen.getByTestId("chat-interface")).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /chat input \(disabled in stub\)/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /send message/i }),
    ).toBeDisabled();
  });

  test("renders the figma intro greeting in the message area", () => {
    render(<ChatInterface />);

    expect(screen.getByText(/I'm your KEN-E AI assistant/i)).toBeInTheDocument();
  });
});

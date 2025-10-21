import { describe, test, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MessageContent } from "./MessageContent";

describe("MessageContent", () => {
  describe("parseMessageContent", () => {
    test("renders plain text without JSON", () => {
      const plainText = "This is a simple message with no JSON data";
      render(<MessageContent content={plainText} />);

      expect(screen.getByText(plainText)).toBeInTheDocument();
      expect(screen.queryByText("Details")).not.toBeInTheDocument();
    });

    test("extracts and hides function_call JSON data", () => {
      const jsonData = "{'function_call': {'name': 'test', 'arguments': '{}'}}";
      const textPart = "Here is the actual response text";
      const content = jsonData + textPart;

      render(<MessageContent content={content} />);

      expect(screen.getByText(textPart)).toBeInTheDocument();
      expect(screen.getByText("Function Call")).toBeInTheDocument();
      expect(screen.queryByText(jsonData)).not.toBeInTheDocument();
    });

    test("extracts and hides function_response JSON data", () => {
      const jsonData = "{'function_response': {'result': 'success'}}";
      const textPart = "Operation completed successfully";
      const content = jsonData + textPart;

      render(<MessageContent content={content} />);

      expect(screen.getByText(textPart)).toBeInTheDocument();
      expect(screen.getByText("Function Response")).toBeInTheDocument();
    });

    test("handles multiple consecutive JSON objects", () => {
      const json1 = "{'function_call': {'name': 'func1'}}";
      const json2 = "{'function_response': {'status': 'ok'}}";
      const textPart = "Final response text";
      const content = json1 + json2 + textPart;

      render(<MessageContent content={content} />);

      expect(screen.getByText(textPart)).toBeInTheDocument();
      expect(screen.getByText("Details")).toBeInTheDocument();
    });

    test("shows 'Response received' when only JSON and no text", () => {
      const content = "{'function_call': {'name': 'test'}}";

      render(<MessageContent content={content} />);

      expect(screen.getByText("Response received")).toBeInTheDocument();
      expect(screen.getByText("Function Call")).toBeInTheDocument();
    });

    test("expands and collapses JSON data on click", () => {
      const jsonData = "{'function_call': {'name': 'test', 'arguments': '{}'}}";
      const textPart = "Response text";
      const content = jsonData + textPart;

      const { container } = render(<MessageContent content={content} />);

      const button = screen.getByText("Function Call");

      // Initially collapsed - should not show raw JSON
      expect(container.querySelector("pre code")).not.toBeInTheDocument();

      // Click to expand
      fireEvent.click(button);

      // Should now show formatted JSON in code block
      const codeBlock = container.querySelector("pre code");
      expect(codeBlock).toBeInTheDocument();
      expect(codeBlock?.textContent).toContain("function_call");
      expect(codeBlock?.textContent).toContain("name");
      expect(codeBlock?.textContent).toContain("test");

      // Click to collapse
      fireEvent.click(button);

      // Should be hidden again
      expect(container.querySelector("pre code")).not.toBeInTheDocument();
    });

    test("renders markdown content with tables", () => {
      const markdownContent = `
# Header

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |

**Bold text** and *italic text*
`;

      render(<MessageContent content={markdownContent} />);

      // Check for rendered markdown elements
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        "Header",
      );
      expect(screen.getByRole("table")).toBeInTheDocument();
      expect(screen.getByText("Column 1")).toBeInTheDocument();
      expect(screen.getByText("Value 1")).toBeInTheDocument();
      expect(screen.getByText("Bold text")).toBeInTheDocument();
      expect(screen.getByText("italic text")).toBeInTheDocument();
    });

    test("applies assistant-specific styling when isAssistant is true", () => {
      const content = "Assistant message";

      const { container } = render(
        <MessageContent content={content} isAssistant={true} />,
      );

      // Check for prose-invert class which is applied for assistant messages
      const proseElement = container.querySelector(".prose-invert");
      expect(proseElement).toBeInTheDocument();
    });

    test("handles malformed JSON gracefully", () => {
      const content = "{'invalid': json'}} Some text after";

      render(<MessageContent content={content} />);

      // Should render the entire content as text when JSON parsing fails
      expect(screen.getByText(content)).toBeInTheDocument();
      expect(screen.queryByText("Details")).not.toBeInTheDocument();
    });

    test("handles JSON in code blocks", () => {
      const content = `
Here is some text

\`\`\`json
{
  "function_call": {
    "name": "test_function",
    "arguments": {}
  }
}
\`\`\`

More text after
`;

      render(<MessageContent content={content} />);

      // Should extract the JSON and show it in a pill
      expect(screen.getByText("Function Call")).toBeInTheDocument();
      // Text parts should be visible
      expect(screen.getByText(/Here is some text/)).toBeInTheDocument();
      expect(screen.getByText(/More text after/)).toBeInTheDocument();
    });
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { Textarea } from "@/components/ui/textarea";

describe("Textarea", () => {
  it("renders a textarea element", () => {
    render(<Textarea />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("textbox").tagName).toBe("TEXTAREA");
  });

  it("has data-slot='textarea' on the element", () => {
    render(<Textarea />);
    expect(screen.getByRole("textbox")).toHaveAttribute(
      "data-slot",
      "textarea",
    );
  });

  it("forwards the placeholder prop", () => {
    render(<Textarea placeholder="Write something..." />);
    expect(
      screen.getByPlaceholderText("Write something..."),
    ).toBeInTheDocument();
  });

  it("renders aria-invalid='true' when passed", () => {
    render(<Textarea aria-invalid="true" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("forwards the disabled attribute", () => {
    render(<Textarea disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("forwards the rows prop", () => {
    render(<Textarea rows={8} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "8");
  });

  it("forwards ref to the textarea DOM node", () => {
    const ref = createRef<HTMLTextAreaElement>();
    render(<Textarea ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement);
    expect(ref.current).toBe(screen.getByRole("textbox"));
  });
});

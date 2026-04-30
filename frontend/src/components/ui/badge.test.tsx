import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it.each([
    "default",
    "secondary",
    "destructive",
    "outline",
    "success",
    "error",
    "warning",
    "info",
    "disconnected",
    "neutral",
  ] as const)("renders variant '%s' without error", (variant) => {
    render(<Badge variant={variant}>Label</Badge>);
    expect(screen.getByText("Label")).toBeInTheDocument();
  });

  it("renders children text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("has data-slot='badge' on the root element", () => {
    const { container } = render(<Badge>Slotted</Badge>);
    expect(container.firstChild).toHaveAttribute("data-slot", "badge");
  });

  it("merges custom className onto the element", () => {
    const { container } = render(
      <Badge className="my-custom-class">Styled</Badge>,
    );
    expect(container.firstChild).toHaveClass("my-custom-class");
  });

  it("forwards ref to the DOM node", () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(<Badge ref={ref}>Ref</Badge>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
    expect(ref.current).toBe(container.firstChild);
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it.each([
    "default",
    "gradient",
    "destructive",
    "outline",
    "secondary",
    "ghost",
    "link",
  ] as const)("renders variant '%s' without error", (variant) => {
    render(<Button variant={variant}>Label</Button>);
    expect(screen.getByRole("button", { name: "Label" })).toBeInTheDocument();
  });

  it.each(["default", "sm", "lg", "icon"] as const)(
    "renders size '%s' without error",
    (size) => {
      render(<Button size={size}>Label</Button>);
      expect(screen.getByRole("button", { name: "Label" })).toBeInTheDocument();
    },
  );

  it("renders child element when asChild is true", () => {
    render(
      <Button asChild>
        <a href="/home">Home</a>
      </Button>,
    );
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("has disabled attribute when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button", { name: "Disabled" })).toBeDisabled();
  });

  it("calls onClick when clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    await user.click(screen.getByRole("button", { name: "Click me" }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("has data-slot='button' on the root element", () => {
    render(<Button>Slotted</Button>);
    expect(screen.getByRole("button", { name: "Slotted" })).toHaveAttribute(
      "data-slot",
      "button",
    );
  });

  it("forwards ref to the DOM node", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    expect(ref.current).toBe(screen.getByRole("button", { name: "Ref" }));
  });
});

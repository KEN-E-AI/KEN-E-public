import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction,
} from "@/components/ui/card";

describe("Card", () => {
  it("renders with data-slot='card'", () => {
    const { container } = render(<Card />);
    expect(container.firstChild).toHaveAttribute("data-slot", "card");
  });

  it("sets borderLeftColor inline style when accentColor is provided", () => {
    const { container } = render(<Card accentColor="#ff0000" />);
    expect((container.firstChild as HTMLElement).style.borderLeftColor).toBe(
      "rgb(255, 0, 0)",
    );
  });

  it("does not set borderLeftColor inline style when accentColor is not provided", () => {
    const { container } = render(<Card />);
    expect(
      (container.firstChild as HTMLElement).style.borderLeftColor,
    ).toBeFalsy();
  });

  it("forwards ref to the DOM node", () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(<Card ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
    expect(ref.current).toBe(container.firstChild);
  });
});

describe("CardHeader", () => {
  it("renders with data-slot='card-header'", () => {
    const { container } = render(<CardHeader />);
    expect(container.firstChild).toHaveAttribute("data-slot", "card-header");
  });
});

describe("CardTitle", () => {
  it("renders with data-slot='card-title'", () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByText("Title")).toHaveAttribute(
      "data-slot",
      "card-title",
    );
  });

  it("renders as an h4 element", () => {
    render(<CardTitle>My Title</CardTitle>);
    expect(
      screen.getByRole("heading", { level: 4, name: "My Title" }),
    ).toBeInTheDocument();
  });
});

describe("CardDescription", () => {
  it("renders with data-slot='card-description'", () => {
    render(<CardDescription>Desc</CardDescription>);
    expect(screen.getByText("Desc")).toHaveAttribute(
      "data-slot",
      "card-description",
    );
  });
});

describe("CardContent", () => {
  it("renders with data-slot='card-content'", () => {
    const { container } = render(<CardContent />);
    expect(container.firstChild).toHaveAttribute("data-slot", "card-content");
  });
});

describe("CardFooter", () => {
  it("renders with data-slot='card-footer'", () => {
    const { container } = render(<CardFooter />);
    expect(container.firstChild).toHaveAttribute("data-slot", "card-footer");
  });
});

describe("CardAction", () => {
  it("renders with data-slot='card-action'", () => {
    const { container } = render(<CardAction />);
    expect(container.firstChild).toHaveAttribute("data-slot", "card-action");
  });
});

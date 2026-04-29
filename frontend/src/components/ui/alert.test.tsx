import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

describe("Alert", () => {
  it.each(["default", "destructive", "success", "warning", "info"] as const)(
    "renders variant '%s' without error",
    (variant) => {
      render(<Alert variant={variant}>Content</Alert>);
      expect(screen.getByRole("alert")).toBeInTheDocument();
    },
  );

  it("has role='alert' for accessibility", () => {
    render(<Alert>Something happened</Alert>);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("has data-slot='alert' on the root element", () => {
    render(<Alert>Slotted</Alert>);
    expect(screen.getByRole("alert")).toHaveAttribute("data-slot", "alert");
  });

  it("forwards ref to the DOM node", () => {
    const ref = createRef<HTMLDivElement>();
    render(<Alert ref={ref}>Ref</Alert>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
    expect(ref.current).toBe(screen.getByRole("alert"));
  });
});

describe("AlertTitle", () => {
  it("renders with data-slot='alert-title'", () => {
    render(
      <Alert>
        <AlertTitle>Title text</AlertTitle>
      </Alert>,
    );
    expect(screen.getByText("Title text")).toHaveAttribute(
      "data-slot",
      "alert-title",
    );
  });
});

describe("AlertDescription", () => {
  it("renders with data-slot='alert-description'", () => {
    render(
      <Alert>
        <AlertDescription>Description text</AlertDescription>
      </Alert>,
    );
    expect(screen.getByText("Description text")).toHaveAttribute(
      "data-slot",
      "alert-description",
    );
  });
});

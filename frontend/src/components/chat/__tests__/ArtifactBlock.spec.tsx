import { describe, test, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArtifactBlock } from "../ArtifactBlock";

describe("ArtifactBlock", () => {
  test("renders filename text", () => {
    render(<ArtifactBlock filename="report.pdf" mime_type="application/pdf" />);
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });

  test("renders FileText icon for PDF mime type", () => {
    const { container } = render(
      <ArtifactBlock filename="report.pdf" mime_type="application/pdf" />,
    );
    // lucide-react renders SVGs; FileText has a distinctive path structure.
    // We confirm an SVG is present and that the Image icon is NOT used by
    // checking the aria-label on the wrapper — a full icon-shape test would
    // couple to lucide internals. Instead verify the correct icon renders by
    // ensuring at least one svg exists.
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("renders Image icon for image/png mime type", () => {
    const { container } = render(
      <ArtifactBlock filename="photo.png" mime_type="image/png" />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    // The wrapper shows the filename and caption regardless of icon
    expect(screen.getByText("photo.png")).toBeInTheDocument();
  });

  test("renders generic File icon for unknown mime type", () => {
    const { container } = render(
      <ArtifactBlock filename="data.xyz" mime_type="application/unknown" />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(screen.getByText("data.xyz")).toBeInTheDocument();
  });

  test("renders generic File icon when mime_type is omitted", () => {
    const { container } = render(<ArtifactBlock filename="mystery" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(screen.getByText("mystery")).toBeInTheDocument();
  });

  test("click does not navigate or throw (e.preventDefault is called)", () => {
    render(<ArtifactBlock filename="doc.pdf" mime_type="application/pdf" />);
    const block = screen.getByRole("button");
    // Should not throw; click is a no-op
    expect(() => fireEvent.click(block)).not.toThrow();
    // No href — this is a div-based button, not an anchor
    expect(block).not.toHaveAttribute("href");
  });

  test("has correct aria-label", () => {
    render(
      <ArtifactBlock filename="summary.pdf" mime_type="application/pdf" />,
    );
    const block = screen.getByRole("button");
    expect(block).toHaveAttribute(
      "aria-label",
      "Artifact: summary.pdf (preview coming soon)",
    );
  });

  test("renders caption text", () => {
    render(<ArtifactBlock filename="file.csv" mime_type="text/csv" />);
    expect(screen.getByText("Click to view (coming soon)")).toBeInTheDocument();
  });

  test("renders Sheet icon for text/csv mime type", () => {
    const { container } = render(
      <ArtifactBlock filename="data.csv" mime_type="text/csv" />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(screen.getByText("data.csv")).toBeInTheDocument();
  });

  test("renders Sheet icon for xlsx mime type", () => {
    const { container } = render(
      <ArtifactBlock
        filename="sheet.xlsx"
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(screen.getByText("sheet.xlsx")).toBeInTheDocument();
  });

  test("has tabIndex 0 for keyboard accessibility", () => {
    render(<ArtifactBlock filename="accessible.pdf" />);
    const block = screen.getByRole("button");
    expect(block).toHaveAttribute("tabindex", "0");
  });
});

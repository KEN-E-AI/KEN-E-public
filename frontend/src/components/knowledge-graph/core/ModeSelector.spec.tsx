import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ModeSelector } from "./ModeSelector";

describe("ModeSelector", () => {
  const mockModes = [
    { value: "strengths", label: "Strengths" },
    { value: "weaknesses", label: "Weaknesses" },
    { value: "tactics", label: "Tactics" },
  ];

  it("should render all mode options", () => {
    render(
      <ModeSelector modes={mockModes} value="strengths" onChange={vi.fn()} />,
    );

    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.getByText("Weaknesses")).toBeInTheDocument();
    expect(screen.getByText("Tactics")).toBeInTheDocument();
  });

  it("should highlight selected mode", () => {
    render(
      <ModeSelector modes={mockModes} value="weaknesses" onChange={vi.fn()} />,
    );

    const weaknessesButton = screen.getByText("Weaknesses");
    expect(weaknessesButton.closest("button")).toHaveAttribute(
      "data-state",
      "on",
    );
  });

  it("should call onChange when mode is clicked", () => {
    const handleChange = vi.fn();

    render(
      <ModeSelector
        modes={mockModes}
        value="strengths"
        onChange={handleChange}
      />,
    );

    fireEvent.click(screen.getByText("Weaknesses"));

    expect(handleChange).toHaveBeenCalledWith("weaknesses");
    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  it("should support custom mode values", () => {
    const customModes = [
      { value: "custom1", label: "Custom One" },
      { value: "custom2", label: "Custom Two" },
    ];

    const handleChange = vi.fn();

    render(
      <ModeSelector
        modes={customModes}
        value="custom1"
        onChange={handleChange}
      />,
    );

    expect(screen.getByText("Custom One")).toBeInTheDocument();
    expect(screen.getByText("Custom Two")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Custom Two"));

    expect(handleChange).toHaveBeenCalledWith("custom2");
  });

  it("should render single mode", () => {
    const singleMode = [{ value: "only", label: "Only Option" }];

    render(<ModeSelector modes={singleMode} value="only" onChange={vi.fn()} />);

    expect(screen.getByText("Only Option")).toBeInTheDocument();
  });
});

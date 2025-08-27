import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  LoadingOverlay,
  type ProgressInfo,
  type ProgressStep,
} from "./loading-overlay";

describe("LoadingOverlay", () => {
  test("renders nothing when not loading", () => {
    const { container } = render(
      <LoadingOverlay isLoading={false} message="Test message" />,
    );
    expect(container.firstChild).toBeNull();
  });

  test("renders loading message when loading", () => {
    render(<LoadingOverlay isLoading={true} message="Loading data..." />);
    expect(screen.getByText("Loading data...")).toBeInTheDocument();
  });

  test("renders sub-message when provided", () => {
    render(
      <LoadingOverlay
        isLoading={true}
        message="Main message"
        subMessage="Sub message"
      />,
    );
    expect(screen.getByText("Main message")).toBeInTheDocument();
    expect(screen.getByText("Sub message")).toBeInTheDocument();
  });

  test("renders progress bar when progress is provided", () => {
    const progress: ProgressInfo = {
      percentage: 60,
      currentStep: 3,
      totalSteps: 5,
    };

    render(
      <LoadingOverlay
        isLoading={true}
        message="Processing..."
        progress={progress}
      />,
    );

    expect(screen.getByText("Processing...")).toBeInTheDocument();
    expect(screen.getByText("Step 3 of 5")).toBeInTheDocument();
  });

  test("renders progress steps when provided", () => {
    const steps: ProgressStep[] = [
      { name: "Creating account", status: "completed" },
      { name: "Setting up database", status: "processing" },
      { name: "Generating strategy", status: "pending" },
    ];

    const progress: ProgressInfo = {
      percentage: 40,
      currentStep: 2,
      totalSteps: 3,
      steps,
    };

    render(
      <LoadingOverlay
        isLoading={true}
        message="Processing..."
        progress={progress}
      />,
    );

    expect(screen.getByText("Creating account")).toBeInTheDocument();
    expect(screen.getByText("Setting up database")).toBeInTheDocument();
    expect(screen.getByText("Generating strategy")).toBeInTheDocument();
  });

  test("applies correct styles for different step statuses", () => {
    const steps: ProgressStep[] = [
      { name: "Completed step", status: "completed" },
      { name: "Processing step", status: "processing" },
      { name: "Pending step", status: "pending" },
    ];

    const progress: ProgressInfo = {
      percentage: 50,
      currentStep: 2,
      totalSteps: 3,
      steps,
    };

    const { container } = render(
      <LoadingOverlay isLoading={true} message="Test" progress={progress} />,
    );

    // Check that different status icons are rendered
    const completedIcon = container.querySelector(".text-green-500");
    const processingIcon = container.querySelector(".animate-spin");
    const pendingIcon = container.querySelector(".text-muted-foreground");

    expect(completedIcon).toBeTruthy();
    expect(processingIcon).toBeTruthy();
    expect(pendingIcon).toBeTruthy();
  });

  test("applies fullscreen variant when specified", () => {
    const { container } = render(
      <LoadingOverlay
        isLoading={true}
        message="Fullscreen loading"
        variant="fullscreen"
      />,
    );

    const overlay = container.querySelector(".fixed");
    expect(overlay).toBeTruthy();
  });

  test("applies local variant by default", () => {
    const { container } = render(
      <LoadingOverlay isLoading={true} message="Local loading" />,
    );

    const overlay = container.querySelector(".absolute");
    const fixedOverlay = container.querySelector(".fixed");

    expect(overlay).toBeTruthy();
    expect(fixedOverlay).toBeFalsy();
  });

  test("sets correct aria attributes", () => {
    render(
      <LoadingOverlay isLoading={true} message="Accessible loading message" />,
    );

    const overlay = screen.getByLabelText("Accessible loading message");
    expect(overlay).toHaveAttribute("aria-busy", "true");
  });
});

import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  UnsavedChangesIndicator,
  AutoSaveIndicator,
  FormStateIndicator,
} from "./UnsavedChangesIndicator";

describe("UnsavedChangesIndicator", () => {
  test("renders saved state correctly", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={false}
        lastSaved="2 minutes ago"
      />,
    );

    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    // Note: lastSaved is not shown in badge variant, only in card variant
  });

  test("renders unsaved changes state correctly", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        lastSaved="5 minutes ago"
      />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    // Note: lastSaved is not shown in badge variant, only in card variant
  });

  test("renders loading state correctly", () => {
    render(
      <UnsavedChangesIndicator hasUnsavedChanges={true} isLoading={true} />,
    );

    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });

  test("shows save and reset buttons when unsaved changes exist", () => {
    const onSave = vi.fn();
    const onReset = vi.fn();

    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        onSave={onSave}
        onReset={onReset}
      />,
    );

    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Reset")).toBeInTheDocument();
  });

  test("calls onSave when save button is clicked", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();

    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        onSave={onSave}
      />,
    );

    const saveButton = screen.getByText("Save");
    await user.click(saveButton);

    expect(onSave).toHaveBeenCalledTimes(1);
  });

  test("calls onReset when reset button is clicked", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();

    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        onReset={onReset}
      />,
    );

    const resetButton = screen.getByText("Reset");
    await user.click(resetButton);

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  test("disables save button when saveDisabled is true", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        saveDisabled={true}
        onSave={vi.fn()}
      />,
    );

    const saveButton = screen.getByText("Save");
    expect(saveButton).toBeDisabled();
  });

  test("disables buttons when loading", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        isLoading={true}
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    const saveButton = screen.getByText("Save");
    const resetButton = screen.getByText("Reset");

    expect(saveButton).toBeDisabled();
    expect(resetButton).toBeDisabled();
  });

  test("renders badge variant correctly", () => {
    render(
      <UnsavedChangesIndicator hasUnsavedChanges={true} variant="badge" />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  test("renders alert variant correctly", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Reset")).toBeInTheDocument();
  });

  test("does not render alert variant when no unsaved changes", () => {
    const { container } = render(
      <UnsavedChangesIndicator hasUnsavedChanges={false} variant="alert" />,
    );

    expect(container.firstChild).toBeNull();
  });

  test("renders card variant correctly", () => {
    render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="card"
        lastSaved="1 hour ago"
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(screen.getByText("Last saved: 1 hour ago")).toBeInTheDocument();
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
    expect(screen.getByText("Reset")).toBeInTheDocument();
  });

  test("handles different sizes correctly", () => {
    const { rerender } = render(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        size="sm"
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("Save")).toBeInTheDocument();

    rerender(
      <UnsavedChangesIndicator
        hasUnsavedChanges={true}
        variant="alert"
        size="lg"
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("Save")).toBeInTheDocument();
  });
});

describe("AutoSaveIndicator", () => {
  test("renders auto-saving state correctly", () => {
    render(<AutoSaveIndicator isAutoSaving={true} lastAutoSaved="just now" />);

    expect(screen.getByText("Auto-saving...")).toBeInTheDocument();
  });

  test("renders auto-saved state correctly", () => {
    render(
      <AutoSaveIndicator isAutoSaving={false} lastAutoSaved="2 minutes ago" />,
    );

    expect(screen.getByText("Auto-saved")).toBeInTheDocument();
    expect(screen.getByText("2 minutes ago")).toBeInTheDocument();
  });

  test("shows enable/disable toggle when provided", () => {
    const onToggle = vi.fn();

    render(
      <AutoSaveIndicator
        isAutoSaving={false}
        autoSaveEnabled={true}
        onToggleAutoSave={onToggle}
      />,
    );

    expect(screen.getByText("Disable Auto-save")).toBeInTheDocument();
  });

  test("shows enable button when auto-save is disabled", () => {
    const onToggle = vi.fn();

    render(
      <AutoSaveIndicator
        isAutoSaving={false}
        autoSaveEnabled={false}
        onToggleAutoSave={onToggle}
      />,
    );

    expect(screen.getByText("Enable Auto-save")).toBeInTheDocument();
  });

  test("calls onToggleAutoSave when toggle button is clicked", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    render(
      <AutoSaveIndicator
        isAutoSaving={false}
        autoSaveEnabled={true}
        onToggleAutoSave={onToggle}
      />,
    );

    const toggleButton = screen.getByText("Disable Auto-save");
    await user.click(toggleButton);

    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

describe("FormStateIndicator", () => {
  test("renders saved state correctly", () => {
    render(
      <FormStateIndicator
        isDirty={false}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
        lastSaved="1 minute ago"
      />,
    );

    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    expect(screen.getByText("• Last saved: 1 minute ago")).toBeInTheDocument();
  });

  test("renders submitting state correctly", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={true}
        hasErrors={false}
      />,
    );

    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });

  test("renders error state correctly", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={false}
        isSubmitting={false}
        hasErrors={true}
      />,
    );

    expect(screen.getByText("Has errors")).toBeInTheDocument();
  });

  test("renders dirty state correctly", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
      />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  test("shows save and reset buttons when dirty or has errors", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Reset")).toBeInTheDocument();
  });

  test("disables save button when form is invalid", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={false}
        isSubmitting={false}
        hasErrors={true}
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    const saveButton = screen.getByText("Save");
    expect(saveButton).toBeDisabled();
  });

  test("disables buttons when submitting", () => {
    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={true}
        hasErrors={false}
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    const saveButton = screen.getByText("Save");
    const resetButton = screen.getByText("Reset");

    expect(saveButton).toBeDisabled();
    expect(resetButton).toBeDisabled();
  });

  test("calls onSave when save button is clicked", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();

    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
        onSave={onSave}
      />,
    );

    const saveButton = screen.getByText("Save");
    await user.click(saveButton);

    expect(onSave).toHaveBeenCalledTimes(1);
  });

  test("calls onReset when reset button is clicked", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();

    render(
      <FormStateIndicator
        isDirty={true}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
        onReset={onReset}
      />,
    );

    const resetButton = screen.getByText("Reset");
    await user.click(resetButton);

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  test("does not show buttons when form is clean and has no errors", () => {
    render(
      <FormStateIndicator
        isDirty={false}
        isValid={true}
        isSubmitting={false}
        hasErrors={false}
        onSave={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.queryByText("Save")).not.toBeInTheDocument();
    expect(screen.queryByText("Reset")).not.toBeInTheDocument();
  });
});

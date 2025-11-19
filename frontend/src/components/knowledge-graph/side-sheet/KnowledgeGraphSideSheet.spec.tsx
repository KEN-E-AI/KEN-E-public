import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Package } from "lucide-react";
import { KnowledgeGraphSideSheet } from "./KnowledgeGraphSideSheet";

describe("KnowledgeGraphSideSheet", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    title: "Test Sheet",
    icon: Package,
    isEditing: false,
    onEdit: vi.fn(),
    onSave: vi.fn(),
    onCancel: vi.fn(),
    onDelete: vi.fn(),
    hasEditAccess: true,
    children: <div>Sheet Content</div>,
  };

  it("should render in view mode by default", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} />);

    expect(screen.getByText("Test Sheet")).toBeInTheDocument();
    expect(screen.getByText("Sheet Content")).toBeInTheDocument();
    expect(screen.getByLabelText(/edit/i)).toBeInTheDocument();
  });

  it("should show edit button when hasEditAccess is true", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} />);

    expect(screen.getByLabelText(/edit/i)).toBeInTheDocument();
  });

  it("should hide edit button when hasEditAccess is false", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} hasEditAccess={false} />);

    expect(screen.queryByLabelText(/edit/i)).not.toBeInTheDocument();
  });

  it("should switch to edit mode when edit button clicked", () => {
    const handleEdit = vi.fn();

    render(<KnowledgeGraphSideSheet {...defaultProps} onEdit={handleEdit} />);

    fireEvent.click(screen.getByLabelText(/edit/i));

    expect(handleEdit).toHaveBeenCalledTimes(1);
  });

  it("should show save and cancel buttons in edit mode", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} isEditing={true} />);

    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("should call onSave when save button clicked", () => {
    const handleSave = vi.fn();

    render(
      <KnowledgeGraphSideSheet
        {...defaultProps}
        isEditing={true}
        onSave={handleSave}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    expect(handleSave).toHaveBeenCalledTimes(1);
  });

  it("should call onCancel when cancel button clicked", () => {
    const handleCancel = vi.fn();

    render(
      <KnowledgeGraphSideSheet
        {...defaultProps}
        isEditing={true}
        onCancel={handleCancel}
      />,
    );

    fireEvent.click(screen.getByText("Cancel"));

    expect(handleCancel).toHaveBeenCalledTimes(1);
  });

  it("should show delete button in view mode", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} />);

    expect(screen.getByLabelText(/delete/i)).toBeInTheDocument();
  });

  it("should call onDelete when delete button clicked", () => {
    const handleDelete = vi.fn();

    render(
      <KnowledgeGraphSideSheet {...defaultProps} onDelete={handleDelete} />,
    );

    fireEvent.click(screen.getByLabelText(/delete/i));

    expect(handleDelete).toHaveBeenCalledTimes(1);
  });

  it("should display correct title", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} title="Custom Title" />);

    expect(screen.getByText("Custom Title")).toBeInTheDocument();
  });

  it("should not render when open is false", () => {
    render(<KnowledgeGraphSideSheet {...defaultProps} open={false} />);

    expect(screen.queryByText("Test Sheet")).not.toBeInTheDocument();
  });
});

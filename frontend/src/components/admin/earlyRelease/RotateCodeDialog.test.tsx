import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RotateCodeDialog } from "./RotateCodeDialog";

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  onRotate: vi.fn(),
  isPending: false,
  serverError: null,
};

function renderDialog(props = {}) {
  return render(<RotateCodeDialog {...defaultProps} {...props} />);
}

describe("RotateCodeDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dialog when open", () => {
    renderDialog();
    expect(screen.getByText("Set / Rotate Code")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /rotate code/i }),
    ).toBeInTheDocument();
  });

  it("submit button is disabled when code input is empty", () => {
    renderDialog();
    const submitBtn = screen.getByRole("button", { name: /rotate code/i });
    expect(submitBtn).toBeDisabled();
  });

  it("submit button is disabled when isPending is true", async () => {
    renderDialog({ isPending: true });
    const submitBtn = screen.getByRole("button", { name: /rotating…/i });
    expect(submitBtn).toBeDisabled();
  });

  it("shows 'Code is required.' when the form is submitted with a blank code", async () => {
    const onRotate = vi.fn();
    const user = userEvent.setup();
    renderDialog({ onRotate });

    const input = screen.getByRole("textbox", { name: /new code/i });
    await user.type(input, "   "); // whitespace only → trims to empty

    // The submit button is disabled for blank input, so submit the form
    // directly to exercise the handleSubmit "Code is required." branch.
    const form = input.closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(screen.getByText(/code is required/i)).toBeInTheDocument();
    expect(onRotate).not.toHaveBeenCalled();
  });

  it("calls onRotate with code when submitted with valid code", async () => {
    const onRotate = vi.fn();
    const user = userEvent.setup();
    renderDialog({ onRotate });

    const input = screen.getByRole("textbox", { name: /new code/i });
    await user.type(input, "LAUNCH2025");

    const submitBtn = screen.getByRole("button", { name: /rotate code/i });
    await user.click(submitBtn);

    expect(onRotate).toHaveBeenCalledWith(
      expect.objectContaining({ code: "LAUNCH2025" }),
    );
  });

  it("includes is_active=false when 'disable immediately' checkbox is checked", async () => {
    const onRotate = vi.fn();
    const user = userEvent.setup();
    renderDialog({ onRotate });

    const input = screen.getByRole("textbox", { name: /new code/i });
    await user.type(input, "MYCODE");

    const checkbox = screen.getByRole("checkbox", {
      name: /disable code immediately/i,
    });
    await user.click(checkbox);

    await user.click(screen.getByRole("button", { name: /rotate code/i }));

    expect(onRotate).toHaveBeenCalledWith(
      expect.objectContaining({ code: "MYCODE", is_active: false }),
    );
  });

  it("does not include is_active when checkbox is unchecked", async () => {
    const onRotate = vi.fn();
    const user = userEvent.setup();
    renderDialog({ onRotate });

    const input = screen.getByRole("textbox", { name: /new code/i });
    await user.type(input, "MYCODE");

    await user.click(screen.getByRole("button", { name: /rotate code/i }));

    expect(onRotate).toHaveBeenCalledWith(
      expect.not.objectContaining({ is_active: false }),
    );
  });

  it("displays a server error when provided", () => {
    renderDialog({ serverError: "Code already in use" });
    expect(screen.getByText("Code already in use")).toBeInTheDocument();
  });

  it("calls onOpenChange with false when Cancel is clicked", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    renderDialog({ onOpenChange });

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

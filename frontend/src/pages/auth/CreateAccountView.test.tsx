import { describe, test, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CreateAccountView } from "./CreateAccountView";

const baseProps = {
  name: "",
  email: "",
  password: "",
  confirmPassword: "",
  agreedToTerms: false,
  isLoading: false,
  errorMessage: "",
  fieldErrors: {},
  invitationToken: null,
  invitationData: null,
  invitationError: null,
  onNameChange: vi.fn(),
  onEmailChange: vi.fn(),
  onPasswordChange: vi.fn(),
  onConfirmPasswordChange: vi.fn(),
  onAgreedToTermsChange: vi.fn(),
  onSubmit: vi.fn(),
  onGoogleSignUp: vi.fn(),
};

const renderView = (props = {}) =>
  render(
    <MemoryRouter>
      <CreateAccountView {...baseProps} {...props} />
    </MemoryRouter>,
  );

describe("CreateAccountView", () => {
  describe("without requiresAccessCode (default / flag-OFF)", () => {
    test("does not render the early-access banner or code field", () => {
      renderView();
      expect(
        screen.queryByTestId("early-access-banner"),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("access-code-field")).not.toBeInTheDocument();
      expect(
        screen.queryByLabelText(/early release code/i),
      ).not.toBeInTheDocument();
    });

    test("submit button is enabled when not loading", () => {
      renderView();
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).not.toBeDisabled();
    });

    test("standard form fields are present", () => {
      renderView();
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    });
  });

  describe("with requiresAccessCode={true}", () => {
    test("renders the early-access banner", () => {
      renderView({ requiresAccessCode: true });
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument();
      expect(screen.getByText(/early access required/i)).toBeInTheDocument();
    });

    test("renders the code input field", () => {
      renderView({ requiresAccessCode: true });
      expect(screen.getByLabelText(/early release code/i)).toBeInTheDocument();
      expect(screen.getByTestId("access-code-field")).toBeInTheDocument();
    });

    test("submit button is disabled when accessCodeStatus is idle", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "idle" });
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeDisabled();
    });

    test("submit button is disabled when accessCodeStatus is validating", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "validating" });
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeDisabled();
    });

    test("submit button is disabled when accessCodeStatus is invalid", () => {
      renderView({
        requiresAccessCode: true,
        accessCodeStatus: "invalid",
        accessCodeError: "Invalid Early Release code",
      });
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeDisabled();
    });

    test("submit button is enabled when accessCodeStatus is valid", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "valid" });
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).not.toBeDisabled();
    });

    test("Google button is disabled when accessCodeStatus is not valid", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "idle" });
      expect(screen.getByRole("button", { name: /google/i })).toBeDisabled();
    });

    test("Google button is enabled when accessCodeStatus is valid", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "valid" });
      expect(
        screen.getByRole("button", { name: /google/i }),
      ).not.toBeDisabled();
    });

    test("shows Validating… hint while accessCodeStatus is validating", () => {
      renderView({ requiresAccessCode: true, accessCodeStatus: "validating" });
      expect(screen.getByText(/validating…/i)).toBeInTheDocument();
    });

    test("shows inline error when accessCodeStatus is invalid", () => {
      renderView({
        requiresAccessCode: true,
        accessCodeStatus: "invalid",
        accessCodeError: "Invalid Early Release code",
      });
      expect(
        screen.getByText(/invalid early release code/i),
      ).toBeInTheDocument();
    });

    test("shows green check icon when accessCodeStatus is valid", () => {
      const { container } = renderView({
        requiresAccessCode: true,
        accessCodeStatus: "valid",
        accessCode: "VALID-CODE",
      });
      const codeField = container.querySelector(
        '[data-testid="access-code-field"]',
      );
      expect(codeField).not.toBeNull();
      const svgIcons = codeField!.querySelectorAll("svg");
      expect(svgIcons.length).toBeGreaterThan(0);
    });

    test("calls onAccessCodeChange when typing in the code field", () => {
      const onAccessCodeChange = vi.fn();
      renderView({
        requiresAccessCode: true,
        onAccessCodeChange,
      });
      const input = screen.getByLabelText(/early release code/i);
      fireEvent.change(input, { target: { value: "TEST" } });
      expect(onAccessCodeChange).toHaveBeenCalledWith("TEST");
    });

    test("calls onAccessCodeBlur when the code field loses focus", () => {
      const onAccessCodeBlur = vi.fn();
      renderView({
        requiresAccessCode: true,
        onAccessCodeBlur,
      });
      const input = screen.getByLabelText(/early release code/i);
      fireEvent.blur(input);
      expect(onAccessCodeBlur).toHaveBeenCalled();
    });
  });

  describe("invitation banner (unchanged)", () => {
    test("renders invitation banner when invitationData is present", () => {
      renderView({
        invitationToken: "tok-123",
        invitationData: {
          organization_name: "Acme Corp",
          access_level: "admin",
        },
      });
      expect(screen.getByText(/you've been invited!/i)).toBeInTheDocument();
      expect(screen.getByText(/acme corp/i)).toBeInTheDocument();
    });

    test("does not render invitation banner when invitationData is null", () => {
      renderView({ invitationToken: "tok-123", invitationData: null });
      expect(
        screen.queryByText(/you've been invited!/i),
      ).not.toBeInTheDocument();
    });
  });
});

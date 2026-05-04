import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { vi } from "vitest";
import UserSettings from "./UserSettings";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext");
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));
vi.mock("axios", () => {
  const mockAxiosInstance = {
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn(),
  };
  return {
    default: {
      ...mockAxiosInstance,
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});
vi.mock("@/components/notifications/NotificationPreferences", () => ({
  NotificationPreferences: ({ onSave }: { onSave: () => void }) => (
    <div data-testid="notification-preferences">
      <button onClick={onSave}>Save Notifications</button>
    </div>
  ),
}));

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

const mockUser = {
  id: "user-123",
  email: "sarah@company.com",
  firstName: "Sarah",
  lastName: "Chen",
  jobTitle: "Marketing Director",
};

describe("UserSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockUseAuth.mockReturnValue({
      user: mockUser,
      updateUser: vi.fn(),
    });
  });

  const renderUserSettings = () =>
    render(
      <BrowserRouter>
        <UserSettings />
      </BrowserRouter>,
    );

  it("renders 4 tabs: Profile, Notifications, Security, Preferences", () => {
    renderUserSettings();

    expect(screen.getByRole("tab", { name: /Profile/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Notifications/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Security/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Preferences/i }),
    ).toBeInTheDocument();
  });

  it("shows profile form with user data in default Profile tab", () => {
    renderUserSettings();

    expect(screen.getByDisplayValue("Sarah")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Chen")).toBeInTheDocument();
    expect(screen.getByDisplayValue("sarah@company.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Marketing Director")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Save Changes/i }),
    ).toBeInTheDocument();
  });

  it("renders NotificationPreferences when Notifications tab is activated", async () => {
    renderUserSettings();

    const notificationsTab = screen.getByRole("tab", {
      name: /Notifications/i,
    });
    await userEvent.click(notificationsTab);

    expect(screen.getByTestId("notification-preferences")).toBeInTheDocument();
  });

  it("shows Chat Text Size combobox in Preferences tab", async () => {
    renderUserSettings();

    const preferencesTab = screen.getByRole("tab", { name: /Preferences/i });
    await userEvent.click(preferencesTab);

    expect(
      screen.getByRole("combobox", { name: /Chat Text Size/i }),
    ).toBeInTheDocument();
  });

  it("loads chat text size from localStorage on mount and shows it in Preferences tab", async () => {
    localStorage.setItem("kene-chat-text-size", "small");
    renderUserSettings();

    const preferencesTab = screen.getByRole("tab", { name: /Preferences/i });
    await userEvent.click(preferencesTab);

    await waitFor(() => {
      const trigger = screen.getByRole("combobox", { name: /Chat Text Size/i });
      expect(trigger).toHaveTextContent("Small");
    });
  });

  it("shows loading fallback when user is null", () => {
    mockUseAuth.mockReturnValue({ user: null, updateUser: vi.fn() });
    renderUserSettings();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

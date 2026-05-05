import { describe, test, expect, beforeEach, vi, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { AuthProvider, useAuth, type SelectedOrgAccount } from "./AuthContext";
import type { OrganizationId, AccountId } from "@/lib/branded-types";

// Mock firebase/auth (modular SDK functions)
vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn(() => vi.fn()),
  signOut: vi.fn(() => Promise.resolve()),
}));

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

// Mock Firebase
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: null,
    onAuthStateChanged: vi.fn(() => vi.fn()), // Return unsubscribe function
  },
  authInitialized: true,
  authBypassEnabled: false,
}));

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Test component that uses the auth context
function TestComponent({
  onContextUpdate,
}: {
  onContextUpdate?: (auth: any) => void;
}) {
  const auth = useAuth();

  if (onContextUpdate) {
    onContextUpdate(auth);
  }

  return <div data-testid="test-component" />;
}

describe("AuthContext - setSelectedOrgAccount", () => {
  let authContext: any;

  const mockSelectedAccount: SelectedOrgAccount = {
    orgId: "org-123" as OrganizationId,
    accountId: "acc-456" as AccountId,
    metadata: {
      organization_name: "Test Org",
      account_name: "Test Account",
      industry: "Technology",
      status: "active",
      timezone: "UTC",
      plan: "premium",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    authContext = null;
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  const renderWithAuth = (onContextUpdate?: (auth: any) => void) => {
    return render(
      <AuthProvider>
        <TestComponent onContextUpdate={onContextUpdate} />
      </AuthProvider>,
    );
  };

  test("setSelectedOrgAccount should handle null without throwing errors", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    expect(() => {
      act(() => {
        authContext.setSelectedOrgAccount(null);
      });
    }).not.toThrow();
  });

  test("setSelectedOrgAccount should save valid account to localStorage", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    act(() => {
      authContext.setSelectedOrgAccount(mockSelectedAccount);
    });

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "selectedOrgAccount",
      JSON.stringify(mockSelectedAccount),
    );
  });

  test("setSelectedOrgAccount should remove localStorage when passed null", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    act(() => {
      authContext.setSelectedOrgAccount(null);
    });

    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "selectedOrgAccount",
    );
  });

  test("setSelectedOrgAccount should update context state with valid account", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    act(() => {
      authContext.setSelectedOrgAccount(mockSelectedAccount);
    });

    expect(authContext.selectedOrgAccount).toEqual(mockSelectedAccount);
  });

  test("setSelectedOrgAccount should clear context state when passed null", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    // First set a valid account
    act(() => {
      authContext.setSelectedOrgAccount(mockSelectedAccount);
    });

    expect(authContext.selectedOrgAccount).toEqual(mockSelectedAccount);

    // Then clear it with null
    act(() => {
      authContext.setSelectedOrgAccount(null);
    });

    expect(authContext.selectedOrgAccount).toBeNull();
  });

  test("setSelectedOrgAccount should clear notifications when passed null", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    // Mock that there are some notifications initially
    act(() => {
      authContext.setNotifications([
        {
          id: "1",
          message: "Test notification",
          type: "info",
          timestamp: new Date(),
        },
      ]);
    });

    expect(authContext.notifications).toHaveLength(1);

    // Clear account should clear notifications
    act(() => {
      authContext.setSelectedOrgAccount(null);
    });

    expect(authContext.notifications).toEqual([]);
  });

  test("reproduces original error scenario - calling setSelectedOrgAccount(null) from account deletion", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    // Set up a scenario similar to account deletion
    act(() => {
      authContext.setSelectedOrgAccount(mockSelectedAccount);
    });

    expect(authContext.selectedOrgAccount).toEqual(mockSelectedAccount);

    // This should NOT throw an error (reproducing the original bug fix)
    expect(() => {
      act(() => {
        // Simulate what happens in AccountsManagement.tsx line 903
        authContext.setSelectedOrgAccount(null);
      });
    }).not.toThrow();

    // Verify the state was properly cleared
    expect(authContext.selectedOrgAccount).toBeNull();
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "selectedOrgAccount",
    );
    expect(authContext.notifications).toEqual([]);
  });

  test("setSelectedOrgAccount should handle rapid null/valid account switching", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    // Rapid switching between null and valid account
    act(() => {
      authContext.setSelectedOrgAccount(null);
      authContext.setSelectedOrgAccount(mockSelectedAccount);
      authContext.setSelectedOrgAccount(null);
      authContext.setSelectedOrgAccount(mockSelectedAccount);
    });

    expect(authContext.selectedOrgAccount).toEqual(mockSelectedAccount);
    expect(localStorageMock.setItem).toHaveBeenLastCalledWith(
      "selectedOrgAccount",
      JSON.stringify(mockSelectedAccount),
    );
  });

  test("setSelectedOrgAccount should handle invalid account object gracefully", () => {
    renderWithAuth((auth) => {
      authContext = auth;
    });

    const incompleteAccount = {
      orgId: "org-123" as OrganizationId,
      // Missing accountId and metadata
    } as any;

    // This should not throw even with incomplete data
    expect(() => {
      act(() => {
        authContext.setSelectedOrgAccount(incompleteAccount);
      });
    }).not.toThrow();
  });
});

describe("AuthContext - logout", () => {
  let authContext: any;

  const renderWithAuth = (onContextUpdate?: (auth: any) => void) => {
    return render(
      <AuthProvider>
        <TestComponent onContextUpdate={onContextUpdate} />
      </AuthProvider>,
    );
  };

  beforeEach(async () => {
    vi.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    authContext = null;

    // Restore default mocks for firebase/auth and firebase lib
    const firebaseAuth = await import("firebase/auth");
    (firebaseAuth.signOut as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );

    const firebaseLib = await import("@/lib/firebase");
    (firebaseLib as any).authInitialized = true;
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  // TC-A: happy path — signOut is called with the auth object and local state is cleared
  test("TC-A: logout calls signOut(auth) and clears user state when authInitialized=true", async () => {
    const { signOut } = await import("firebase/auth");
    const { auth } = await import("@/lib/firebase");

    renderWithAuth((ctx) => {
      authContext = ctx;
    });

    await act(async () => {
      await authContext.logout();
    });

    expect(signOut).toHaveBeenCalledTimes(1);
    expect(signOut).toHaveBeenCalledWith(auth);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("user");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "hasSelectedWorkspace",
    );
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "currentOrganizationId",
    );
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "selectedOrgAccount",
    );
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("orgMetadata");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("accountMetadata");
  });

  // TC-B: bypass path — signOut is NOT called, local state is still cleared
  test("TC-B: logout does not throw and skips signOut when authInitialized=false (bypass path)", async () => {
    const { signOut } = await import("firebase/auth");
    const firebaseLib = await import("@/lib/firebase");
    // Override authInitialized to simulate bypass / stub mode
    (firebaseLib as any).authInitialized = false;

    renderWithAuth((ctx) => {
      authContext = ctx;
    });

    await expect(
      act(async () => {
        await authContext.logout();
      }),
    ).resolves.not.toThrow();

    expect(signOut).not.toHaveBeenCalled();
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("user");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "currentOrganizationId",
    );
  });

  // TC-C: failure path — signOut rejects; toast.error is shown; local state is still cleared
  test("TC-C: logout surfaces toast.error and clears state even when signOut rejects", async () => {
    const { signOut } = await import("firebase/auth");
    const { toast } = await import("sonner");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    (signOut as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("network"),
    );

    renderWithAuth((ctx) => {
      authContext = ctx;
    });

    await expect(
      act(async () => {
        await authContext.logout();
      }),
    ).resolves.not.toThrow();

    expect(consoleSpy).toHaveBeenCalledWith(
      "[AuthContext] Firebase signOut failed",
      expect.any(Error),
    );
    expect(toast.error).toHaveBeenCalledTimes(1);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("user");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      "currentOrganizationId",
    );

    consoleSpy.mockRestore();
  });
});

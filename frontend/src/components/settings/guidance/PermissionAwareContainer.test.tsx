import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  PermissionAwareContainer,
  PermissionCheck,
  ConditionalPermission,
} from "./PermissionAwareContainer";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";

const mockAuthContext: AuthContextType = {
  user: {
    id: "user-123",
    firstName: "John",
    lastName: "Doe",
    email: "john.doe@example.com",
    permissions: {
      organizations: {
        "org-123": "admin",
        "org-456": "member",
        "org-789": "viewer",
      },
    },
  },
  isAuthenticated: true,
  isLoading: false,
  orgMetadata: {},
  selectedOrgAccount: {
    orgId: "org-123",
    accountId: "account-123",
    metadata: {
      organization_name: "Test Organization",
      account_name: "Test Account",
      industry: "Technology",
      status: "Active",
      timezone: "UTC",
      plan: "Pro",
    },
  },
  currentOrganizationId: "org-123",
  notificationSettings: [],
  securitySettings: [],
  setCurrentOrganization: vi.fn(),
  setOrgMetadata: vi.fn(),
  updateUser: vi.fn(),
  setNotificationSettings: vi.fn(),
  signOut: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  getUserOrganizations: vi.fn(),
  getOrganizationData: vi.fn(),
  refetchUser: vi.fn(),
  clearUserData: vi.fn(),
};

const TestWrapper = ({
  children,
  authContext = mockAuthContext,
}: {
  children: React.ReactNode;
  authContext?: AuthContextType;
}) => (
  <AuthContext.Provider value={authContext}>{children}</AuthContext.Provider>
);

describe("PermissionAwareContainer", () => {
  test("renders children when user has required permission", () => {
    render(
      <TestWrapper>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          <div>Protected Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  test("shows permission hint when user lacks required permission", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          <div>Protected Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("organization level")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  test("shows graceful degradation when enabled", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
          gracefulDegradation={true}
        >
          <div>Protected Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
  });

  test("shows fallback content when provided", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
          fallbackContent={<div>Fallback Content</div>}
        >
          <div>Protected Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByText("Fallback Content")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  test("returns nothing when no permission and no fallback", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    const { container } = render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
          showPermissionHint={false}
        >
          <div>Protected Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(container.firstChild).toBeNull();
  });
});

describe("PermissionCheck", () => {
  test("calls children function with correct permission status", () => {
    const childrenMock = vi.fn(() => <div>Test Content</div>);

    render(
      <TestWrapper>
        <PermissionCheck
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          {childrenMock}
        </PermissionCheck>
      </TestWrapper>,
    );

    expect(childrenMock).toHaveBeenCalledWith(true);
    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });

  test("calls children function with false when permission lacking", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    const childrenMock = vi.fn(() => <div>Test Content</div>);

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionCheck
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          {childrenMock}
        </PermissionCheck>
      </TestWrapper>,
    );

    expect(childrenMock).toHaveBeenCalledWith(false);
  });
});

describe("ConditionalPermission", () => {
  test("renders children when condition is false", () => {
    render(
      <TestWrapper>
        <ConditionalPermission
          when={false}
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          <div>Content</div>
        </ConditionalPermission>
      </TestWrapper>,
    );

    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  test("applies permission check when condition is true", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <ConditionalPermission
          when={true}
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          <div>Content</div>
        </ConditionalPermission>
      </TestWrapper>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });

  test("shows fallback when condition is true and permission lacking", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <ConditionalPermission
          when={true}
          requiredPermission="test-permission"
          requiredRole="admin"
          fallback={<div>Fallback</div>}
        >
          <div>Content</div>
        </ConditionalPermission>
      </TestWrapper>,
    );

    expect(screen.getByText("Fallback")).toBeInTheDocument();
    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });
});

describe("Role hierarchy", () => {
  test("admin role can access member-required content", () => {
    render(
      <TestWrapper>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="member"
        >
          <div>Member Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByText("Member Content")).toBeInTheDocument();
  });

  test("member role can access viewer-required content", () => {
    const contextWithMemberRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "member",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithMemberRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="viewer"
        >
          <div>Viewer Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByText("Viewer Content")).toBeInTheDocument();
  });

  test("viewer role cannot access admin-required content", () => {
    const contextWithViewerRole = {
      ...mockAuthContext,
      user: {
        ...mockAuthContext.user!,
        permissions: {
          organizations: {
            "org-123": "viewer",
          },
        },
      },
    };

    render(
      <TestWrapper authContext={contextWithViewerRole}>
        <PermissionAwareContainer
          requiredPermission="test-permission"
          requiredRole="admin"
        >
          <div>Admin Content</div>
        </PermissionAwareContainer>
      </TestWrapper>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("organization level")).toBeInTheDocument();
    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });
});

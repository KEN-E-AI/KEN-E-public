import React from "react";
import { render, RenderOptions } from "@testing-library/react";
import { MemoryRouter, MemoryRouterProps } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";

// Default mock auth context
const defaultMockAuthContext: AuthContextType = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  orgMetadata: {},
  selectedOrgAccount: null,
  currentOrganizationId: null,
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

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  authContext?: Partial<AuthContextType>;
  routerProps?: MemoryRouterProps;
}

// Create a custom render function that includes all providers
export function renderWithProviders(
  ui: React.ReactElement,
  {
    authContext = {},
    routerProps = { initialEntries: ["/"] },
    ...renderOptions
  }: CustomRenderOptions = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { 
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: { 
        retry: false 
      },
    },
  });

  const mergedAuthContext = {
    ...defaultMockAuthContext,
    ...authContext,
  } as AuthContextType;

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter {...routerProps}>
          <AuthContext.Provider value={mergedAuthContext}>
            {children}
          </AuthContext.Provider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
}

// Re-export everything from React Testing Library
export * from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";
import { createContext, useContext, useState, ReactNode } from "react";

interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  hasSelectedWorkspace: boolean;
  currentOrganizationId: string | null;
  selectedOrgAccount: string | null;
  login: (user: User) => void;
  logout: () => void;
  completeWorkspaceSelection: () => void;
  resetWorkspaceSelection: () => void;
  setCurrentOrganization: (orgId: string) => void;
  setSelectedOrgAccount: (combinedId: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [hasSelectedWorkspace, setHasSelectedWorkspace] = useState(false);
  const [currentOrganizationId, setCurrentOrganizationId] = useState<
    string | null
  >(null);
  const [selectedOrgAccount, setSelectedOrgAccountState] = useState<
    string | null
  >(null);

  const login = (userData: User) => {
    setUser(userData);
    // In a real app, you'd also store the auth token
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const logout = () => {
    setUser(null);
    setHasSelectedWorkspace(false);
    localStorage.removeItem("user");
    localStorage.removeItem("hasSelectedWorkspace");
  };

  const completeWorkspaceSelection = () => {
    setHasSelectedWorkspace(true);
    localStorage.setItem("hasSelectedWorkspace", "true");
  };

  const resetWorkspaceSelection = () => {
    setHasSelectedWorkspace(false);
    setCurrentOrganizationId(null);
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("currentOrganizationId");
  };

  const setCurrentOrganization = (orgId: string) => {
    setCurrentOrganizationId(orgId);
    localStorage.setItem("currentOrganizationId", orgId);
  };

  const setSelectedOrgAccount = (combinedId: string) => {
    setSelectedOrgAccountState(combinedId);
    localStorage.setItem("selectedOrgAccount", combinedId);
  };

  // Initialize auth state from localStorage on component mount
  useState(() => {
    const savedUser = localStorage.getItem("user");
    const savedWorkspaceSelection = localStorage.getItem(
      "hasSelectedWorkspace",
    );
    const savedOrganizationId = localStorage.getItem("currentOrganizationId");

    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }

    if (savedWorkspaceSelection === "true") {
      setHasSelectedWorkspace(true);
    }

    if (savedOrganizationId) {
      setCurrentOrganizationId(savedOrganizationId);
    }
  });

  const value = {
    user,
    isAuthenticated: !!user,
    hasSelectedWorkspace,
    currentOrganizationId,
    login,
    logout,
    completeWorkspaceSelection,
    resetWorkspaceSelection,
    setCurrentOrganization,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

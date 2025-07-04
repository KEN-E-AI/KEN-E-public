import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import axios from "axios";

interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  jobTitle?: string;
  permissions?: {
    accounts?: Record<string, string>;
    organizations?: Record<string, string>;
  };
  preferences?: {
    theme?: string;
    language?: string;
    date_format?: string;
  };
}

export interface SelectedOrgAccount {
  orgId: string;
  accountId: string;
  metadata: {
    organization_name: string;
    account_name: string;
    industry: string;
    status: string;
    timezone?: string;
    plan?: string;
    [key: string]: any;
  };
}

interface Notification {
  id: string;
  account_id: string;
  category: string;
  created_date: string;
  data: {
    hasIndicator: boolean;
    icon: string;
    metadata: {
      priority: string;
      source: string;
      tags: string[];
    };
    title: string;
    type: string;
  };
  description: string;
  modified_timestamp: number;
  status: string;
}

interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

interface SecuritySetting {
  id: string;
  label: string;
  description: string;
  action_text: string;
  action_type: "button" | "switch";
  status?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  hasSelectedWorkspace: boolean;
  currentOrganizationId: string | null;
  selectedOrgAccount: SelectedOrgAccount | null;
  login: (user: User) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
  completeWorkspaceSelection: () => void;
  resetWorkspaceSelection: () => void;
  setCurrentOrganization: (orgId: string) => void;
  setSelectedOrgAccount: (account: SelectedOrgAccount) => void;
  orgMetadata: Record<string, any>;
  accountMetadata: Record<string, any>;
  setOrgMetadata: (data: Record<string, any>) => void;
  setAccountMetadata: (data: Record<string, any>) => void;
  notifications: Notification[];
  setNotifications: (n: Notification[]) => void;
  notificationSettings: NotificationSetting[];
  securitySettings: SecuritySetting[];
  setNotificationSettings: (settings: NotificationSetting[]) => void;
  setSecuritySettings: (settings: SecuritySetting[]) => void;
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
  const [selectedOrgAccount, setSelectedOrgAccountState] = useState<SelectedOrgAccount | null>(null);
  const [orgMetadata, setOrgMetadata] = useState<Record<string, any>>({});
  const [accountMetadata, setAccountMetadata] = useState<Record<string, any>>({});
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationSettings, setNotificationSettings] = useState<NotificationSetting[]>([]);
  const [securitySettings, setSecuritySettings] = useState<SecuritySetting[]>([]);

  const fetchNotifications = async (accountId: string) => {
    try {
      const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/query`, {
        account_id: accountId,
        collection: "notifications",
        field: "account_id",
        operator: "==",
        value: accountId,
        limit: 20,
      });

      console.log("📬 Notifications fetched in context:", res.data);
      const documents = res.data.documents ?? []; // ✅ fallback to empty array
      const sorted = [...documents].sort((a, b) =>
        new Date(b.created_date).getTime() - new Date(a.created_date).getTime()
      );

      setNotifications(sorted);
    } catch (err) {
      console.error("❌ Failed to fetch notifications in context", err);
    }
  };


  const login = (userData: User) => {
    setUser(userData);
    // In a real app, you'd also store the auth token
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const updateUser = (updates: Partial<User>) => {
    setUser(prev => {
      const merged = { ...prev, ...updates };
      localStorage.setItem("user", JSON.stringify(merged));
      return merged;
    });
  };

  const logout = () => {
    setUser(null);
    setHasSelectedWorkspace(false);
    setSelectedOrgAccountState(null);
    localStorage.removeItem("user");
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("selectedOrgAccount");
  };

  const completeWorkspaceSelection = () => {
    setHasSelectedWorkspace(true);
    localStorage.setItem("hasSelectedWorkspace", "true");
  };

  const resetWorkspaceSelection = () => {
    setHasSelectedWorkspace(false);
    setCurrentOrganizationId(null);
    setSelectedOrgAccountState(null);
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("currentOrganizationId");
    localStorage.removeItem("selectedOrgAccount");
  };

  const setCurrentOrganization = (orgId: string) => {
    setCurrentOrganizationId(orgId);
    localStorage.setItem("currentOrganizationId", orgId);
  };

  const setSelectedOrgAccount = (account: SelectedOrgAccount) => {
    console.log("✅ Context updated:", account);
    setSelectedOrgAccountState(account);
    localStorage.setItem("selectedOrgAccount", JSON.stringify(account));

    // 🧠 Fetch notifications here
    fetchNotifications(account.accountId);
  };

  // Initialize auth state from localStorage on component mount
  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    const savedWorkspaceSelection = localStorage.getItem(
      "hasSelectedWorkspace",
    );
    const savedOrganizationId = localStorage.getItem("currentOrganizationId");
    const savedOrgAccount = localStorage.getItem("selectedOrgAccount");

    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }

    if (savedWorkspaceSelection === "true") {
      setHasSelectedWorkspace(true);
    }

    if (savedOrganizationId) {
      setCurrentOrganizationId(savedOrganizationId);
    }

    if (savedOrgAccount) {
      try {
        setSelectedOrgAccountState(JSON.parse(savedOrgAccount));
      } catch (err) {
        console.warn("Failed to parse savedOrgAccount", err);
      }
    }
  });

  const value = {
    user,
    isAuthenticated: !!user,
    hasSelectedWorkspace,
    currentOrganizationId,
    selectedOrgAccount,
    login,
    logout,
    updateUser,
    completeWorkspaceSelection,
    resetWorkspaceSelection,
    setCurrentOrganization,
    setSelectedOrgAccount,
    orgMetadata,
    accountMetadata,
    setOrgMetadata,
    setAccountMetadata,
    notifications,
    setNotifications,
    notificationSettings,
    securitySettings,
    setNotificationSettings,
    setSecuritySettings,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

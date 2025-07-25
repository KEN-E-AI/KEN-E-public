import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import axios from "axios";
import type { UserId, OrganizationId, AccountId } from "@/lib/branded-types";
import {
  toUserId,
  toOrganizationId,
  toAccountId,
  tryOrganizationId,
  tryAccountId,
} from "@/lib/branded-types";

interface User {
  id: UserId;
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
  orgId: OrganizationId;
  accountId: AccountId;
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
  account_id: AccountId;
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
  currentOrganizationId: OrganizationId | null;
  selectedOrgAccount: SelectedOrgAccount | null;
  login: (user: User) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
  completeWorkspaceSelection: () => void;
  resetWorkspaceSelection: () => void;
  setCurrentOrganization: (orgId: OrganizationId) => void;
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

export const AuthContext = createContext<AuthContextType | undefined>(
  undefined,
);

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
  const [currentOrganizationId, setCurrentOrganizationId] =
    useState<OrganizationId | null>(null);
  const [selectedOrgAccount, setSelectedOrgAccountState] =
    useState<SelectedOrgAccount | null>(null);
  const [orgMetadata, setOrgMetadataState] = useState<Record<string, any>>({});
  const [accountMetadata, setAccountMetadataState] = useState<
    Record<string, any>
  >({});
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationSettings, setNotificationSettings] = useState<
    NotificationSetting[]
  >([]);
  const [securitySettings, setSecuritySettings] = useState<SecuritySetting[]>(
    [],
  );

  // Wrapper functions to persist metadata to localStorage
  const setOrgMetadata = (data: Record<string, any>) => {
    setOrgMetadataState(data);
    localStorage.setItem("orgMetadata", JSON.stringify(data));
  };

  const setAccountMetadata = (data: Record<string, any>) => {
    setAccountMetadataState(data);
    localStorage.setItem("accountMetadata", JSON.stringify(data));
  };

  const fetchNotifications = async (accountId: AccountId) => {
    try {
      const res = await axios.post(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/firestore/documents/query`,
        {
          account_id: accountId,
          collection: "notifications",
          field: "account_id",
          operator: "==",
          value: accountId,
          limit: 20,
        },
      );

      console.log("📬 Notifications fetched in context:", res.data);
      const documents = res.data.documents ?? []; // ✅ fallback to empty array
      const sorted = [...documents].sort(
        (a, b) =>
          new Date(b.created_date).getTime() -
          new Date(a.created_date).getTime(),
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
    setUser((prev) => {
      const merged = { ...prev, ...updates };
      localStorage.setItem("user", JSON.stringify(merged));
      return merged;
    });
  };

  const logout = () => {
    setUser(null);
    setHasSelectedWorkspace(false);
    setSelectedOrgAccountState(null);
    setOrgMetadataState({});
    setAccountMetadataState({});
    localStorage.removeItem("user");
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("selectedOrgAccount");
    localStorage.removeItem("orgMetadata");
    localStorage.removeItem("accountMetadata");
  };

  const completeWorkspaceSelection = () => {
    setHasSelectedWorkspace(true);
    localStorage.setItem("hasSelectedWorkspace", "true");
  };

  const resetWorkspaceSelection = () => {
    setHasSelectedWorkspace(false);
    setCurrentOrganizationId(null);
    setSelectedOrgAccountState(null);
    setOrgMetadataState({});
    setAccountMetadataState({});
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("currentOrganizationId");
    localStorage.removeItem("selectedOrgAccount");
    localStorage.removeItem("orgMetadata");
    localStorage.removeItem("accountMetadata");
  };

  const setCurrentOrganization = (orgId: OrganizationId) => {
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
    const savedOrgMetadata = localStorage.getItem("orgMetadata");
    const savedAccountMetadata = localStorage.getItem("accountMetadata");

    if (savedUser) {
      const userData = JSON.parse(savedUser);
      // Convert id to branded type
      if (userData.id) {
        userData.id = toUserId(userData.id);
      }
      setUser(userData);
    }

    if (savedWorkspaceSelection === "true") {
      setHasSelectedWorkspace(true);
    }

    if (savedOrganizationId) {
      const orgId = tryOrganizationId(savedOrganizationId);
      if (orgId) {
        setCurrentOrganizationId(orgId);
      }
    }

    if (savedOrgAccount) {
      try {
        const parsedOrgAccount = JSON.parse(savedOrgAccount);
        // Convert IDs to branded types
        if (parsedOrgAccount.orgId) {
          parsedOrgAccount.orgId = toOrganizationId(parsedOrgAccount.orgId);
        }
        if (parsedOrgAccount.accountId) {
          parsedOrgAccount.accountId = toAccountId(parsedOrgAccount.accountId);
        }
        setSelectedOrgAccountState(parsedOrgAccount);
        // Fetch notifications for the restored account
        fetchNotifications(parsedOrgAccount.accountId);
      } catch (err) {
        console.warn("Failed to parse savedOrgAccount", err);
      }
    }

    if (savedOrgMetadata) {
      try {
        setOrgMetadataState(JSON.parse(savedOrgMetadata));
      } catch (err) {
        console.warn("Failed to parse savedOrgMetadata", err);
      }
    }

    if (savedAccountMetadata) {
      try {
        setAccountMetadataState(JSON.parse(savedAccountMetadata));
      } catch (err) {
        console.warn("Failed to parse savedAccountMetadata", err);
      }
    }
  }, []); // Add empty dependency array to run only on mount

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

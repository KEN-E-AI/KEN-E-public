import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import api from "@/lib/api";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { toast } from "sonner";
import { auth, authBypassEnabled, authInitialized } from "@/lib/firebase";
import type { UserId, OrganizationId, AccountId } from "@/lib/branded-types";

// VITE_AUTH_BYPASS_WORKSPACE_SELECTED=false keeps hasSelectedWorkspace=false so
// ProtectedRoute redirects to /select-organization for org-selection flow testing.
const authBypassWorkspaceSelected =
  import.meta.env.VITE_AUTH_BYPASS_WORKSPACE_SELECTED !== "false";
import {
  toUserId,
  toOrganizationId,
  toAccountId,
  tryOrganizationId,
  tryAccountId,
} from "@/lib/branded-types";
import { validateAndCleanAuthState } from "@/utils/authRecovery";

interface User {
  id: UserId;
  email: string;
  firstName: string;
  lastName: string;
  jobTitle?: string;
  permissions?: {
    account_permissions?: Record<string, string>; // New canonical structure
    organizations?: Record<string, string>;
    accounts?: Record<string, string>; // Deprecated - kept for backward compatibility
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
  created_at: string;
  created_date?: string; // For backward compatibility
  data?: {
    hasIndicator?: boolean;
    icon?: string;
    metadata?: {
      priority: string;
      source: string;
      tags: string[];
    };
    title?: string;
    type?: string;
    badge?: string;
    [key: string]: any;
  };
  description: string;
  modified_timestamp?: number;
  status: string;
  read_at?: string;
  user_archived_at?: string;
  archived_at?: string;
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
  isAuthLoading: boolean;
  hasSelectedWorkspace: boolean;
  currentOrganizationId: OrganizationId | null;
  selectedOrgAccount: SelectedOrgAccount | null;
  login: (user: User) => void;
  logout: () => Promise<void>;
  updateUser: (updates: Partial<User>) => void;
  completeWorkspaceSelection: () => void;
  resetWorkspaceSelection: () => void;
  setCurrentOrganization: (orgId: OrganizationId) => void;
  setSelectedOrgAccount: (account: SelectedOrgAccount | null) => void;
  orgMetadata: Record<string, any>;
  accountMetadata: Record<string, any>;
  setOrgMetadata: (data: Record<string, any>) => void;
  setAccountMetadata: (data: Record<string, any>) => void;
  notifications: Notification[];
  setNotifications: (n: Notification[]) => void;
  refreshNotifications: () => Promise<void>;
  notificationSettings: NotificationSetting[];
  securitySettings: SecuritySetting[];
  setNotificationSettings: (settings: NotificationSetting[]) => void;
  setSecuritySettings: (settings: SecuritySetting[]) => void;
  isSuperAdmin: boolean;
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
  const [isAuthLoading, setIsAuthLoading] = useState(true);
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
      // Use the proper notifications API endpoint that includes user-specific status
      const res = await api.get(`/api/v1/notifications/`, {
        params: {
          include_archived: false,
        },
      });

      console.log("📬 Notifications fetched in context:", res.data);
      const notifications = res.data ?? []; // ✅ fallback to empty array

      // Filter by account_id since the API returns all notifications for the user
      const accountNotifications = notifications.filter(
        (n: any) => n.account_id === accountId,
      );

      console.log(
        "📬 Filtered notifications for account:",
        accountId,
        accountNotifications,
      );
      console.log(
        "📬 Individual notification statuses:",
        accountNotifications.map((doc: any) => ({
          id: doc.id,
          status: doc.status,
          statusType: typeof doc.status,
          statusValue: JSON.stringify(doc.status),
          hasStatusField: "status" in doc,
          allFields: Object.keys(doc),
        })),
      );

      const sorted = [...accountNotifications].sort(
        (a: any, b: any) =>
          new Date(b.created_at || b.created_date).getTime() -
          new Date(a.created_at || a.created_date).getTime(),
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

  const logout = async () => {
    if (authInitialized) {
      try {
        await signOut(auth);
      } catch (err) {
        console.error("[AuthContext] Firebase signOut failed", err);
        toast.error(
          "Failed to sign out completely. Please refresh and try again.",
        );
      }
    }
    setUser(null);
    setHasSelectedWorkspace(false);
    setCurrentOrganizationId(null);
    setSelectedOrgAccountState(null);
    setOrgMetadataState({});
    setAccountMetadataState({});
    localStorage.removeItem("user");
    localStorage.removeItem("hasSelectedWorkspace");
    localStorage.removeItem("currentOrganizationId");
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

  /**
   * Sets the selected organization account or clears it if null is passed.
   * When an account is selected, it saves to localStorage and fetches notifications.
   * When null is passed, it clears localStorage and notifications.
   * @param account - The account to select, or null to clear selection
   */
  const setSelectedOrgAccount = (account: SelectedOrgAccount | null) => {
    console.log("✅ Context updated:", account);
    setSelectedOrgAccountState(account);

    if (account) {
      // Keep currentOrganizationId in lockstep with the selected workspace.
      // The two are persisted under separate localStorage keys and would
      // otherwise drift — leaving the org-settings page on a different org
      // than the header switcher.
      if (account.orgId) {
        setCurrentOrganizationId(account.orgId);
        localStorage.setItem("currentOrganizationId", account.orgId);
      }
      localStorage.setItem("selectedOrgAccount", JSON.stringify(account));
      // 🧠 Fetch notifications here
      fetchNotifications(account.accountId);
    } else {
      localStorage.removeItem("selectedOrgAccount");
      // Clear notifications when no account is selected
      setNotifications([]);
    }
  };

  /**
   * Refreshes notifications for the currently selected account.
   * This can be called after creating an account or when notifications need to be updated.
   */
  const refreshNotifications = async () => {
    if (selectedOrgAccount?.accountId) {
      console.log(
        "🔄 Refreshing notifications for account:",
        selectedOrgAccount.accountId,
      );
      await fetchNotifications(selectedOrgAccount.accountId);
    } else {
      console.log("⚠️ No account selected, cannot refresh notifications");
    }
  };

  // Sync with Firebase auth state
  useEffect(() => {
    if (!authInitialized) {
      // Either bypass mode or init failed in firebase.ts. Either way, the
      // `auth` export is a stub and onAuthStateChanged would throw.
      if (authBypassEnabled) {
        const bypassRole = import.meta.env.VITE_AUTH_BYPASS_ROLE;
        const bypassEmail =
          bypassRole === "regular"
            ? "test-bypass@external-test.com"
            : "test-bypass@ken-e.ai";
        console.warn(
          `[AuthContext] auth bypass active — injecting synthetic test user (role: ${bypassRole ?? "superadmin"}, workspace: ${authBypassWorkspaceSelected})`,
        );
        const fakeUser: User = {
          id: toUserId("test-bypass-uid"),
          email: bypassEmail,
          firstName: "Test",
          lastName: "Bypass",
        };
        setUser(fakeUser);
        localStorage.setItem("user", JSON.stringify(fakeUser));
        if (authBypassWorkspaceSelected) {
          setHasSelectedWorkspace(true);
          localStorage.setItem("hasSelectedWorkspace", "true");
          const orgId = toOrganizationId("org_bypass");
          const accountId = toAccountId("acc_bypass");
          setCurrentOrganizationId(orgId);
          localStorage.setItem("currentOrganizationId", orgId);
          setSelectedOrgAccountState({
            orgId,
            accountId,
            metadata: {
              organization_name: "Bypass Org",
              account_name: "Bypass Account",
              industry: "test",
              status: "active",
            },
          });
        }
      }
      setIsAuthLoading(false);
      return;
    }
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      if (!firebaseUser) {
        // User is signed out - clear all state
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
      } else {
        // User is signed in, restore state from localStorage if available
        const savedUser = localStorage.getItem("user");
        if (savedUser) {
          try {
            const parsedUser = JSON.parse(savedUser);
            setUser(parsedUser);
          } catch (error) {
            console.error("Failed to parse saved user:", error);
          }
        }
      }
      // Set loading to false after auth state is determined
      setIsAuthLoading(false);
    });

    return () => unsubscribe();
  }, []);

  // Initialize auth state from localStorage on component mount
  useEffect(() => {
    // First, validate and clean any corrupted auth state
    validateAndCleanAuthState().then((result) => {
      if (result.clearedItems.length > 0) {
        console.warn("Auth state recovery performed:", result.message);
      }
    });

    const savedWorkspaceSelection = localStorage.getItem(
      "hasSelectedWorkspace",
    );
    const savedOrganizationId = localStorage.getItem("currentOrganizationId");
    const savedOrgAccount = localStorage.getItem("selectedOrgAccount");
    const savedOrgMetadata = localStorage.getItem("orgMetadata");
    const savedAccountMetadata = localStorage.getItem("accountMetadata");

    // User state is now handled by Firebase auth state listener

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
        // Ensure the parsed object is valid and has the expected structure
        if (parsedOrgAccount && typeof parsedOrgAccount === "object") {
          // Convert IDs to branded types
          if (parsedOrgAccount.orgId) {
            parsedOrgAccount.orgId = toOrganizationId(parsedOrgAccount.orgId);
          }
          if (parsedOrgAccount.accountId) {
            parsedOrgAccount.accountId = toAccountId(
              parsedOrgAccount.accountId,
            );
          }
          setSelectedOrgAccountState(parsedOrgAccount);
          // selectedOrgAccount is authoritative for the active workspace —
          // realign currentOrganizationId to it so a previously drifted
          // localStorage pair cannot survive a reload.
          if (parsedOrgAccount.orgId) {
            setCurrentOrganizationId(parsedOrgAccount.orgId);
          }
        } else {
          console.warn("Invalid savedOrgAccount structure:", parsedOrgAccount);
          // Clear invalid data from localStorage
          localStorage.removeItem("selectedOrgAccount");
        }
        // Don't fetch notifications here - wait for Firebase auth
      } catch (err) {
        console.warn("Failed to parse savedOrgAccount", err);
        // Clear invalid data from localStorage
        localStorage.removeItem("selectedOrgAccount");
      }
    }

    if (savedOrgMetadata && savedOrgMetadata !== "undefined") {
      try {
        setOrgMetadataState(JSON.parse(savedOrgMetadata));
      } catch (err) {
        console.warn("Failed to parse savedOrgMetadata", err);
      }
    }

    if (savedAccountMetadata && savedAccountMetadata !== "undefined") {
      try {
        setAccountMetadataState(JSON.parse(savedAccountMetadata));
      } catch (err) {
        console.warn("Failed to parse savedAccountMetadata", err);
      }
    }
  }, []); // Add empty dependency array to run only on mount

  // Synchronize accountMetadata with orgMetadata.accounts to fix EntitySelector
  useEffect(() => {
    const flattenAccounts = (
      orgData: Record<string, any>,
    ): Record<string, any> => {
      const flattened: Record<string, any> = {};

      for (const org of Object.values(orgData)) {
        if (org?.accounts && Array.isArray(org.accounts)) {
          for (const account of org.accounts) {
            if (account?.account_id) {
              flattened[account.account_id] = account;
            }
          }
        }
      }

      return flattened;
    };

    const newAccountMetadata = flattenAccounts(orgMetadata);

    // Only update if there's actual data and it's different from current state
    if (Object.keys(newAccountMetadata).length > 0) {
      setAccountMetadataState(newAccountMetadata);
      localStorage.setItem(
        "accountMetadata",
        JSON.stringify(newAccountMetadata),
      );
    }
  }, [orgMetadata]);

  // Fetch notifications when we have both auth and selected account
  useEffect(() => {
    const fetchNotificationsIfReady = async () => {
      // Check if we have Firebase auth, user data, and selected account
      if (auth.currentUser && user && selectedOrgAccount?.accountId) {
        await fetchNotifications(selectedOrgAccount.accountId);
      }
    };

    fetchNotificationsIfReady();
  }, [user, selectedOrgAccount?.accountId]); // Re-fetch when user or account changes

  const value = {
    user,
    isAuthenticated: !!user,
    isAuthLoading,
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
    refreshNotifications,
    notificationSettings,
    securitySettings,
    setNotificationSettings,
    setSecuritySettings,
    isSuperAdmin: user?.email?.toLowerCase().endsWith("@ken-e.ai") || false,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

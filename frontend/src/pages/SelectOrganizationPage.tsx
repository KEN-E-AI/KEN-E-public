import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import { useNavigate, Navigate } from "react-router-dom";
import { Check, Plus, ArrowRight, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Logo } from "@/components/branding/Logo";
import { cn } from "@/lib/utils";
import type { OrganizationId } from "@/lib/branded-types";
import { useAuth } from "@/contexts/AuthContext";
import {
  getOrganizations,
  getOrganizationsBatch,
} from "@/data/organizationApi";
import {
  resolveOrganizationAndAccount,
  formatWorkspaceMetadata,
} from "@/lib/organizationUtils";
import { WORKSPACE_SELECTION_DELAY } from "@/constants/organizationSelection";
import { useChildOrganizations } from "@/hooks/useChildOrganizations";
import { useAvailableAccounts } from "@/hooks/useAvailableAccounts";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export default function SelectOrganizationPage() {
  const navigate = useNavigate();
  const {
    user,
    setSelectedOrgAccount,
    completeWorkspaceSelection,
    setCurrentOrganization,
    setOrgMetadata,
    setAccountMetadata,
    isSuperAdmin,
    isAuthenticated,
    isAuthLoading,
    hasSelectedWorkspace,
  } = useAuth();

  const [selectedOrganization, setSelectedOrganization] = useState<string>("");
  const [selectedAccount, setSelectedAccount] = useState<string>("");
  const [selectedChildOrg, setSelectedChildOrg] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [orgsFromFirestore, setOrgsFromFirestore] = useState<
    Record<string, string>
  >({});
  // Fetch status — 'success' is required before the zero-orgs redirect can fire,
  // so a transient API failure can never spuriously bounce a multi-org user to
  // /create-organization (the empty initial state is indistinguishable from
  // "user has no orgs" without this gate).
  const [userDataFetchStatus, setUserDataFetchStatus] = useState<
    "loading" | "success" | "error"
  >("loading");
  const [userDataFetchAttempt, setUserDataFetchAttempt] = useState(0);
  const [localOrgMetadata, setLocalOrgMetadata] = useState<Record<string, any>>(
    {},
  );
  const [searchQuery, setSearchQuery] = useState("");

  const lastRefreshTime = useRef<number>(0);
  const isFetchingRef = useRef<boolean>(false);
  const lastOrgKeysRef = useRef<string>("");
  const continueTimerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(continueTimerRef.current), []);

  const { childOrganizations, clearChildOrganizations } =
    useChildOrganizations();

  useEffect(() => {
    const FIRESTORE_USER_ID = user?.id;
    if (!FIRESTORE_USER_ID) return;

    setUserDataFetchStatus("loading");
    let cancelled = false;

    const fetchUserData = async () => {
      try {
        if (isSuperAdmin) {
          const allOrgs = await getOrganizations();
          if (cancelled) return;
          const superAdminOrgs: Record<string, string> = {};
          allOrgs.forEach((org) => {
            superAdminOrgs[org.organization_id] = "admin";
          });
          setOrgsFromFirestore(superAdminOrgs);
          setUserDataFetchStatus("success");
          return;
        }
        const res = await api.get(
          `/api/v1/firestore/documents/users/${FIRESTORE_USER_ID}`,
        );
        if (cancelled) return;
        const orgs = res.data?.data?.permissions?.organizations;
        // Distinguish missing-shape (server bug → error UI) from empty perms
        // (genuine zero-orgs user → redirect). A {} fallback would silently
        // conflate the two and bounce existing users to /create-organization.
        if (orgs === undefined || orgs === null) {
          throw new Error("User document missing permissions.organizations");
        }
        setOrgsFromFirestore(orgs);
        setUserDataFetchStatus("success");
      } catch (error) {
        if (cancelled) return;
        console.error("Failed to fetch user org/account data", error);
        setUserDataFetchStatus("error");
      }
    };

    fetchUserData();
    return () => {
      cancelled = true;
    };
  }, [user?.id, isSuperAdmin, userDataFetchAttempt]);

  const fetchOrgMetadata = async () => {
    const orgIds = Object.keys(orgsFromFirestore);
    if (orgIds.length === 0) {
      setLocalOrgMetadata({});
      setOrgMetadata({});
      setAccountMetadata({});
      return;
    }

    try {
      const batchResult = await getOrganizationsBatch(orgIds, true);
      const result: Record<string, any> = {};
      const deletedOrgIds: string[] = [];

      orgIds.forEach((orgId) => {
        if (batchResult[orgId]) {
          result[orgId] = batchResult[orgId];
        } else {
          deletedOrgIds.push(orgId);
        }
      });

      if (deletedOrgIds.length > 0) {
        console.warn(
          `Found ${deletedOrgIds.length} deleted organizations in user permissions:`,
          deletedOrgIds,
        );
      }

      setLocalOrgMetadata(result);
      setOrgMetadata(result);

      const flattenedAccounts: Record<string, any> = {};
      Object.values(result).forEach((org: any) => {
        (org.accounts || []).forEach((acc: any) => {
          flattenedAccounts[acc.account_id] = acc;
        });
      });
      setAccountMetadata(flattenedAccounts);
    } catch (error) {
      console.error("Failed to fetch organization metadata:", error);
    }
  };

  const refreshOrgMetadata = async () => {
    if (Object.keys(orgsFromFirestore).length === 0) return;

    const now = Date.now();
    const currentOrgKeys = JSON.stringify(
      Object.keys(orgsFromFirestore).sort(),
    );

    if (isFetchingRef.current) return;
    if (
      now - lastRefreshTime.current < 5000 &&
      currentOrgKeys === lastOrgKeysRef.current
    )
      return;

    isFetchingRef.current = true;
    lastOrgKeysRef.current = currentOrgKeys;

    try {
      await fetchOrgMetadata();
      // Only commit the debounce window on success — failed fetches must be
      // retryable immediately, otherwise a transient error locks the UI for 5s.
      lastRefreshTime.current = now;
    } finally {
      isFetchingRef.current = false;
    }
  };

  useEffect(() => {
    if (Object.keys(orgsFromFirestore).length > 0) {
      refreshOrgMetadata();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgsFromFirestore]);

  // Zero-orgs redirect requires a successful fetch — see comment on
  // userDataFetchStatus above.
  useEffect(() => {
    if (
      !isAuthLoading &&
      isAuthenticated &&
      userDataFetchStatus === "success" &&
      Object.keys(orgsFromFirestore).length === 0 &&
      !isSuperAdmin
    ) {
      navigate("/create-organization", { replace: true });
    }
  }, [
    isAuthLoading,
    isAuthenticated,
    userDataFetchStatus,
    orgsFromFirestore,
    isSuperAdmin,
    navigate,
  ]);

  const organizationList = Object.entries(orgsFromFirestore)
    .filter(([orgId]) => localOrgMetadata[orgId] !== undefined)
    .map(([orgId, permission]) => {
      const metadata = localOrgMetadata[orgId] || {};
      return {
        organization_id: orgId,
        organization_name:
          metadata.organization_name || orgId.replace(/-/g, " "),
        permission,
        error: metadata.error || false,
        ...metadata,
      };
    });

  const shouldShowSearch = isSuperAdmin || organizationList.length > 5;

  const filteredOrganizationList =
    shouldShowSearch && searchQuery
      ? organizationList.filter((org) =>
          org.organization_name
            .toLowerCase()
            .includes(searchQuery.toLowerCase()),
        )
      : organizationList;

  const selectedOrgData = organizationList.find(
    (org) => org.organization_id === selectedOrganization,
  );

  const getAccountsByOrganizationIdFromLocal = (orgId: string) => {
    const orgAccounts: any[] = localOrgMetadata[orgId]?.accounts || [];
    const hasOrgAccess = orgId in orgsFromFirestore;
    if (!hasOrgAccess) return [];
    return orgAccounts
      .map((account) => ({
        account_id: account.account_id,
        account_name:
          account.account_name || account.account_id.replace(/-/g, " "),
        industry: account.industry || "Unknown",
        status: account.status || "Active",
        permission: orgsFromFirestore[orgId],
      }))
      .sort((a, b) => a.account_name.localeCompare(b.account_name));
  };

  const { availableAccounts } = useAvailableAccounts({
    selectedOrganization,
    selectedChildOrg,
    localOrgMetadata,
    childOrganizations,
    orgsFromFirestore,
    getAccountsByOrganizationIdFromLocal,
  });

  const handleOrganizationSelect = (orgId: string) => {
    if (orgId !== selectedOrganization) {
      setSelectedAccount("");
      setSelectedChildOrg("");
      clearChildOrganizations();
    }
    setSelectedOrganization(orgId);
  };

  const handleContinue = () => {
    if (!selectedOrganization || !selectedAccount) return;
    setIsLoading(true);
    continueTimerRef.current = setTimeout(() => {
      try {
        const resolution = resolveOrganizationAndAccount(
          selectedOrganization,
          selectedAccount,
          selectedChildOrg,
          localOrgMetadata,
          childOrganizations,
        );
        const metadata = formatWorkspaceMetadata(
          resolution.organization?.organization_name || selectedOrganization,
          resolution.account?.account_name || selectedAccount,
          resolution.account?.industry || "Unknown",
          resolution.account?.status || "Active",
          resolution.account?.timezone,
          resolution.organization?.plan,
        );
        setSelectedOrgAccount({
          orgId: resolution.organizationId,
          accountId: selectedAccount,
          metadata,
        });
        setCurrentOrganization(resolution.organizationId as OrganizationId);
        completeWorkspaceSelection();
        navigate("/");
      } catch (error) {
        // Without this catch, any throw inside the deferred callback would leave
        // isLoading=true forever, hanging the spinner with no recovery path.
        console.error("Failed to complete workspace selection", error);
        setIsLoading(false);
      }
    }, WORKSPACE_SELECTION_DELAY);
  };

  const handleGearIconClick = (e: React.MouseEvent, org: any) => {
    e.stopPropagation();
    const firstAccount = org.accounts?.[0];
    setSelectedOrgAccount({
      orgId: org.organization_id,
      accountId: firstAccount?.account_id || "",
      metadata: {
        organization_name: org.organization_name,
        account_name: firstAccount?.account_name || "",
        industry: firstAccount?.industry || "",
        status: firstAccount?.status || "Active",
        timezone: firstAccount?.timezone || "",
        plan: org.plan,
      },
    });
    setCurrentOrganization(org.organization_id as OrganizationId);
    completeWorkspaceSelection();
    navigate("/settings/organization");
  };

  if (isAuthLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 border-4 border-[var(--color-violet-500)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--color-text-secondary)]">Loading...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace />;
  }

  if (hasSelectedWorkspace) {
    return <Navigate to="/" replace />;
  }

  const isDataLoading = userDataFetchStatus === "loading";
  const hasFetchError = userDataFetchStatus === "error";

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <div className="w-full max-w-4xl animate-page-enter">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="mb-2 flex justify-center animate-logo-float">
            <Logo size="2xl" variant="icon" />
          </div>
          <h1 className="mb-2">Choose a workspace</h1>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Select the organization and account you want to work with.
          </p>
        </div>

        {/* Rainbow Accent Bar */}
        <div
          className="h-[3px] rounded-full mb-6 mx-auto w-[60%]"
          style={{ background: "var(--gradient-rainbow)" }}
        />

        {/* Two-column grid */}
        {isDataLoading ? (
          <div className="grid lg:grid-cols-2 gap-6 mb-8">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Organizations</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[var(--color-text-secondary)] py-6 text-center">
                  Loading organizations…
                </p>
              </CardContent>
            </Card>
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Accounts</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[var(--color-text-secondary)] py-6 text-center">
                  Select an organization to view its accounts.
                </p>
              </CardContent>
            </Card>
          </div>
        ) : hasFetchError ? (
          <Card className="shadow-lg mb-8">
            <CardContent className="py-10 text-center space-y-4">
              <p className="text-sm text-[var(--color-text-primary)]">
                We couldn't load your workspaces. Please try again.
              </p>
              <Button
                type="button"
                variant="outline"
                onClick={() => setUserDataFetchAttempt((n) => n + 1)}
              >
                Retry
              </Button>
              <p className="text-xs text-[var(--color-text-secondary)]">
                If the problem persists, contact{" "}
                <a
                  href="mailto:support@ken-e.com"
                  className="text-[var(--color-violet-600)] hover:underline"
                >
                  support@ken-e.com
                </a>
                .
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid lg:grid-cols-2 gap-6 mb-8">
            {/* Organizations card */}
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Organizations</CardTitle>
              </CardHeader>
              <CardContent>
                {shouldShowSearch && (
                  <div className="mb-3">
                    <Input
                      placeholder="Search organizations…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="text-sm"
                    />
                  </div>
                )}
                <div className="space-y-2 mb-4">
                  {filteredOrganizationList.map((org) => (
                    <div
                      key={org.organization_id}
                      role="button"
                      tabIndex={0}
                      aria-pressed={
                        selectedOrganization === org.organization_id
                      }
                      onClick={() =>
                        handleOrganizationSelect(org.organization_id)
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleOrganizationSelect(org.organization_id);
                        }
                      }}
                      className={cn(
                        "flex items-center justify-between p-3 rounded-[var(--radius-md)] border-2 cursor-pointer transition-all duration-200 hover:-translate-y-0.5",
                        selectedOrganization === org.organization_id
                          ? "border-[var(--color-violet-500)] bg-[var(--color-violet-100)]/40"
                          : "border-[var(--color-border-default)] hover:border-[var(--color-violet-300)]",
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-sm font-medium text-[var(--color-text-primary)]">
                            {org.organization_name}
                          </p>
                          {org.error && (
                            <Badge variant="destructive" className="text-xs">
                              Error Loading
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-[var(--color-text-secondary)]">
                          {org.plan || org.permission}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {selectedOrganization === org.organization_id && (
                          <Check
                            className="size-4 text-[var(--color-violet-500)]"
                            aria-hidden="true"
                          />
                        )}
                        <button
                          type="button"
                          aria-label="Organization settings"
                          onClick={(e) => handleGearIconClick(e, org)}
                          className="p-1 rounded hover:bg-[var(--color-violet-100)]/60 transition-colors"
                        >
                          <Settings
                            className="size-4 text-[var(--color-text-secondary)]"
                            aria-hidden="true"
                          />
                          <span className="sr-only">Organization settings</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full gap-2"
                  onClick={() => navigate("/create-organization")}
                >
                  <Plus className="size-4" />
                  Create new organization
                </Button>
              </CardContent>
            </Card>

            {/* Accounts card */}
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Accounts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 mb-4">
                  {availableAccounts.length > 0 ? (
                    availableAccounts.map((account) => (
                      <div
                        key={account.account_id}
                        role="button"
                        tabIndex={0}
                        aria-pressed={selectedAccount === account.account_id}
                        onClick={() => setSelectedAccount(account.account_id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedAccount(account.account_id);
                          }
                        }}
                        className={cn(
                          "flex items-center justify-between p-3 rounded-[var(--radius-md)] border-2 cursor-pointer transition-all duration-200 hover:-translate-y-0.5",
                          selectedAccount === account.account_id
                            ? "border-[var(--color-violet-500)] bg-[var(--color-violet-100)]/40"
                            : "border-[var(--color-border-default)] hover:border-[var(--color-violet-300)]",
                        )}
                      >
                        <p className="text-sm font-medium text-[var(--color-text-primary)]">
                          {account.account_name}
                        </p>
                        {selectedAccount === account.account_id && (
                          <Check
                            className="size-4 text-[var(--color-violet-500)] shrink-0"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-[var(--color-text-secondary)] py-6 text-center">
                      {selectedOrganization
                        ? "No accounts found for this organization."
                        : "Select an organization to view its accounts."}
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full gap-2"
                  disabled={!selectedOrganization}
                  onClick={() => {
                    if (!selectedOrganization) return;
                    setCurrentOrganization(
                      selectedOrganization as OrganizationId,
                    );
                    completeWorkspaceSelection();
                    navigate("/settings/organization?openCreateAccount=true");
                  }}
                >
                  <Plus className="size-4" />
                  Create new account
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Continue button */}
        <div className="flex justify-center">
          <Button
            type="button"
            disabled={
              !selectedOrganization ||
              !selectedAccount ||
              isLoading ||
              !!(selectedOrgData?.agency && !selectedChildOrg)
            }
            onClick={handleContinue}
            className="gap-2 bg-[var(--color-cta-coral)] hover:bg-[var(--color-cta-coral-hover)] shadow-[var(--shadow-color-coral)] text-[var(--color-text-inverse)] border-0 transition-all duration-200 hover:-translate-y-0.5"
          >
            {isLoading ? (
              <>
                <div className="size-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Setting up workspace…
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="size-4" />
              </>
            )}
          </Button>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Need help?{" "}
            <a
              href="mailto:support@ken-e.com"
              className="text-[var(--color-violet-600)] hover:underline transition-colors"
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>

      <style>{`
        @keyframes page-enter {
          from {
            opacity: 0;
            transform: translateY(40px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes logo-float {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-12px);
          }
        }

        .animate-page-enter {
          animation: page-enter 600ms cubic-bezier(0.175, 0.885, 0.32, 1.1);
        }

        .animate-logo-float {
          animation: logo-float 6s ease-in-out infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .animate-page-enter,
          .animate-logo-float {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}

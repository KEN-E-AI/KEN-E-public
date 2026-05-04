import { useState } from "react";
import { Check, Plus, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Logo } from "@/components/branding/Logo";
import { cn } from "@/lib/utils";

type PlaceholderOrg = {
  id: string;
  name: string;
  plan: string;
};

type PlaceholderAccount = {
  id: string;
  name: string;
  orgId: string;
};

const PLACEHOLDER_ORGS: PlaceholderOrg[] = [
  { id: "org-1", name: "Acme Corporation", plan: "Pro" },
  { id: "org-2", name: "Globex Ventures", plan: "Starter" },
];

const PLACEHOLDER_ACCOUNTS: PlaceholderAccount[] = [
  { id: "acc-1", name: "Main Account", orgId: "org-1" },
  { id: "acc-2", name: "EMEA Account", orgId: "org-1" },
];

export default function SelectOrganizationPage() {
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(
    null,
  );

  const visibleAccounts = PLACEHOLDER_ACCOUNTS.filter(
    (a) => a.orgId === selectedOrgId,
  );

  function handleOrgSelect(orgId: string) {
    setSelectedOrgId(orgId);
    setSelectedAccountId(null);
  }

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
        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* Organizations card */}
          <Card className="hover:translate-y-0 hover:border-[var(--color-border-default)] shadow-lg">
            <CardHeader>
              <CardTitle>Organizations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 mb-4">
                {PLACEHOLDER_ORGS.map((org) => (
                  <div
                    key={org.id}
                    role="button"
                    tabIndex={0}
                    aria-pressed={selectedOrgId === org.id}
                    onClick={() => handleOrgSelect(org.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleOrgSelect(org.id);
                      }
                    }}
                    className={cn(
                      "flex items-center justify-between p-3 rounded-[var(--radius-md)] border-2 cursor-pointer transition-all duration-200 hover:-translate-y-0.5",
                      selectedOrgId === org.id
                        ? "border-[var(--color-violet-500)] bg-[var(--color-violet-100)]/40"
                        : "border-[var(--color-border-default)] hover:border-[var(--color-violet-300)]",
                    )}
                  >
                    <div>
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">
                        {org.name}
                      </p>
                      <p className="text-xs text-[var(--color-text-secondary)]">
                        {org.plan}
                      </p>
                    </div>
                    {selectedOrgId === org.id && (
                      <Check
                        className="size-4 text-[var(--color-violet-500)] shrink-0"
                        aria-hidden="true"
                      />
                    )}
                  </div>
                ))}
              </div>
              <Button type="button" variant="outline" className="w-full gap-2">
                <Plus className="size-4" />
                Create new organization
              </Button>
            </CardContent>
          </Card>

          {/* Accounts card */}
          <Card className="hover:translate-y-0 hover:border-[var(--color-border-default)] shadow-lg">
            <CardHeader>
              <CardTitle>Accounts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 mb-4">
                {selectedOrgId && visibleAccounts.length > 0 ? (
                  visibleAccounts.map((account) => (
                    <div
                      key={account.id}
                      role="button"
                      tabIndex={0}
                      aria-pressed={selectedAccountId === account.id}
                      onClick={() => setSelectedAccountId(account.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedAccountId(account.id);
                        }
                      }}
                      className={cn(
                        "flex items-center justify-between p-3 rounded-[var(--radius-md)] border-2 cursor-pointer transition-all duration-200 hover:-translate-y-0.5",
                        selectedAccountId === account.id
                          ? "border-[var(--color-violet-500)] bg-[var(--color-violet-100)]/40"
                          : "border-[var(--color-border-default)] hover:border-[var(--color-violet-300)]",
                      )}
                    >
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">
                        {account.name}
                      </p>
                      {selectedAccountId === account.id && (
                        <Check
                          className="size-4 text-[var(--color-violet-500)] shrink-0"
                          aria-hidden="true"
                        />
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--color-text-secondary)] py-6 text-center">
                    {selectedOrgId
                      ? "No accounts found for this organization."
                      : "Select an organization to view its accounts."}
                  </p>
                )}
              </div>
              <Button type="button" variant="outline" className="w-full gap-2">
                <Plus className="size-4" />
                Create new account
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Continue button */}
        <div className="flex justify-center">
          <Button
            type="button"
            disabled={!(selectedOrgId && selectedAccountId)}
            className="gap-2 bg-[var(--color-cta-coral)] hover:bg-[var(--color-cta-coral-hover)] shadow-[var(--shadow-color-coral)] text-white border-0 transition-all duration-200 hover:-translate-y-0.5"
          >
            Continue
            <ArrowRight className="size-4" />
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

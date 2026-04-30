import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { CustomerProfilesManagement } from "@/components/customers/CustomerProfilesManagement";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

const Customers = () => {
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);

  const { selectedOrgAccount, user, isSuperAdmin } = useAuth();

  const hasEditAccess = useMemo(() => {
    if (!selectedOrgAccount) return false;
    if (isSuperAdmin) return true;

    const accountId = selectedOrgAccount.accountId;
    const orgId = selectedOrgAccount.orgId;

    const orgRole = user?.permissions?.organizations?.[orgId];
    if (orgRole === "admin" || orgRole === "owner") return true;

    const accountPerm =
      user?.permissions?.account_permissions?.[accountId] ||
      user?.permissions?.accounts?.[accountId]; // Fallback for backward compatibility
    return accountPerm === "edit" || accountPerm === "admin";
  }, [selectedOrgAccount, user, isSuperAdmin]);

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Customers</h1>
      </header>
      <div className="space-y-6">
        {/* Back to Knowledge Base Link */}
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/knowledge")}
            className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal mr-auto"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </Button>
        </div>

        <CustomerProfilesManagement hasEditAccess={hasEditAccess} />
      </div>
    </>
  );
};

export default Customers;

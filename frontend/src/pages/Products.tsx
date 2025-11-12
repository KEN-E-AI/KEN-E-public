import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { useAuth } from "@/contexts/AuthContext";
import { ProductCategoriesManagement } from "@/components/products/ProductCategoriesManagement";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

const Products = () => {
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
      user?.permissions?.accounts?.[accountId] ||
      user?.permissions?.[accountId];
    return accountPerm === "edit" || accountPerm === "admin";
  }, [selectedOrgAccount, user, isSuperAdmin]);

  return (
    <Layout
      pageTitle="Products and Services"
      selectedTab="Products"
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
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

        <ProductCategoriesManagement hasEditAccess={hasEditAccess} />
      </div>
    </Layout>
  );
};

export default Products;

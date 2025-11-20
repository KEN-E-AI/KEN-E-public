import type { SelectedOrgAccount } from "@/contexts/AuthContext";

interface GlobalHeaderProps {
  pageTitle?: string;
  dateRange: { from: Date; to: Date };
  setDateRange: (range: { from: Date; to: Date }) => void;
  comparisonDateRange?: { from: Date; to: Date };
  setComparisonDateRange?: (range: { from: Date; to: Date }) => void;
  selectedOrgAccount: SelectedOrgAccount | null;
  setSelectedOrgAccount: (account: SelectedOrgAccount) => void;
}

const GlobalHeader = ({
  pageTitle = "Marketing Strategies",
}: GlobalHeaderProps) => {
  return (
    <h1 className="text-2xl font-semibold text-dashboard-gray-900 mb-6">
      {pageTitle}
    </h1>
  );
};

export default GlobalHeader;

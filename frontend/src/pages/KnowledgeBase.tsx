import { useState } from "react";
import Layout from "@/components/layout/Layout";
import MetricsPage from "@/components/knowledge-base/MetricsPage";
import ActivitiesPage from "@/components/knowledge-base/ActivitiesPage";
import InsightsPage from "@/components/knowledge-base/InsightsPage";
import AccountOverviewPage from "@/components/knowledge-base/AccountOverviewPage";
import CustomersPage from "@/components/knowledge-base/CustomersPage";
import CompetitorsPage from "@/components/knowledge-base/CompetitorsPage";

const KnowledgeBase = () => {
  const [selectedPage, setSelectedPage] = useState("metrics");

  const renderContent = () => {
    switch (selectedPage) {
      case "metrics":
        return <MetricsPage />;
      case "activities":
        return <ActivitiesPage />;
      case "insights":
        return <InsightsPage />;
      case "account-overview":
        return <AccountOverviewPage />;
      case "customers":
        return <CustomersPage />;
      case "competitors":
        return <CompetitorsPage />;
      default:
        return <MetricsPage />;
    }
  };

  return (
    <Layout
      pageType="knowledge-base"
      selectedKnowledgePage={selectedPage}
      onKnowledgePageChange={setSelectedPage}
    >
      {/* Knowledge Base Content */}
      <div className="p-3 sm:p-6">{renderContent()}</div>
    </Layout>
  );
};

export default KnowledgeBase;

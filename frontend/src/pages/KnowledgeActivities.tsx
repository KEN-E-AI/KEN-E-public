import Layout from "@/components/layout/Layout";
import { ActivitiesConfiguration } from "@/components/configuration";

const KnowledgeActivities = () => {

  return (
    <Layout pageTitle="Activities Configuration">
      <div className="space-y-6">
        {/* Activities Page Content */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
          <ActivitiesConfiguration />
        </div>
      </div>
    </Layout>
  );
};

export default KnowledgeActivities;

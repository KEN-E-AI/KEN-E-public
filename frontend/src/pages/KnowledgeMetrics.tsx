import Layout from "@/components/layout/Layout";
import { MetricsConfiguration } from "@/components/configuration";

const KnowledgeMetrics = () => {

  return (
    <Layout pageTitle="Metrics Configuration">
      <div className="space-y-6">
        {/* Metrics Page Content */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
          <MetricsConfiguration />
        </div>
      </div>
    </Layout>
  );
};

export default KnowledgeMetrics;

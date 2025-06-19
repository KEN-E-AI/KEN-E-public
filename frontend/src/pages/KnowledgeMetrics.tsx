import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { MetricsConfiguration } from "@/components/configuration";

const KnowledgeMetrics = () => {
  const navigate = useNavigate();

  return (
    <Layout pageTitle="Metrics Configuration">
      <div className="space-y-6">
        {/* Back Navigation */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate("/knowledge")}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Knowledge Configuration
          </Button>
        </div>

        {/* Metrics Page Content */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
          <MetricsConfiguration />
        </div>
      </div>
    </Layout>
  );
};

export default KnowledgeMetrics;

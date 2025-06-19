import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { ActivitiesConfiguration } from "@/components/configuration";

const KnowledgeActivities = () => {
  const navigate = useNavigate();

  return (
    <Layout pageTitle="Activities Configuration">
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

        {/* Activities Page Content */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
          <ActivitiesConfiguration />
        </div>
      </div>
    </Layout>
  );
};

export default KnowledgeActivities;

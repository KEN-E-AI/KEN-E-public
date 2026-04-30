import { useNavigate } from "react-router-dom";
import { ActivitiesConfiguration } from "@/components/configuration";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

const KnowledgeActivities = () => {
  const navigate = useNavigate();

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Activities Configuration</h1>
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

        {/* Activities Page Content */}
        <div className="bg-white rounded-lg border border-dashboard-gray-200 p-6">
          <ActivitiesConfiguration />
        </div>
      </div>
    </>
  );
};

export default KnowledgeActivities;

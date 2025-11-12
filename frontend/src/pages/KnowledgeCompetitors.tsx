import { useNavigate } from "react-router-dom";
import CompetitorsConfiguration from "@/components/configuration/CompetitorsConfiguration";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function KnowledgeCompetitors() {
  const navigate = useNavigate();

  return (
    <Layout pageTitle="Competitor Knowledge" maxWidth={false}>
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

        <p className="text-muted-foreground">
          Track your competitors' mentions and activities in news and social
          media.
        </p>

        <CompetitorsConfiguration />
      </div>
    </Layout>
  );
}

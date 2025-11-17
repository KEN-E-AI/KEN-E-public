import { useNavigate } from "react-router-dom";
import CustomerKeywordsConfiguration from "@/components/configuration/CustomerKeywordsConfiguration";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function KnowledgeCustomers() {
  const navigate = useNavigate();

  return (
    <Layout pageTitle="Customer Knowledge" maxWidth={false}>
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
          Manage keywords related to your customers for targeted monitoring.
        </p>

        <CustomerKeywordsConfiguration />
      </div>
    </Layout>
  );
}

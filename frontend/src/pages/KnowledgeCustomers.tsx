import { useNavigate } from "react-router-dom";
import CustomerKeywordsConfiguration from "@/components/configuration/CustomerKeywordsConfiguration";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function KnowledgeCustomers() {
  const navigate = useNavigate();

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Customer Knowledge</h1>
      </header>
      <div className="space-y-6">
        {/* Back to Knowledge Base Link */}
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/knowledge")}
            className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] p-0 h-auto font-normal mr-auto"
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
    </>
  );
}

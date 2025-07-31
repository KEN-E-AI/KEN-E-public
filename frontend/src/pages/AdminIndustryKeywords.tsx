import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { IndustryKeywordsSettings } from "@/components/settings/admin/IndustryKeywordsSettings";

const AdminIndustryKeywords = () => {
  const navigate = useNavigate();
  const { isSuperAdmin } = useAuth();

  // Redirect non-super admins
  if (!isSuperAdmin) {
    navigate("/settings");
    return null;
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/settings/admin")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Industry Keywords</h1>
          <p className="text-muted-foreground">
            Manage keywords that are automatically applied to accounts based on their industry
          </p>
        </div>
      </div>

      {/* Industry Keywords Component */}
      <IndustryKeywordsSettings />
    </div>
  );
};

export default AdminIndustryKeywords;
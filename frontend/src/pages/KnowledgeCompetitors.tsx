import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { CompetitorsManagement } from "@/components/competitors/CompetitorsManagement";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ArrowLeft, Info, Pencil, Loader2, Swords } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import {
  useCompetitiveEnvironment,
  useUpdateCompetitiveEnvironment,
} from "@/queries/competitors";

export default function KnowledgeCompetitors() {
  const navigate = useNavigate();
  const { selectedOrgAccount, user, isSuperAdmin } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing] = useState(false);
  const [
    competitiveEnvironmentDescription,
    setCompetitiveEnvironmentDescription,
  ] = useState("");
  const [originalDescription, setOriginalDescription] = useState("");

  // Fetch competitive environment
  const { data: competitiveEnvironment, isLoading: isLoadingEnvironment } =
    useCompetitiveEnvironment(selectedOrgAccount?.accountId || null);

  const updateEnvironmentMutation = useUpdateCompetitiveEnvironment();

  // Permissions logic
  const hasEditAccess = useMemo(() => {
    if (!selectedOrgAccount) return false;
    if (isSuperAdmin) return true;

    const accountId = selectedOrgAccount.accountId;
    const orgId = selectedOrgAccount.orgId;

    const orgRole = user?.permissions?.organizations?.[orgId];
    if (orgRole === "admin" || orgRole === "owner") return true;

    const accountPerm =
      user?.permissions?.account_permissions?.[accountId] ||
      user?.permissions?.accounts?.[accountId];
    return accountPerm === "edit" || accountPerm === "admin";
  }, [selectedOrgAccount, user, isSuperAdmin]);

  const currentDescription = competitiveEnvironment?.description || "";

  const handleEdit = () => {
    setCompetitiveEnvironmentDescription(currentDescription);
    setOriginalDescription(currentDescription);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!selectedOrgAccount?.accountId) return;

    try {
      await updateEnvironmentMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        updates: {
          description: competitiveEnvironmentDescription,
        },
      });

      queryClient.invalidateQueries({
        queryKey: ["competitive-environment", selectedOrgAccount.accountId],
      });

      toast({
        title: "Success",
        description: "Competitive environment updated successfully",
      });

      setIsEditing(false);
    } catch (error: any) {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail ||
          "Failed to update competitive environment",
        variant: "destructive",
      });
    }
  };

  const handleCancel = () => {
    setCompetitiveEnvironmentDescription(originalDescription);
    setIsEditing(false);
  };

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Competitor Knowledge</h1>
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

        {/* Competitive Environment Card */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle className="flex items-center gap-2">
                <Swords className="h-5 w-5" />
                Competitive Environment
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Define the competitive landscape and strategy for
                        identifying key competitors. This includes factors like
                        geography, market segment, brand positioning, and
                        product substitutability.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
              {hasEditAccess && (
                <Button
                  onClick={handleEdit}
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingEnvironment ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {currentDescription ||
                  "No competitive environment description yet. Click the pencil icon to add one."}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Competitors Management */}
        <CompetitorsManagement hasEditAccess={hasEditAccess} />

        {/* Edit Sheet */}
        <Sheet open={isEditing} modal={false} onOpenChange={setIsEditing}>
          <SheetContent side="right" className="w-[25rem] flex flex-col">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Swords className="h-5 w-5" />
                Edit Competitive Environment
              </SheetTitle>
            </SheetHeader>

            <div className="flex-1 mt-6 overflow-y-auto">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="competitive-environment-description">
                    Description
                  </Label>
                  <Textarea
                    id="competitive-environment-description"
                    value={competitiveEnvironmentDescription}
                    onChange={(e) =>
                      setCompetitiveEnvironmentDescription(e.target.value)
                    }
                    placeholder="Describe the competitive landscape, key factors for identifying competitors, target markets, and strategic positioning..."
                    className="min-h-[12.5rem]"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t">
              <Button
                variant="outline"
                onClick={handleCancel}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={updateEnvironmentMutation.isPending}
                className="flex-1"
              >
                {updateEnvironmentMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Save
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}

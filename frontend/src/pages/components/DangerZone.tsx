import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle, Trash2 } from "lucide-react";
import { type Organization } from "@/data/organizationTypes";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import { deleteOrganization } from "@/data/organizationApi";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";

interface DangerZoneProps {
  orgData: Organization;
}

const DangerZone = ({ orgData }: DangerZoneProps) => {
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const { toast } = useToast();
  const { user, updateUser, setOrgMetadata, orgMetadata } = useAuth();
  const navigate = useNavigate();

  const handleDeleteOrganization = () => {
    setIsDeleteDialogOpen(true);
  };

  const updateUserPermissionsAfterDeletion = (organizationId: string) => {
    if (user?.permissions?.organizations) {
      const newOrgPermissions = { ...user.permissions.organizations };
      delete newOrgPermissions[organizationId];
      updateUser({
        permissions: {
          ...user.permissions,
          organizations: newOrgPermissions,
        },
      });
    }
  };

  const updateOrgMetadataAfterDeletion = (organizationId: string) => {
    const newOrgMetadata = { ...orgMetadata };
    delete newOrgMetadata[organizationId];
    setOrgMetadata(newOrgMetadata);
  };

  const showSuccessMessageAndNavigate = (organizationName: string) => {
    setIsDeleteDialogOpen(false);

    toast({
      title: "Organization Deleted",
      description: `"${organizationName}" and all associated accounts have been permanently deleted.`,
    });

    navigate("/organization-selection");
  };

  const handleDeletionError = (error: any) => {
    console.error("[DangerZone] Error deleting organization:", error);

    const errorDetail =
      error.response?.data?.detail ||
      error.message ||
      "Failed to delete organization";

    // Check if the error is about accounts needing to be deleted first
    if (
      error.response?.status === 400 &&
      errorDetail.includes("associated accounts")
    ) {
      toast({
        title: "Cannot Delete Organization",
        description:
          "You must delete all accounts first before deleting this organization. Please remove accounts from the Accounts section above.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Error",
        description: `Error: ${errorDetail}`,
        variant: "destructive",
      });
    }
  };

  const confirmDeleteOrganization = async () => {
    try {
      console.log(
        "[DangerZone] Deleting organization:",
        orgData.organization_id,
      );

      // Delete organization from Neo4j
      await deleteOrganization(orgData.organization_id);

      // Update local state
      updateUserPermissionsAfterDeletion(orgData.organization_id);
      updateOrgMetadataAfterDeletion(orgData.organization_id);

      // Show success and navigate
      showSuccessMessageAndNavigate(orgData.organization_name);

      console.log("[DangerZone] Organization deleted successfully");
    } catch (error: any) {
      handleDeletionError(error);
    }
  };

  return (
    <>
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Danger Zone
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="text-red-600 mr-auto">
                Cancel Subscription
              </Label>
              <p className="text-sm text-dashboard-gray-600">
                Cancel your subscription and downgrade to free plan
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="text-red-600 border-red-200 hover:bg-red-50"
            >
              Cancel Subscription
            </Button>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="text-red-600 mr-auto">
                Delete Organization
              </Label>
              <p className="text-sm text-dashboard-gray-600">
                Permanently delete your organization (requires all accounts to
                be deleted first)
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteOrganization}
            >
              Delete Organization
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Delete Organization Confirmation Dialog */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5 text-red-600" />
              Delete Organization
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <div>
                  Are you sure you want to delete the organization{" "}
                  <span className="font-semibold">
                    "{orgData.organization_name}"
                  </span>
                  ?
                </div>
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                  <div className="text-sm text-amber-800 font-medium">
                    📋 Required: You must delete all accounts first
                  </div>
                  <div className="text-sm text-amber-700 mt-1">
                    Before deleting this organization, please remove all accounts
                    from the Accounts section above. This ensures you understand
                    exactly what data will be lost.
                  </div>
                </div>
                <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                  <div className="text-sm text-red-800 font-medium">
                    ⚠️ Warning: This action cannot be undone
                  </div>
                  <div className="text-sm text-red-700 mt-1">
                    Deleting this organization will permanently remove all
                    associated data, reports, and settings.
                  </div>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setIsDeleteDialogOpen(false);
              }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteOrganization}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              Delete Organization
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default DangerZone;

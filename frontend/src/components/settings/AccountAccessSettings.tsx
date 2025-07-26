import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Users, Plus, Shield, Trash2, Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  getAccountPermissions,
  grantAccountAccess,
  revokeAccountAccess,
  getOrganizationMembers,
} from "@/data/teamApi";

interface AccountAccessSettingsProps {
  accountId: string;
  onUpdate?: (updates: any) => void;
}

interface AccountPermission {
  user_id: string;
  email: string;
  access_level: string;
  first_name?: string;
  last_name?: string;
}

export const AccountAccessSettings = ({
  accountId,
  onUpdate,
}: AccountAccessSettingsProps) => {
  const { toast } = useToast();
  const { user, selectedOrgAccount } = useAuth();
  const [permissions, setPermissions] = useState<AccountPermission[]>([]);
  const [orgMembers, setOrgMembers] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGrantModalOpen, setIsGrantModalOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedAccessLevel, setSelectedAccessLevel] = useState<"edit" | "view">("view");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load account permissions
  useEffect(() => {
    const loadData = async () => {
      if (!accountId || !user?.id) return;

      setIsLoading(true);
      try {
        // Load account permissions
        const permResponse = await getAccountPermissions(accountId);
        setPermissions(permResponse.permissions);

        // Load organization members to show who can be granted access
        if (selectedOrgAccount?.orgId) {
          const membersResponse = await getOrganizationMembers(
            selectedOrgAccount.orgId,
            user.id
          );
          setOrgMembers(membersResponse.members);
        }
      } catch (error) {
        console.error("[AccountAccessSettings] Error loading data:", error);
        toast({
          title: "Error",
          description: "Failed to load access permissions",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [accountId, user?.id, selectedOrgAccount?.orgId, toast]);

  // Filter available users (org members who don't already have access)
  const availableUsers = orgMembers.filter(
    (member) => !permissions.some((perm) => perm.user_id === member.user_id)
  );

  const handleGrantAccess = async () => {
    if (!selectedUserId || !accountId) return;

    setIsSubmitting(true);
    try {
      await grantAccountAccess(accountId, selectedUserId, selectedAccessLevel);

      // Reload permissions
      const response = await getAccountPermissions(accountId);
      setPermissions(response.permissions);

      setIsGrantModalOpen(false);
      setSelectedUserId("");
      setSelectedAccessLevel("view");

      toast({
        title: "Success",
        description: "Access granted successfully",
      });

      if (onUpdate) {
        onUpdate({ permissions: response.permissions });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to grant access",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevokeAccess = async (userId: string, userEmail: string) => {
    // Show confirmation
    toast({
      title: "Revoke Access",
      description: `Are you sure you want to revoke ${userEmail}'s access to this account?`,
      action: (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Dismiss
            }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={async () => {
              try {
                await revokeAccountAccess(accountId, userId);

                // Reload permissions
                const response = await getAccountPermissions(accountId);
                setPermissions(response.permissions);

                toast({
                  title: "Success",
                  description: `Revoked access for ${userEmail}`,
                });

                if (onUpdate) {
                  onUpdate({ permissions: response.permissions });
                }
              } catch (error) {
                toast({
                  title: "Error",
                  description: "Failed to revoke access",
                  variant: "destructive",
                });
              }
            }}
          >
            Revoke Access
          </Button>
        </div>
      ),
    });
  };

  // Check if current user can manage access (needs admin org permission)
  const canManageAccess =
    user?.permissions?.organizations?.[selectedOrgAccount?.orgId || ""] === "admin";

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Account Access Control
            </div>
            {canManageAccess && availableUsers.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsGrantModalOpen(true)}
                className="h-8 px-3"
              >
                <Plus className="h-4 w-4 mr-1" />
                Grant Access
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-gray-600">
            <p>
              Control who has access to this account. Users with organization-level admin
              permissions automatically have edit access to all accounts.
            </p>
          </div>

          {isLoading ? (
            <div className="text-center py-8 text-gray-500">
              <p>Loading access permissions...</p>
            </div>
          ) : permissions.length > 0 ? (
            <div className="space-y-3">
              {permissions.map((permission) => (
                <div
                  key={permission.user_id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-brand-light-blue/20 rounded-full flex items-center justify-center">
                      <Mail className="h-5 w-5 text-brand-medium-blue" />
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">
                        {permission.email}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        {permission.first_name && permission.last_name && (
                          <span className="text-sm text-gray-600">
                            {permission.first_name} {permission.last_name}
                          </span>
                        )}
                        <Badge variant="outline">
                          <Shield className="h-3 w-3 mr-1" />
                          {permission.access_level}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  {canManageAccess && permission.user_id !== user?.id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleRevokeAccess(permission.user_id, permission.email)
                      }
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Users className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No specific account permissions granted</p>
              <p className="text-sm mt-2">
                Organization admins have automatic access to all accounts
              </p>
            </div>
          )}

          {!canManageAccess && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-800">
                You need organization admin permissions to manage account access
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Grant Access Modal */}
      <Dialog open={isGrantModalOpen} onOpenChange={setIsGrantModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Grant Account Access</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="grant-user">Select User</Label>
              <Select
                value={selectedUserId}
                onValueChange={setSelectedUserId}
              >
                <SelectTrigger id="grant-user">
                  <SelectValue placeholder="Choose a user" />
                </SelectTrigger>
                <SelectContent>
                  {availableUsers.map((member) => (
                    <SelectItem key={member.user_id} value={member.user_id}>
                      {member.email}
                      {member.first_name && member.last_name && (
                        <span className="text-gray-500 ml-2">
                          ({member.first_name} {member.last_name})
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="grant-access">Access Level</Label>
              <Select
                value={selectedAccessLevel}
                onValueChange={(value) =>
                  setSelectedAccessLevel(value as "edit" | "view")
                }
              >
                <SelectTrigger id="grant-access">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="view">
                    View - Can view account data
                  </SelectItem>
                  <SelectItem value="edit">
                    Edit - Can modify account settings
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsGrantModalOpen(false);
                  setSelectedUserId("");
                  setSelectedAccessLevel("view");
                }}
                className="flex-1"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleGrantAccess}
                className="flex-1"
                disabled={isSubmitting || !selectedUserId}
              >
                {isSubmitting ? "Granting..." : "Grant Access"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
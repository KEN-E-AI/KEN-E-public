import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDialogFix } from "@/hooks/useDialogFix";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { Users, Plus, MoreVertical, Mail, Shield, Trash2, Settings } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { type Organization, type Account } from "@/data/organizationTypes";
import {
  getOrganizationMembers,
  inviteMemberToOrganization,
  updateMemberAccessLevel,
  removeMemberFromOrganization,
  getOrganizationInvitations,
  cancelInvitation,
  grantAccountAccess,
  revokeAccountAccess,
  type TeamMember,
  type Invitation,
} from "@/data/teamApi";
import { useAccounts } from "@/queries/accounts";
import { useAuth } from "@/contexts/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface TeamManagementProps {
  orgData: Organization;
}

const TeamManagement = ({ orgData }: TeamManagementProps) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();
  
  // Fix for dialog-related freezing issues
  useDialogFix();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [isLoadingMembers, setIsLoadingMembers] = useState(true);
  const [isLoadingInvitations, setIsLoadingInvitations] = useState(true);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);
  const [isEditAccessModalOpen, setIsEditAccessModalOpen] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<TeamMember | null>(null);
  const [invitationToCancel, setInvitationToCancel] = useState<Invitation | null>(null);

  // Form states
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteAccessLevel, setInviteAccessLevel] = useState<"admin" | "view">(
    "view",
  );
  const [inviteAccountPermissions, setInviteAccountPermissions] = useState<
    Record<string, "edit" | "view">
  >({});
  const [editAccessLevel, setEditAccessLevel] = useState<"admin" | "view">(
    "view",
  );
  const [editAccountPermissions, setEditAccountPermissions] = useState<
    Record<string, "edit" | "view">
  >({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Check if current user can manage team (admin or owner)
  const canManageTeam =
    user?.permissions?.organizations?.[orgData.organization_id] === "admin" ||
    user?.permissions?.organizations?.[orgData.organization_id] === "owner";

  // Fetch accounts for the organization
  const { data: accounts = [] } = useAccounts(orgData.organization_id);

  // Load team members and invitations
  useEffect(() => {
    const loadData = async () => {
      if (!orgData.organization_id || !user?.id) return;

      // Load members
      setIsLoadingMembers(true);
      try {
        const response = await getOrganizationMembers(
          orgData.organization_id,
          user.id,
        );
        setMembers(response.members);
      } catch (error) {
        console.error("[TeamManagement] Error loading members:", error);
        toast({
          title: "Error",
          description: "Failed to load team members. Please try again.",
          variant: "destructive",
        });
      } finally {
        setIsLoadingMembers(false);
      }

      // Load pending invitations if user can manage team
      if (canManageTeam) {
        setIsLoadingInvitations(true);
        try {
          const response = await getOrganizationInvitations(
            orgData.organization_id,
            user.id,
            "pending",
          );
          setInvitations(response.invitations);
        } catch (error) {
          console.error("[TeamManagement] Error loading invitations:", error);
        } finally {
          setIsLoadingInvitations(false);
        }
      }
    };

    loadData();
  }, [orgData.organization_id, user?.id, canManageTeam, toast]);

  const handleInviteMember = async () => {
    if (!inviteEmail || !orgData.organization_id) {
      toast({
        title: "Error",
        description: "Please enter an email address",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      await inviteMemberToOrganization(
        orgData.organization_id,
        {
          email: inviteEmail,
          access_level: inviteAccessLevel,
          account_permissions: inviteAccessLevel === "view" ? inviteAccountPermissions : undefined,
        },
        user!.id,
        `${user!.firstName} ${user!.lastName}`.trim() || user!.email,
        orgData.organization_name,
      );

      // Reload members
      const response = await getOrganizationMembers(
        orgData.organization_id,
        user!.id,
      );
      setMembers(response.members);

      setIsInviteModalOpen(false);
      setInviteEmail("");
      setInviteAccessLevel("view");
      setInviteAccountPermissions({});

      toast({
        title: "Success",
        description: `Invitation sent to ${inviteEmail}`,
      });

      // Reload invitations
      if (canManageTeam) {
        try {
          const invitationsResponse = await getOrganizationInvitations(
            orgData.organization_id,
            user.id,
            "pending",
          );
          setInvitations(invitationsResponse.invitations);
        } catch (error) {
          console.error("[TeamManagement] Error reloading invitations:", error);
        }
      }
    } catch (error: any) {
      let errorMessage = "Failed to invite member";

      if (error.response?.status === 404) {
        errorMessage = `User with email ${inviteEmail} not found. The user must have an existing account in the system.`;
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateAccess = async () => {
    if (!selectedMember || !orgData.organization_id || !user?.id) return;

    console.log("[TeamManagement] Starting handleUpdateAccess", {
      selectedMember,
      editAccessLevel,
      editAccountPermissions,
    });

    setIsSubmitting(true);
    try {
      // Update organization access level
      console.log("[TeamManagement] Updating member access level...");
      await updateMemberAccessLevel(
        orgData.organization_id,
        selectedMember.user_id,
        { access_level: editAccessLevel },
        user.id,
      );

      // Handle account permissions for view-role users
      if (editAccessLevel === "view") {
        const currentPermissions = selectedMember.account_permissions || {};
        
        // Revoke access from accounts that were removed
        for (const accountId of Object.keys(currentPermissions)) {
          if (!editAccountPermissions[accountId]) {
            console.log(`[TeamManagement] Revoking access from account ${accountId}`);
            await revokeAccountAccess(accountId, selectedMember.user_id);
          }
        }
        
        // Grant or update access for accounts in editAccountPermissions
        for (const [accountId, accessLevel] of Object.entries(editAccountPermissions)) {
          if (currentPermissions[accountId] !== accessLevel) {
            console.log(`[TeamManagement] Granting ${accessLevel} access to account ${accountId}`);
            await grantAccountAccess(accountId, selectedMember.user_id, accessLevel);
          }
        }
      }

      console.log("[TeamManagement] Updating local state...");
      // Update local state
      setMembers(
        members.map((m) =>
          m.user_id === selectedMember.user_id
            ? { 
                ...m, 
                access_level: editAccessLevel,
                account_permissions: editAccessLevel === "view" ? editAccountPermissions : {}
              }
            : m,
        ),
      );

      console.log("[TeamManagement] Closing modal...");
      // Close modal first
      setIsEditAccessModalOpen(false);
      
      // Clear state after a small delay to ensure modal closes properly
      setTimeout(() => {
        setSelectedMember(null);
        setEditAccountPermissions({});
      }, 100);

      console.log("[TeamManagement] Showing success toast...");
      // Show toast after a delay to avoid conflicts with dialog closing
      setTimeout(() => {
        toast({
          title: "Success",
          description: `Updated access level${editAccessLevel === "view" && Object.keys(editAccountPermissions).length > 0 ? " and account permissions" : ""}`,
        });
      }, 200);
      
      console.log("[TeamManagement] handleUpdateAccess completed successfully");
    } catch (error) {
      console.error("[TeamManagement] Error in handleUpdateAccess:", error);
      toast({
        title: "Error",
        description: "Failed to update access level",
        variant: "destructive",
      });
    } finally {
      console.log("[TeamManagement] Setting isSubmitting to false");
      setIsSubmitting(false);
    }
  };

  const handleRemoveMember = async (member: TeamMember) => {
    setMemberToRemove(member);
  };

  const confirmRemoveMember = async () => {
    if (!memberToRemove) return;
    
    try {
      await removeMemberFromOrganization(
        orgData.organization_id,
        memberToRemove.user_id,
        user!.id,
      );

      // Update local state
      setMembers(members.filter((m) => m.user_id !== memberToRemove.user_id));
      setMemberToRemove(null);

      toast({
        title: "Success",
        description: `Removed ${memberToRemove.email} from the organization`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to remove member",
        variant: "destructive",
      });
    }
  };

  const handleCancelInvitation = async (invitation: Invitation) => {
    setInvitationToCancel(invitation);
  };

  const confirmCancelInvitation = async () => {
    if (!invitationToCancel) return;
    
    try {
      await cancelInvitation(invitationToCancel.id, user!.id);

      // Update local state
      setInvitations(
        invitations.filter((i) => i.id !== invitationToCancel.id),
      );
      setInvitationToCancel(null);

      toast({
        title: "Success",
        description: `Cancelled invitation to ${invitationToCancel.email}`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to cancel invitation",
        variant: "destructive",
      });
    }
  };

  const getAccessBadgeVariant = (accessLevel: string, isSuperAdmin?: boolean) => {
    if (isSuperAdmin) {
      return "default"; // Purple/primary color for super admins
    }
    switch (accessLevel) {
      case "owner":
        return "default";
      case "admin":
        return "secondary";
      default:
        return "outline";
    }
  };

  // Helper to check if a user is a super admin
  const isSuperAdmin = (email: string) => {
    return email.toLowerCase().endsWith("@ken-e.ai");
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Team Management
            </div>
            {canManageTeam && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsInviteModalOpen(true)}
                className="h-8 px-3"
              >
                <Plus className="h-4 w-4 mr-1" />
                Invite Member
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoadingMembers ? (
            <div className="text-center py-8 text-gray-500">
              <p>Loading team members...</p>
            </div>
          ) : members.length > 0 ? (
            <div className="space-y-3">
              {members.map((member) => (
                <div
                  key={member.user_id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-brand-light-blue/20 rounded-full flex items-center justify-center">
                      <Mail className="h-5 w-5 text-brand-medium-blue" />
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">
                        {member.email}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        {member.first_name && member.last_name && (
                          <span className="text-sm text-gray-600">
                            {member.first_name} {member.last_name}
                          </span>
                        )}
                        {isSuperAdmin(member.email) ? (
                          <Badge variant="default">
                            <Shield className="h-3 w-3 mr-1" />
                            Super Admin
                          </Badge>
                        ) : (
                          <Badge
                            variant={getAccessBadgeVariant(member.access_level)}
                          >
                            <Shield className="h-3 w-3 mr-1" />
                            {member.access_level}
                          </Badge>
                        )}
                      </div>
                      {/* Show account permissions for view-role users */}
                      {member.access_level === "view" && member.account_permissions && Object.keys(member.account_permissions).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {Object.entries(member.account_permissions).map(([accountId, accessLevel]) => (
                            <Badge key={accountId} variant="outline" className="text-xs">
                              Account {accountId.slice(-6)}: {accessLevel}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  {canManageTeam &&
                    member.access_level !== "owner" &&
                    member.user_id !== user?.id &&
                    !isSuperAdmin(member.email) && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                          >
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              console.log("[TeamManagement] Opening edit access modal for:", member.email);
                              setSelectedMember(member);
                              // Initialize edit access level with current level
                              // Map "owner" to "admin" for the modal
                              const currentLevel = member.access_level === "owner" ? "admin" : member.access_level;
                              setEditAccessLevel(currentLevel as "admin" | "view");
                              // Initialize account permissions with current permissions
                              setEditAccountPermissions(member.account_permissions || {});
                              setIsEditAccessModalOpen(true);
                            }}
                          >
                            Change Access Level
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-red-600"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleRemoveMember(member);
                            }}
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Remove from Organization
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Users className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No team members found</p>
            </div>
          )}

          <div className="mt-6 pt-6 border-t">
            <div className="text-sm text-gray-600">
              <p>
                {members.length} of {orgData.team.members_limit} seats used in
                your current plan
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      {canManageTeam && invitations.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg">Pending Invitations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {invitations.map((invitation) => (
                <div
                  key={invitation.id}
                  className="flex items-center justify-between p-4 border rounded-lg bg-orange-50 border-orange-200"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-orange-200 rounded-full flex items-center justify-center">
                      <Mail className="h-5 w-5 text-orange-600" />
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">
                        {invitation.email}
                      </h4>
                      <div className="flex items-center gap-2 mt-1 text-sm text-gray-600">
                        <Badge
                          variant="outline"
                          className="border-orange-300 text-orange-700"
                        >
                          <Shield className="h-3 w-3 mr-1" />
                          {invitation.access_level}
                        </Badge>
                        <span>
                          • Invited{" "}
                          {new Date(invitation.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCancelInvitation(invitation)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    Cancel
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invite Member Modal */}
      <Dialog open={isInviteModalOpen} onOpenChange={setIsInviteModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email Address</Label>
              <Input
                id="invite-email"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="member@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-access">Access Level</Label>
              <Select
                value={inviteAccessLevel}
                onValueChange={(value) =>
                  setInviteAccessLevel(value as "admin" | "view")
                }
              >
                <SelectTrigger id="invite-access">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="view">
                    View - Can view data only
                  </SelectItem>
                  <SelectItem value="admin">
                    Admin - Can manage settings
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Show account permissions for view-role users */}
            {inviteAccessLevel === "view" && accounts.length > 0 && (
              <div className="space-y-2">
                <Label>Account Permissions</Label>
                <div className="border rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
                  {accounts.map((account) => (
                    <div key={account.account_id} className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id={`account-${account.account_id}`}
                          checked={!!inviteAccountPermissions[account.account_id]}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setInviteAccountPermissions({
                                ...inviteAccountPermissions,
                                [account.account_id]: "view",
                              });
                            } else {
                              const { [account.account_id]: _, ...rest } = inviteAccountPermissions;
                              setInviteAccountPermissions(rest);
                            }
                          }}
                        />
                        <Label
                          htmlFor={`account-${account.account_id}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {account.account_name}
                        </Label>
                      </div>
                      {inviteAccountPermissions[account.account_id] && (
                        <div className="ml-6">
                          <Select
                            value={inviteAccountPermissions[account.account_id]}
                            onValueChange={(value) =>
                              setInviteAccountPermissions({
                                ...inviteAccountPermissions,
                                [account.account_id]: value as "edit" | "view",
                              })
                            }
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="view">View</SelectItem>
                              <SelectItem value="edit">Edit</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  Select which accounts this user should have access to
                </p>
              </div>
            )}
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsInviteModalOpen(false);
                  setInviteEmail("");
                  setInviteAccessLevel("view");
                  setInviteAccountPermissions({});
                }}
                className="flex-1"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleInviteMember}
                className="flex-1"
                disabled={isSubmitting || !inviteEmail}
              >
                {isSubmitting ? "Inviting..." : "Send Invitation"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Access Level Modal */}
      <Dialog
        open={isEditAccessModalOpen}
        onOpenChange={(open) => {
          console.log("[TeamManagement] Edit dialog onOpenChange:", open);
          setIsEditAccessModalOpen(open);
          if (!open) {
            // Force cleanup of dialog elements
            setTimeout(() => {
              const portalElements = document.querySelectorAll('[data-radix-portal]');
              portalElements.forEach(el => {
                if (el.innerHTML.trim() === '') {
                  el.remove();
                }
              });
              // Reset body styles that might have been set by dialog
              document.body.style.pointerEvents = '';
              document.body.style.overflow = '';
            }, 100);
            
            setSelectedMember(null);
            setEditAccountPermissions({});
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Change Access Level</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <p className="text-sm text-gray-600">
              Change access level for {selectedMember?.email}
            </p>
            <div className="space-y-2">
              <Label htmlFor="edit-access">Organization Access Level</Label>
              <Select
                value={editAccessLevel}
                onValueChange={(value) => {
                  setEditAccessLevel(value as "admin" | "view");
                  // Clear account permissions when changing to admin
                  if (value === "admin") {
                    setEditAccountPermissions({});
                  }
                }}
              >
                <SelectTrigger id="edit-access">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="view">
                    View - Can view data only
                  </SelectItem>
                  <SelectItem value="admin">
                    Admin - Can manage settings
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Show account permissions for view-role users */}
            {editAccessLevel === "view" && accounts.length > 0 && (
              <div className="space-y-2">
                <Label>Account Permissions</Label>
                <div className="border rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
                  {accounts.map((account) => (
                    <div key={account.account_id} className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id={`edit-account-${account.account_id}`}
                          checked={!!editAccountPermissions[account.account_id]}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setEditAccountPermissions({
                                ...editAccountPermissions,
                                [account.account_id]: "view",
                              });
                            } else {
                              const { [account.account_id]: _, ...rest } = editAccountPermissions;
                              setEditAccountPermissions(rest);
                            }
                          }}
                        />
                        <Label
                          htmlFor={`edit-account-${account.account_id}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {account.account_name}
                        </Label>
                      </div>
                      {editAccountPermissions[account.account_id] && (
                        <div className="ml-6">
                          <Select
                            value={editAccountPermissions[account.account_id]}
                            onValueChange={(value) =>
                              setEditAccountPermissions({
                                ...editAccountPermissions,
                                [account.account_id]: value as "edit" | "view",
                              })
                            }
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="view">View</SelectItem>
                              <SelectItem value="edit">Edit</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  Select which accounts this user should have access to
                </p>
              </div>
            )}
            
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditAccessModalOpen(false);
                  setSelectedMember(null);
                  setEditAccountPermissions({});
                }}
                className="flex-1"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={(e) => {
                  console.log("[TeamManagement] Update button clicked");
                  e.preventDefault();
                  handleUpdateAccess();
                }}
                className="flex-1"
                disabled={isSubmitting}
                type="button"
              >
                {isSubmitting ? "Updating..." : "Update Organization Access"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Remove Member Confirmation Dialog */}
      <Dialog
        open={!!memberToRemove}
        onOpenChange={(open) => {
          if (!open) setMemberToRemove(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Remove Team Member</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <p className="text-sm text-gray-600">
              Are you sure you want to remove <strong>{memberToRemove?.email}</strong> from the organization?
            </p>
            <p className="text-sm text-gray-500">
              This action cannot be undone. The user will lose access to all organization resources.
            </p>
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => setMemberToRemove(null)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={confirmRemoveMember}
                className="flex-1"
              >
                Remove Member
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Cancel Invitation Confirmation Dialog */}
      <Dialog
        open={!!invitationToCancel}
        onOpenChange={(open) => {
          if (!open) setInvitationToCancel(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Cancel Invitation</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <p className="text-sm text-gray-600">
              Are you sure you want to cancel the invitation to <strong>{invitationToCancel?.email}</strong>?
            </p>
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => setInvitationToCancel(null)}
                className="flex-1"
              >
                Keep Invitation
              </Button>
              <Button
                variant="destructive"
                onClick={confirmCancelInvitation}
                className="flex-1"
              >
                Cancel Invitation
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default TeamManagement;

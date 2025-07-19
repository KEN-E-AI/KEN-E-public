import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { Users, Plus, MoreVertical, Mail, Shield, Trash2 } from "lucide-react";
import { type Organization } from "@/data/organizationTypes";
import {
  getOrganizationMembers,
  inviteMemberToOrganization,
  updateMemberAccessLevel,
  removeMemberFromOrganization,
  getOrganizationInvitations,
  cancelInvitation,
  type TeamMember,
  type Invitation,
} from "@/data/teamApi";
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
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [isLoadingMembers, setIsLoadingMembers] = useState(true);
  const [isLoadingInvitations, setIsLoadingInvitations] = useState(true);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);
  const [isEditAccessModalOpen, setIsEditAccessModalOpen] = useState(false);

  // Form states
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteAccessLevel, setInviteAccessLevel] = useState<"admin" | "view">(
    "view",
  );
  const [editAccessLevel, setEditAccessLevel] = useState<"admin" | "view">(
    "view",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Check if current user can manage team (admin or owner)
  const canManageTeam =
    user?.permissions?.organizations?.[orgData.organization_id] === "admin" ||
    user?.permissions?.organizations?.[orgData.organization_id] === "owner";

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

    setIsSubmitting(true);
    try {
      await updateMemberAccessLevel(
        orgData.organization_id,
        selectedMember.user_id,
        { access_level: editAccessLevel },
        user.id,
      );

      // Update local state
      setMembers(
        members.map((m) =>
          m.user_id === selectedMember.user_id
            ? { ...m, access_level: editAccessLevel }
            : m,
        ),
      );

      setIsEditAccessModalOpen(false);
      setSelectedMember(null);

      toast({
        title: "Success",
        description: `Updated access level to ${editAccessLevel}`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update access level",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveMember = async (member: TeamMember) => {
    // Show confirmation toast with action
    toast({
      title: "Remove Team Member",
      description: `Are you sure you want to remove ${member.email} from the organization?`,
      action: (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Just dismiss the toast
            }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={async () => {
              try {
                await removeMemberFromOrganization(
                  orgData.organization_id,
                  member.user_id,
                  user!.id,
                );

                // Update local state
                setMembers(members.filter((m) => m.user_id !== member.user_id));

                toast({
                  title: "Success",
                  description: `Removed ${member.email} from the organization`,
                });
              } catch (error) {
                toast({
                  title: "Error",
                  description: "Failed to remove member",
                  variant: "destructive",
                });
              }
            }}
          >
            Remove Member
          </Button>
        </div>
      ),
    });
  };

  const handleCancelInvitation = async (invitation: Invitation) => {
    // Show confirmation toast with action
    toast({
      title: "Cancel Invitation",
      description: `Are you sure you want to cancel the invitation to ${invitation.email}?`,
      action: (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Just dismiss the toast
            }}
          >
            Keep
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={async () => {
              try {
                await cancelInvitation(invitation.id, user!.id);

                // Update local state
                setInvitations(invitations.filter((i) => i.id !== invitation.id));

                toast({
                  title: "Success",
                  description: `Cancelled invitation to ${invitation.email}`,
                });
              } catch (error) {
                toast({
                  title: "Error",
                  description: "Failed to cancel invitation",
                  variant: "destructive",
                });
              }
            }}
          >
            Cancel Invitation
          </Button>
        </div>
      ),
    });
  };

  const getAccessBadgeVariant = (accessLevel: string) => {
    switch (accessLevel) {
      case "owner":
        return "default";
      case "admin":
        return "secondary";
      default:
        return "outline";
    }
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
                        <Badge
                          variant={getAccessBadgeVariant(member.access_level)}
                        >
                          <Shield className="h-3 w-3 mr-1" />
                          {member.access_level}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  {canManageTeam &&
                    member.access_level !== "owner" &&
                    member.user_id !== user?.id && (
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
                            onClick={() => {
                              setSelectedMember(member);
                              setEditAccessLevel(
                                member.access_level as "admin" | "view",
                              );
                              setIsEditAccessModalOpen(true);
                            }}
                          >
                            Change Access Level
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-red-600"
                            onClick={() => handleRemoveMember(member)}
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
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsInviteModalOpen(false);
                  setInviteEmail("");
                  setInviteAccessLevel("view");
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
        onOpenChange={setIsEditAccessModalOpen}
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
              <Label htmlFor="edit-access">New Access Level</Label>
              <Select
                value={editAccessLevel}
                onValueChange={(value) =>
                  setEditAccessLevel(value as "admin" | "view")
                }
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
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditAccessModalOpen(false);
                  setSelectedMember(null);
                }}
                className="flex-1"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleUpdateAccess}
                className="flex-1"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Updating..." : "Update Access"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default TeamManagement;

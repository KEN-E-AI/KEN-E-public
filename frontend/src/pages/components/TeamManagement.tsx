import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Users } from "lucide-react";
import { type Organization } from "@/data/organizationData";

interface TeamManagementProps {
  orgData: Organization;
}

const TeamManagement = ({ orgData }: TeamManagementProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          Team Management
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Team Members</Label>
              <p className="text-sm text-dashboard-gray-600">
                {orgData.team.members_used} of {orgData.team.members_limit}{" "}
                seats used in your current plan
              </p>
            </div>
            <Button variant="outline" size="sm">
              Manage Team
            </Button>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Pending Invitations</Label>
              <p className="text-sm text-dashboard-gray-600">
                {orgData.team.pending_invitations} pending invitations sent
              </p>
            </div>
            <Button variant="outline" size="sm">
              View Invitations
            </Button>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Role Permissions</Label>
              <p className="text-sm text-dashboard-gray-600">
                Configure access levels for team roles
              </p>
            </div>
            <Button variant="outline" size="sm">
              Manage Roles
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TeamManagement;

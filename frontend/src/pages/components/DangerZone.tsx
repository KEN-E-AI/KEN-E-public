import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle } from "lucide-react";
import { type Organization } from "@/data/organizationData";

interface DangerZoneProps {
  orgData: Organization;
}

const DangerZone = ({ orgData }: DangerZoneProps) => {
  return (
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
            <Label className="text-red-600 mr-auto">Cancel Subscription</Label>
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
            <Label className="text-red-600 mr-auto">Delete Organization</Label>
            <p className="text-sm text-dashboard-gray-600">
              Permanently delete your organization and all associated data
            </p>
          </div>
          <Button variant="destructive" size="sm">
            Delete Organization
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default DangerZone;

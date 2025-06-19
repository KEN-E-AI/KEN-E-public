import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Crown } from "lucide-react";
import { type Organization } from "@/data/organizationData";

interface SubscriptionCardProps {
  orgData: Organization;
}

const SubscriptionCard = ({ orgData }: SubscriptionCardProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Crown className="h-5 w-5" />
          Subscription & Plan
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg border border-blue-200">
          <div className="flex items-center gap-3">
            <Crown className="h-8 w-8 text-blue-600" />
            <div>
              <h3 className="font-semibold text-blue-900">
                {orgData.subscription.plan_name}
              </h3>
              <p className="text-sm text-blue-700">
                {orgData.subscription.plan_description}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-900">
              ${orgData.subscription.price}
            </div>
            <div className="text-sm text-blue-700">
              per{" "}
              {orgData.subscription.billing_cycle === "monthly"
                ? "month"
                : "year"}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Plan Features</Label>
              <p className="text-sm text-dashboard-gray-600">
                Your current plan includes
              </p>
            </div>
            <div className="text-right space-y-1">
              {orgData.subscription.features.map((feature, index) => (
                <Badge key={index} variant="secondary">
                  {feature}
                </Badge>
              ))}
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Next Billing Date</Label>
              <p className="text-sm text-dashboard-gray-600">
                {orgData.subscription.next_billing_date}
              </p>
            </div>
            <Button variant="outline" size="sm">
              Change Plan
            </Button>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <Label className="mr-auto">Usage This Month</Label>
              <p className="text-sm text-dashboard-gray-600">
                Reports generated:{" "}
                {orgData.subscription.usage.reports_generated} /{" "}
                {orgData.subscription.usage.reports_limit}
              </p>
            </div>
            <Button variant="outline" size="sm">
              View Usage
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default SubscriptionCard;

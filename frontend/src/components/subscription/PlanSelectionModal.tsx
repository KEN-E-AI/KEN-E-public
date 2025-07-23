import { useState, useMemo, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { useSubscriptionPlans } from "@/hooks/useSubscriptionPlans";
import { updateOrganizationSubscription } from "@/data/organizationApi";
import type { Organization } from "@/data/organizationTypes";

interface PlanSelectionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentOrganization: Organization;
  accountId: string;
  onSubscriptionChanged: (updatedOrg: Organization) => void;
}

export function PlanSelectionModal({
  open,
  onOpenChange,
  currentOrganization,
  accountId,
  onSubscriptionChanged,
}: PlanSelectionModalProps) {
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [isChanging, setIsChanging] = useState(false);
  const { toast } = useToast();
  
  // Use the React Query hook for subscription plans
  const { plans, isLoading, error, refetch } = useSubscriptionPlans(open);

  // Get current plan ID from organization
  const currentPlanName = currentOrganization.subscription?.plan_name || "Free Plan";

  // Memoize getCurrentPlanId to avoid recalculating on every render
  const getCurrentPlanId = useMemo(() => {
    return plans.find((plan) => plan.plan_name === currentPlanName)?.plan_id || "";
  }, [plans, currentPlanName]);
  
  // Set selected plan when plans are loaded
  useEffect(() => {
    if (plans.length > 0 && !selectedPlanId && getCurrentPlanId) {
      setSelectedPlanId(getCurrentPlanId);
    }
  }, [plans, getCurrentPlanId]);

  const handlePlanChange = async () => {
    if (!selectedPlanId || selectedPlanId === getCurrentPlanId) {
      return;
    }

    try {
      setIsChanging(true);
      const updatedOrg = await updateOrganizationSubscription(
        currentOrganization.organization_id,
        selectedPlanId,
        accountId
      );
      
      toast({
        title: "Success",
        description: "Your subscription plan has been updated successfully.",
      });
      
      onSubscriptionChanged(updatedOrg);
      onOpenChange(false);
    } catch (error) {
      console.error("Failed to change subscription plan:", error);
      toast({
        title: "Error",
        description: "Failed to update subscription plan. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsChanging(false);
    }
  };

  const formatPrice = (price: number, currency: string, billingCycle: string) => {
    const formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    });
    return `${formatter.format(price)}/${billingCycle}`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Choose Your Subscription Plan</DialogTitle>
              <DialogDescription>
                Select the plan that best fits your organization's needs
              </DialogDescription>
            </div>
            {!isLoading && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => refetch()}
                title="Refresh subscription plans"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <RadioGroup
            value={selectedPlanId}
            onValueChange={setSelectedPlanId}
            className="grid gap-4 py-4"
          >
            {plans.map((plan) => {
              const isCurrentPlan = plan.plan_id === getCurrentPlanId;
              const isSelected = plan.plan_id === selectedPlanId;

              return (
                <Label
                  key={plan.plan_id}
                  htmlFor={plan.plan_id}
                  className="cursor-pointer"
                >
                  <Card
                    className={cn(
                      "relative transition-colors",
                      isSelected && "ring-2 ring-primary",
                      "hover:bg-accent/50"
                    )}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <RadioGroupItem value={plan.plan_id} id={plan.plan_id} />
                          <div>
                            <CardTitle className="text-lg">
                              {plan.plan_name}
                              {isCurrentPlan && (
                                <Badge variant="secondary" className="ml-2">
                                  Current Plan
                                </Badge>
                              )}
                            </CardTitle>
                            <CardDescription className="mt-1">
                              {plan.plan_description}
                            </CardDescription>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">
                            {formatPrice(plan.price, plan.currency, plan.billing_cycle)}
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <div className="flex items-center gap-2 text-sm">
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                          <span>Up to {plan.features.max_users} team members</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                          <span>{plan.features.max_reports} reports per month</span>
                        </div>
                        {plan.features.features.map((feature, index) => (
                          <div key={index} className="flex items-center gap-2 text-sm">
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                            <span>{feature}</span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </Label>
              );
            })}
          </RadioGroup>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handlePlanChange}
            disabled={
              isChanging ||
              isLoading ||
              !selectedPlanId ||
              selectedPlanId === getCurrentPlanId
            }
          >
            {isChanging ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Changing Plan...
              </>
            ) : (
              "Change Plan"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
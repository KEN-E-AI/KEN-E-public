import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import CompanyKeywordsConfiguration from "@/components/configuration/CompanyKeywordsConfiguration";
import Layout from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import {
  Loader2,
  ArrowLeft,
  Building,
  Info,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { SwotManagement } from "@/components/swot/SwotManagement";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useUpdateAccount } from "@/queries/accounts";
import {
  useValuePropositions,
  useCreateValueProposition,
  useUpdateValueProposition,
  useDeleteValueProposition,
} from "@/queries/products";
import { useToast } from "@/hooks/use-toast";
import { getAccountById } from "@/data/organizationApi";
import type { Account } from "@/data/organizationTypes";
import type {
  ValueProposition,
  ValuePropositionCreate,
} from "@/services/valuePropositionService";

export default function KnowledgeAccount() {
  const navigate = useNavigate();
  const { selectedOrgAccount, user, isSuperAdmin } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [companySummary, setCompanySummary] = useState("");
  const [originalSummary, setOriginalSummary] = useState("");

  // Value Proposition state
  const [isCreateVPModalOpen, setIsCreateVPModalOpen] = useState(false);
  const [selectedValueProposition, setSelectedValueProposition] =
    useState<ValueProposition | null>(null);
  const [isDeleteVPDialogOpen, setIsDeleteVPDialogOpen] = useState(false);
  const [valuePropositionFormData, setValuePropositionFormData] =
    useState<ValuePropositionCreate>({
      display_name: "",
      description: "",
      parent_node_id: "",
      parent_node_type: "Account",
      references: [],
    });

  // Fetch full account details from API
  const {
    data: accountData,
    isLoading: isLoadingAccount,
    error: accountError,
  } = useQuery<Account | undefined>({
    queryKey: ["account", selectedOrgAccount?.accountId],
    queryFn: async () => {
      if (!selectedOrgAccount?.accountId) {
        console.log("[KnowledgeAccount] No accountId available");
        return undefined;
      }
      console.log(
        "[KnowledgeAccount] Fetching account:",
        selectedOrgAccount.accountId,
      );
      const result = await getAccountById(selectedOrgAccount.accountId);
      console.log("[KnowledgeAccount] Fetch result:", result);
      return result;
    },
    enabled: !!selectedOrgAccount?.accountId,
  });

  // Log account fetch status
  console.log("[KnowledgeAccount] isLoadingAccount:", isLoadingAccount);
  console.log("[KnowledgeAccount] accountError:", accountError);

  // Use node_id if available, otherwise fall back to account_id
  const parentNodeId = accountData?.node_id || accountData?.account_id || null;

  // Fetch value propositions for this account
  const { data: valuePropositionsData, isLoading: isLoadingVPs } =
    useValuePropositions(selectedOrgAccount?.accountId || null, parentNodeId);
  const valuePropositions = valuePropositionsData?.value_propositions || [];

  // Debug logging
  console.log("[KnowledgeAccount] accountData:", accountData);
  console.log("[KnowledgeAccount] node_id:", accountData?.node_id);
  console.log("[KnowledgeAccount] account_id:", accountData?.account_id);
  console.log("[KnowledgeAccount] parentNodeId (for VP query):", parentNodeId);
  console.log(
    "[KnowledgeAccount] valuePropositionsData:",
    valuePropositionsData,
  );
  console.log(
    "[KnowledgeAccount] valuePropositions count:",
    valuePropositions.length,
  );
  console.log("[KnowledgeAccount] isLoadingVPs:", isLoadingVPs);

  // Value proposition mutations
  const createVPMutation = useCreateValueProposition();
  const updateVPMutation = useUpdateValueProposition();
  const deleteVPMutation = useDeleteValueProposition();

  // Permissions logic (copied from Products.tsx)
  const hasEditAccess = useMemo(() => {
    if (!selectedOrgAccount) return false;
    if (isSuperAdmin) return true;

    const accountId = selectedOrgAccount.accountId;
    const orgId = selectedOrgAccount.orgId;

    const orgRole = user?.permissions?.organizations?.[orgId];
    if (orgRole === "admin" || orgRole === "owner") return true;

    const accountPerm =
      user?.permissions?.account_permissions?.[accountId] ||
      user?.permissions?.accounts?.[accountId]; // Fallback for backward compatibility
    return accountPerm === "edit" || accountPerm === "admin";
  }, [selectedOrgAccount, user, isSuperAdmin]);

  // Update account mutation
  const updateMutation = useUpdateAccount();

  // Initialize company summary from fetched account data
  const currentSummary = accountData?.company_overview || "";

  const handleEdit = () => {
    setCompanySummary(currentSummary);
    setOriginalSummary(currentSummary);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!selectedOrgAccount?.accountId) return;

    try {
      await updateMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        updates: {
          company_overview: companySummary,
        },
      });

      // Invalidate account query to refetch updated data
      queryClient.invalidateQueries({
        queryKey: ["account", selectedOrgAccount.accountId],
      });

      toast({
        title: "Success",
        description: "Company summary updated successfully",
      });

      setIsEditing(false);
    } catch (error: any) {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to update company summary",
        variant: "destructive",
      });
    }
  };

  const handleCancel = () => {
    setCompanySummary(originalSummary);
    setIsEditing(false);
  };

  return (
    <Layout pageTitle="Account" maxWidth={false}>
      <div className="space-y-6">
        {/* Back to Knowledge Base Link */}
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/knowledge")}
            className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal mr-auto"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </Button>
        </div>

        {/* Company Summary Card */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle className="flex items-center gap-2">
                <Building className="h-5 w-5" />
                Company Summary
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        A comprehensive description of the company, including:
                        founding story, mission, featured products or services,
                        brand identity and target customers
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
            <p className="text-sm text-muted-foreground">
              {currentSummary ||
                "No company summary available yet. Click the pencil icon to add one."}
            </p>

            {/* Value Propositions (Read-only) */}
            {valuePropositions.length > 0 && (
              <div className="pt-4 border-t">
                <div className="flex items-center gap-2 mb-2">
                  <p className="font-semibold text-sm">Value Propositions</p>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-4 w-4 text-dashboard-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-sm">
                        <p>
                          Create a list of reasons why customers might choose to
                          do business with your company. What problems do you
                          solve for them? How is your offering unique from those
                          of your competitors?
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="space-y-2">
                  {valuePropositions.map((vp) => (
                    <div
                      key={vp.node_id}
                      className="p-3 rounded-md border border-dashboard-gray-200 bg-dashboard-gray-50"
                    >
                      <p className="font-medium text-sm">{vp.display_name}</p>
                      <p className="text-xs text-dashboard-gray-600 mt-1">
                        {vp.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Company Keywords (Editable) */}
        <CompanyKeywordsConfiguration hasEditAccess={hasEditAccess} />

        {/* SWOT Analysis */}
        <Card>
          <CardContent className="pt-6">
            <SwotManagement hasEditAccess={hasEditAccess} />
          </CardContent>
        </Card>

        {/* Edit Sheet */}
        <Sheet
          open={isEditing}
          modal={false}
          onOpenChange={(open) => {
            // Prevent closing if value proposition dialogs are open
            if (!open && (isCreateVPModalOpen || isDeleteVPDialogOpen)) {
              return;
            }
            setIsEditing(open);
          }}
        >
          <SheetContent side="right" className="w-[400px] flex flex-col">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Building className="h-5 w-5" />
                Edit Company Summary
              </SheetTitle>
            </SheetHeader>

            <div className="flex-1 mt-6 overflow-y-auto">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="company-summary">Company Overview</Label>
                  <Textarea
                    id="company-summary"
                    value={companySummary}
                    onChange={(e) => setCompanySummary(e.target.value)}
                    placeholder="Enter a comprehensive description of the company, including: founding story, mission, featured products or services, brand identity and target customers"
                    className="min-h-[200px]"
                  />
                </div>
              </div>

              {/* Value Propositions Section */}
              <div className="mt-6 pt-6 border-t">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold">Value Propositions</p>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-4 w-4 text-dashboard-gray-400" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm">
                          <p>
                            Create a list of reasons why customers might choose
                            to do business with your company. What problems do
                            you solve for them? How is your offering unique from
                            those of your competitors?
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  {hasEditAccess && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setValuePropositionFormData({
                          display_name: "",
                          description: "",
                          parent_node_id: parentNodeId || "",
                          parent_node_type: "Account",
                          references: [],
                        });
                        setSelectedValueProposition(null);
                        setIsCreateVPModalOpen(true);
                      }}
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Add
                    </Button>
                  )}
                </div>

                {isLoadingVPs ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : valuePropositions.length === 0 ? (
                  <p className="text-sm text-dashboard-gray-500 italic">
                    No value propositions yet
                  </p>
                ) : (
                  <div className="space-y-2">
                    {valuePropositions.map((vp) => (
                      <div
                        key={vp.node_id}
                        className="p-3 rounded-md border border-dashboard-gray-200
                                 bg-dashboard-gray-50 hover:bg-dashboard-gray-100
                                 transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="font-medium text-sm">
                              {vp.display_name}
                            </p>
                            <p className="text-xs text-dashboard-gray-600 mt-1">
                              {vp.description}
                            </p>
                          </div>
                          {hasEditAccess && (
                            <div className="flex gap-1 ml-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedValueProposition(vp);
                                  setValuePropositionFormData({
                                    display_name: vp.display_name,
                                    description: vp.description,
                                    parent_node_id: parentNodeId || "",
                                    parent_node_type: "Account",
                                    references: vp.references || [],
                                  });
                                  setIsCreateVPModalOpen(true);
                                }}
                              >
                                <Pencil className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedValueProposition(vp);
                                  setIsDeleteVPDialogOpen(true);
                                }}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons - Fixed at bottom */}
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
                disabled={updateMutation.isPending}
                className="flex-1"
              >
                {updateMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Save
              </Button>
            </div>
          </SheetContent>
        </Sheet>

        {/* Create/Edit Value Proposition Dialog */}
        <Dialog
          open={isCreateVPModalOpen}
          onOpenChange={(open) => {
            setIsCreateVPModalOpen(open);
            if (!open) {
              setSelectedValueProposition(null);
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {selectedValueProposition ? "Edit" : "Create"} Value Proposition
              </DialogTitle>
              <DialogDescription>
                {selectedValueProposition
                  ? "Update the value proposition details"
                  : "Add a value proposition to your company"}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div>
                <Label htmlFor="vp-display-name">Display Name *</Label>
                <Input
                  id="vp-display-name"
                  value={valuePropositionFormData.display_name}
                  onChange={(e) =>
                    setValuePropositionFormData({
                      ...valuePropositionFormData,
                      display_name: e.target.value,
                    })
                  }
                  placeholder="e.g., Fast Processing Times"
                  maxLength={60}
                />
                <p className="text-xs text-dashboard-gray-500 mt-1">
                  Short, descriptive name (max 60 characters)
                </p>
              </div>
              <div>
                <Label htmlFor="vp-description">Description *</Label>
                <Textarea
                  id="vp-description"
                  value={valuePropositionFormData.description}
                  onChange={(e) =>
                    setValuePropositionFormData({
                      ...valuePropositionFormData,
                      description: e.target.value,
                    })
                  }
                  placeholder="Explain how this benefits your customers..."
                  rows={4}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setIsCreateVPModalOpen(false);
                  setSelectedValueProposition(null);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={async () => {
                  if (
                    !selectedOrgAccount?.accountId ||
                    !valuePropositionFormData.display_name ||
                    !valuePropositionFormData.description
                  ) {
                    toast({
                      title: "Missing fields",
                      description: "Please fill in all required fields",
                      variant: "destructive",
                    });
                    return;
                  }

                  try {
                    if (selectedValueProposition) {
                      await updateVPMutation.mutateAsync({
                        accountId: selectedOrgAccount.accountId,
                        nodeId: selectedValueProposition.node_id,
                        updates: {
                          display_name: valuePropositionFormData.display_name,
                          description: valuePropositionFormData.description,
                          references: valuePropositionFormData.references,
                        },
                      });
                      toast({
                        title: "Success",
                        description: "Value proposition updated successfully",
                      });
                    } else {
                      await createVPMutation.mutateAsync({
                        accountId: selectedOrgAccount.accountId,
                        valueProposition: {
                          ...valuePropositionFormData,
                          parent_node_id: parentNodeId || "",
                        },
                      });
                      toast({
                        title: "Success",
                        description: "Value proposition created successfully",
                      });
                    }

                    // Invalidate VP query to refetch updated data
                    queryClient.invalidateQueries({
                      queryKey: ["products", "value-propositions"],
                    });

                    setIsCreateVPModalOpen(false);
                    setSelectedValueProposition(null);
                  } catch (error: any) {
                    toast({
                      title: "Error",
                      description:
                        error.response?.data?.detail ||
                        "Failed to save value proposition",
                      variant: "destructive",
                    });
                  }
                }}
                disabled={
                  createVPMutation.isPending || updateVPMutation.isPending
                }
              >
                {(createVPMutation.isPending || updateVPMutation.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {selectedValueProposition ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Value Proposition Dialog */}
        <AlertDialog
          open={isDeleteVPDialogOpen}
          onOpenChange={setIsDeleteVPDialogOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Value Proposition</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete "
                {selectedValueProposition?.display_name}"? This action cannot be
                undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={async () => {
                  if (
                    !selectedOrgAccount?.accountId ||
                    !selectedValueProposition
                  )
                    return;

                  try {
                    await deleteVPMutation.mutateAsync({
                      accountId: selectedOrgAccount.accountId,
                      nodeId: selectedValueProposition.node_id,
                    });

                    // Invalidate VP query to refetch updated data
                    queryClient.invalidateQueries({
                      queryKey: ["products", "value-propositions"],
                    });

                    toast({
                      title: "Success",
                      description: "Value proposition deleted successfully",
                    });
                    setIsDeleteVPDialogOpen(false);
                    setSelectedValueProposition(null);
                  } catch (error: any) {
                    toast({
                      title: "Error",
                      description:
                        error.response?.data?.detail ||
                        "Failed to delete value proposition",
                      variant: "destructive",
                    });
                  }
                }}
              >
                {deleteVPMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Layout>
  );
}

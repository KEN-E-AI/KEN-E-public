import { useState, useEffect, useRef } from "react";
import { ReactFlow, Controls, Background } from "reactflow";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import {
  Plus,
  Trash2,
  Star,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Dumbbell,
  Loader2,
  Info,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import type { Strength, StrengthCreate } from "@/services/strengthService";
import type {
  Opportunity,
  OpportunityCreate,
  OpportunityUpdate,
} from "@/services/opportunityService";
import {
  useStrengths,
  useOpportunities,
  useCreateStrength,
  useUpdateStrength,
  useDeleteStrength,
  useCreateOpportunity,
  useUpdateOpportunity,
  useDeleteOpportunity,
} from "@/queries/strengths";
import { StrengthNode, OpportunityNode } from "./StrengthFlowNodes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

interface StrengthsManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  display_name: string;
  description: string;
}

export const StrengthsManagement = ({
  hasEditAccess,
}: StrengthsManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();

  // React Query hooks for data fetching with caching
  const {
    data: strengthsData,
    isLoading,
    refetch: refetchStrengths,
  } = useStrengths(selectedOrgAccount?.accountId || null);
  const strengths = strengthsData?.strengths || [];

  // UI state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedStrength, setSelectedStrength] = useState<Strength | null>(
    null,
  );
  const [selectedStrengthId, setSelectedStrengthId] = useState<string | null>(
    null,
  );
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    display_name: "",
    description: "",
  });
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Opportunity state and queries
  const {
    data: opportunitiesData,
    isLoading: isLoadingOpportunities,
    refetch: refetchOpportunities,
  } = useOpportunities(
    selectedOrgAccount?.accountId || null,
    selectedStrengthId,
  );
  const opportunities = opportunitiesData?.opportunities || [];

  const [selectedOpportunity, setSelectedOpportunity] =
    useState<Opportunity | null>(null);
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<
    string | null
  >(null);
  const [isCreateOpportunityModalOpen, setIsCreateOpportunityModalOpen] =
    useState(false);
  const [opportunityFormData, setOpportunityFormData] =
    useState<OpportunityCreate>({
      display_name: "",
      description: "",
      strength_node_id: "",
      references: [],
    });

  // Context menu state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "strength" | "opportunity" | null
  >(null);
  const [isUnsavedChangesDialogOpen, setIsUnsavedChangesDialogOpen] =
    useState(false);
  const [pendingNode, setPendingNode] = useState<{
    type: "strength" | "opportunity";
    data: Strength | Opportunity;
  } | null>(null);

  // Opportunity delete state
  const [isDeleteOpportunityDialogOpen, setIsDeleteOpportunityDialogOpen] =
    useState(false);

  // React Query mutations
  const createStrengthMutation = useCreateStrength();
  const updateStrengthMutation = useUpdateStrength();
  const deleteStrengthMutation = useDeleteStrength();
  const createOpportunityMutation = useCreateOpportunity();
  const updateOpportunityMutation = useUpdateOpportunity();
  const deleteOpportunityMutation = useDeleteOpportunity();

  const checkScrollPosition = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    setCanScrollLeft(container.scrollLeft > 0);
    setCanScrollRight(
      container.scrollLeft < container.scrollWidth - container.clientWidth - 1,
    );
  };

  const scrollLeft = () => {
    scrollContainerRef.current?.scrollBy({ left: -300, behavior: "smooth" });
  };

  const scrollRight = () => {
    scrollContainerRef.current?.scrollBy({ left: 300, behavior: "smooth" });
  };

  useEffect(() => {
    checkScrollPosition();
    const handleResize = () => checkScrollPosition();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [strengths]);

  const handleCreateClick = () => {
    setFormData({ display_name: "", description: "" });
    setIsCreateModalOpen(true);
  };

  const handleStrengthClick = (strength: Strength) => {
    setSelectedStrengthId(strength.node_id);
    setSelectedStrength(strength);
    setFormData({
      display_name: strength.display_name,
      description: strength.description,
    });
    setIsEditing(false);
    // Do NOT open context menu from horizontal scroll click
  };

  const handleDeleteClick = (strength: Strength) => {
    setSelectedStrength(strength);
    setIsDeleteDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!selectedOrgAccount?.accountId) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Strength name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating strength...");
      setIsCreateModalOpen(false);

      await createStrengthMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        strength: formData,
      });

      toast({
        title: "Success",
        description: "Strength created successfully",
      });
    } catch (error) {
      console.error("Failed to create strength:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create strength";

        if (status === 409) {
          toast({
            title: "Duplicate Strength",
            description: "A strength with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create strengths",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  const handleSave = async () => {
    if (!selectedOrgAccount?.accountId || !selectedStrength) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Strength name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating strength...");
      setIsEditing(false);

      await updateStrengthMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedStrength.node_id,
        updates: formData,
      });

      // Update selected strength with new data
      setSelectedStrength({
        ...selectedStrength,
        display_name: formData.display_name,
        description: formData.description,
      });

      toast({
        title: "Success",
        description: "Strength updated successfully",
      });
    } catch (error) {
      console.error("Failed to update strength:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update strength";
        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      }
    } finally {
      endOperation();
    }
  };

  const handleDelete = async () => {
    if (!selectedOrgAccount?.accountId || !selectedStrength) return;

    try {
      startOperation("Deleting strength...");
      setIsDeleteDialogOpen(false);

      await deleteStrengthMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedStrength.node_id,
      });

      // Clear all selections to return to initial state
      setSelectedStrengthId(null);
      setSelectedStrength(null);
      setSelectedOpportunityId(null);
      setSelectedOpportunity(null);
      setIsContextMenuOpen(false);

      toast({
        title: "Success",
        description: "Strength deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete strength:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to delete strength";

        if (status === 400 && message.includes("dependencies")) {
          toast({
            title: "Cannot Delete",
            description:
              "This strength has opportunities linked to it. Remove them first.",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  // React Flow node types
  const nodeTypes = {
    strengthNode: StrengthNode,
    opportunityNode: OpportunityNode,
  };

  // Generate nodes for React Flow
  const generateNodes = (): Node[] => {
    if (!selectedStrength) return [];

    const nodes: Node[] = [];

    // Strength Node (top center)
    nodes.push({
      id: selectedStrength.node_id,
      type: "strengthNode",
      position: { x: 300, y: 50 },
      data: {
        label: selectedStrength.display_name,
        isSelected:
          selectedStrengthId === selectedStrength.node_id &&
          !selectedOpportunityId,
        onAddOpportunity: () => setIsCreateOpportunityModalOpen(true),
      },
    });

    // Opportunity Nodes (row below, horizontally spaced)
    const opportunityWidth = 224; // Fixed width: 200px text box - 48px overlap + 72px circle
    const gap = 36;
    const totalWidth = opportunities.length * (opportunityWidth + gap) - gap;
    const startX = 300 - totalWidth / 2;

    opportunities.forEach((opportunity, index) => {
      nodes.push({
        id: opportunity.node_id,
        type: "opportunityNode",
        position: {
          x: startX + index * (opportunityWidth + gap),
          y: 224,
        },
        data: {
          label: opportunity.display_name,
          showHandle: selectedOpportunityId === opportunity.node_id,
          isSelected: selectedOpportunityId === opportunity.node_id,
          onAddSubstitute: () => {
            toast({
              title: "Coming Soon",
              description: "Related opportunities feature not yet available",
            });
          },
        },
      });
    });

    return nodes;
  };

  // Generate edges for React Flow
  const generateEdges = (): Edge[] => {
    if (!selectedStrength) return [];

    const edges: Edge[] = [];

    opportunities.forEach((opportunity) => {
      edges.push({
        id: `${selectedStrength.node_id}-${opportunity.node_id}`,
        source: selectedStrength.node_id,
        target: opportunity.node_id,
        type: "smoothstep",
        style: {
          stroke: "#000",
          strokeWidth: 2,
        },
        sourceHandle: "bottom",
        targetHandle: "top",
      });
    });

    return edges;
  };

  // Handle node clicks in React Flow
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    // Check for unsaved changes
    if (isEditing) {
      // Check if data was actually modified (trim to ignore whitespace-only changes)
      const hasChanges =
        (selectedStrength &&
          (formData.display_name.trim() !==
            selectedStrength.display_name.trim() ||
            formData.description.trim() !==
              selectedStrength.description.trim())) ||
        (selectedOpportunity &&
          (formData.display_name.trim() !==
            selectedOpportunity.display_name.trim() ||
            formData.description.trim() !==
              selectedOpportunity.description.trim()));

      if (hasChanges) {
        // Store pending node and show warning
        if (node.type === "opportunityNode") {
          const opportunity = opportunities.find((o) => o.node_id === node.id);
          if (opportunity) {
            setPendingNode({ type: "opportunity", data: opportunity });
            setIsUnsavedChangesDialogOpen(true);
          }
        } else if (node.type === "strengthNode") {
          const strength = strengths.find((s) => s.node_id === node.id);
          if (strength) {
            setPendingNode({ type: "strength", data: strength });
            setIsUnsavedChangesDialogOpen(true);
          }
        }
        return;
      } else {
        // No actual changes, just exit edit mode and continue
        setIsEditing(false);
      }
    }

    // Open context menu
    if (node.type === "opportunityNode") {
      const opportunity = opportunities.find((o) => o.node_id === node.id);
      if (!opportunity) return;

      setSelectedOpportunityId(node.id);
      setSelectedOpportunity(opportunity);
      // Keep strength selected to maintain diagram visibility

      setFormData({
        display_name: opportunity.display_name,
        description: opportunity.description,
      });

      setContextMenuType("opportunity");
      setIsContextMenuOpen(true);
      setIsEditing(false);
    } else if (node.type === "strengthNode") {
      const strength = strengths.find((s) => s.node_id === node.id);
      if (!strength) return;

      // When clicking strength node, clear opportunity selection
      setSelectedOpportunityId(null);
      setSelectedOpportunity(null);

      // Set strength as selected (may already be selected from horizontal scroll)
      setSelectedStrengthId(strength.node_id);
      setSelectedStrength(strength);

      setFormData({
        display_name: strength.display_name,
        description: strength.description,
      });

      setContextMenuType("strength");
      setIsContextMenuOpen(true);
      setIsEditing(false);
    }
  };

  // Handle discarding changes and switching to pending node
  const handleDiscardChanges = () => {
    if (!pendingNode) return;

    setIsEditing(false);
    setIsUnsavedChangesDialogOpen(false);

    // Switch to the pending node
    if (pendingNode.type === "opportunity") {
      const opportunity = pendingNode.data as Opportunity;
      setSelectedOpportunityId(opportunity.node_id);
      setSelectedOpportunity(opportunity);
      // Keep strength selected to maintain diagram visibility

      setFormData({
        display_name: opportunity.display_name,
        description: opportunity.description,
      });

      setContextMenuType("opportunity");
      setIsContextMenuOpen(true);
    } else {
      const strength = pendingNode.data as Strength;

      // Clear opportunity selection when switching to strength
      setSelectedOpportunityId(null);
      setSelectedOpportunity(null);

      // Set strength as selected
      setSelectedStrengthId(strength.node_id);
      setSelectedStrength(strength);

      setFormData({
        display_name: strength.display_name,
        description: strength.description,
      });

      setContextMenuType("strength");
      setIsContextMenuOpen(true);
    }

    setPendingNode(null);
  };

  // Handle opportunity creation
  const handleCreateOpportunity = async () => {
    if (!selectedOrgAccount?.accountId || !selectedStrength) return;
    if (
      !opportunityFormData.display_name.trim() ||
      !opportunityFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Opportunity name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating opportunity...");
      setIsCreateOpportunityModalOpen(false);

      const opportunityData: OpportunityCreate = {
        display_name: opportunityFormData.display_name,
        description: opportunityFormData.description,
        strength_node_id: selectedStrength.node_id,
        references:
          opportunityFormData.references?.filter((r) => r.trim()) || [],
      };

      const newOpportunity = await createOpportunityMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        opportunity: opportunityData,
      });

      setSelectedOpportunityId(newOpportunity.node_id);
      setSelectedOpportunity(newOpportunity);

      setFormData({
        display_name: newOpportunity.display_name,
        description: newOpportunity.description,
      });

      setContextMenuType("opportunity");
      setIsContextMenuOpen(true);

      setOpportunityFormData({
        display_name: "",
        description: "",
        strength_node_id: "",
        references: [],
      });

      toast({
        title: "Success",
        description: "Opportunity created successfully",
      });
    } catch (error) {
      console.error("Failed to create opportunity:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create opportunity";

        if (status === 409) {
          toast({
            title: "Duplicate Opportunity",
            description:
              "An opportunity with this name already exists for this strength",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create opportunities",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  const handleOpportunitySave = async () => {
    if (!selectedOrgAccount?.accountId || !selectedOpportunity) return;

    if (!formData.display_name.trim() || !formData.description.trim()) {
      toast({
        title: "Validation Error",
        description: "Opportunity name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating opportunity...");
      setIsEditing(false);

      const updateData: OpportunityUpdate = {
        display_name: formData.display_name.trim(),
        description: formData.description.trim(),
      };

      const updatedOpportunity = await updateOpportunityMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedOpportunity.node_id,
        updates: updateData,
        strengthId:
          selectedStrength?.node_id || selectedOpportunity.strength_node_id,
      });

      // Update selected opportunity
      setSelectedOpportunity(updatedOpportunity);

      // Update form data to match saved values
      setFormData({
        display_name: updatedOpportunity.display_name,
        description: updatedOpportunity.description,
      });

      toast({
        title: "Success",
        description: "Opportunity updated successfully",
      });
    } catch (error) {
      console.error("Failed to update opportunity:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to update opportunity";

        if (status === 409) {
          toast({
            title: "Duplicate Opportunity",
            description:
              "An opportunity with this name already exists for this strength",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to edit opportunities",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  const handleDeleteOpportunity = async () => {
    if (!selectedOrgAccount?.accountId || !selectedOpportunity) return;

    try {
      startOperation("Deleting opportunity...");
      setIsDeleteOpportunityDialogOpen(false);

      await deleteOpportunityMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedOpportunity.node_id,
        strengthId:
          selectedStrength?.node_id || selectedOpportunity.strength_node_id,
      });

      // Close context menu and clear opportunity selection
      setIsContextMenuOpen(false);
      setSelectedOpportunityId(null);
      setSelectedOpportunity(null);

      toast({
        title: "Success",
        description: "Opportunity deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete opportunity:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to delete opportunity";

        if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to delete opportunities",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Error",
            description: message,
            variant: "destructive",
          });
        }
      }
    } finally {
      endOperation();
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="flex items-center gap-2">
              <Dumbbell className="h-5 w-5" />
              Strengths
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-dashboard-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>
                      Identify your business strengths to help KEN-E understand
                      what your company excels at and how to leverage these
                      advantages.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
            {hasEditAccess && (
              <Button
                onClick={handleCreateClick}
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0"
              >
                <Plus className="h-5 w-5" />
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              Loading strengths...
            </div>
          ) : strengths.length === 0 ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              No strengths found.
              {hasEditAccess && " Click '+' to add one."}
            </div>
          ) : (
            <div className="relative">
              {/* Left Scroll Arrow */}
              {canScrollLeft && (
                <button
                  className="absolute left-0 top-0 bottom-0 z-20 bg-gray-500 bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity"
                  onClick={scrollLeft}
                >
                  <ChevronLeft className="h-6 w-6 text-white" />
                </button>
              )}

              {/* Scrollable Container */}
              <div
                ref={scrollContainerRef}
                className="flex gap-3 overflow-x-auto px-2 py-2"
                onScroll={checkScrollPosition}
              >
                {strengths.map((strength) => (
                  <div
                    key={strength.node_id}
                    className={`flex-shrink-0 p-4 rounded-lg transition-colors cursor-pointer ${
                      selectedStrengthId === strength.node_id
                        ? "ring-2 ring-brand-medium-blue"
                        : "hover:ring-2 hover:ring-gray-300"
                    }`}
                    onClick={() => handleStrengthClick(strength)}
                  >
                    <div className="flex items-center">
                      {/* Text Box - Left */}
                      <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
                        <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
                          Strength
                        </p>
                        <p className="font-semibold text-dashboard-gray-900 leading-tight">
                          {strength.display_name}
                        </p>
                      </div>

                      {/* Circle with Icon - Right */}
                      <div className="flex-shrink-0 -ml-12 relative z-10">
                        <div
                          className="rounded-full bg-brand-light-blue flex items-center justify-center"
                          style={{ width: "72px", height: "72px" }}
                        >
                          <Dumbbell
                            className="text-white"
                            style={{ width: "48px", height: "48px" }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Right Scroll Arrow */}
              {canScrollRight && (
                <button
                  className="absolute right-0 top-0 bottom-0 z-20 bg-gray-500 bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity"
                  onClick={scrollRight}
                >
                  <ChevronRight className="h-6 w-6 text-white" />
                </button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Opportunities Card - Full width, shown when strength is selected */}
      <div className="mt-6">
        {selectedStrengthId ? (
          <Card className="h-[600px]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Star className="h-5 w-5" />
                Opportunities
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-dashboard-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>
                        Identify opportunities that arise from the selected
                        strength. These are potential areas for growth and
                        strategic advantage.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[520px]">
              {isLoadingOpportunities ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : (
                <ReactFlow
                  nodes={generateNodes()}
                  edges={generateEdges()}
                  nodeTypes={nodeTypes}
                  onNodeClick={handleNodeClick}
                  onNodeDoubleClick={handleNodeClick}
                  defaultViewport={{ x: 250, y: 50, zoom: 1 }}
                  minZoom={0.5}
                  maxZoom={1.5}
                  nodesDraggable={false}
                  nodesConnectable={false}
                  elementsSelectable={true}
                  panOnScroll={true}
                  zoomOnScroll={false}
                  proOptions={{ hideAttribution: true }}
                >
                  <Background />
                  <Controls />
                </ReactFlow>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="p-6 bg-dashboard-gray-50 rounded-lg border border-dashboard-gray-200">
            <p className="text-dashboard-gray-500 text-center">
              Select a strength to view opportunities.
            </p>
          </div>
        )}
      </div>

      {/* Create Strength Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Strength</DialogTitle>
            <DialogDescription>
              Add a new strength to your business.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-strength-name">Strength Name</Label>
              <Input
                id="create-strength-name"
                value={formData.display_name}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value })
                }
                placeholder="e.g., Strong Brand Recognition"
              />
            </div>
            <div>
              <Label htmlFor="create-description">Description</Label>
              <Textarea
                id="create-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Describe this strength..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!formData.display_name.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Strength Confirmation */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Strength?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedStrength?.display_name}
              "? This action cannot be undone.
              {selectedStrength && (
                <span className="block mt-2 text-dashboard-gray-600">
                  Note: Strengths with linked opportunities cannot be deleted.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Opportunity Confirmation */}
      <AlertDialog
        open={isDeleteOpportunityDialogOpen}
        onOpenChange={setIsDeleteOpportunityDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Opportunity</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "
              {selectedOpportunity?.display_name}"? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteOpportunity}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Unsaved Changes Warning */}
      <AlertDialog
        open={isUnsavedChangesDialogOpen}
        onOpenChange={setIsUnsavedChangesDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Are you sure you want to discard them?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingNode(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDiscardChanges}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Discard Changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Opportunity Modal */}
      <Dialog
        open={isCreateOpportunityModalOpen}
        onOpenChange={setIsCreateOpportunityModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Opportunity</DialogTitle>
            <DialogDescription>
              Add a new opportunity to {selectedStrength?.display_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-opportunity-name">
                Opportunity Name *
              </Label>
              <Input
                id="create-opportunity-name"
                value={opportunityFormData.display_name}
                onChange={(e) =>
                  setOpportunityFormData({
                    ...opportunityFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder="e.g., Expand into new markets"
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="create-opportunity-description">
                Description *
              </Label>
              <Textarea
                id="create-opportunity-description"
                value={opportunityFormData.description}
                onChange={(e) =>
                  setOpportunityFormData({
                    ...opportunityFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Describe this opportunity..."
                rows={4}
                maxLength={4000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateOpportunityModalOpen(false);
                setOpportunityFormData({
                  display_name: "",
                  description: "",
                  strength_node_id: "",
                  references: [],
                });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateOpportunity}
              disabled={
                !opportunityFormData.display_name.trim() ||
                !opportunityFormData.description.trim()
              }
            >
              Create Opportunity
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Node Context Menu - Slides in from right */}
      <Sheet
        open={isContextMenuOpen}
        modal={false}
        onOpenChange={(open) => {
          // Prevent closing if there are unsaved changes
          if (!open && isEditing) {
            const hasChanges =
              (selectedStrength &&
                (formData.display_name.trim() !==
                  selectedStrength.display_name.trim() ||
                  formData.description.trim() !==
                    selectedStrength.description.trim())) ||
              (selectedOpportunity &&
                (formData.display_name.trim() !==
                  selectedOpportunity.display_name.trim() ||
                  formData.description.trim() !==
                    selectedOpportunity.description.trim()));

            if (hasChanges) {
              // Don't close, user must explicitly cancel or save
              return;
            }
          }
          setIsContextMenuOpen(open);
          if (!open) {
            setIsEditing(false);
          }
        }}
      >
        <SheetContent side="right" className="w-[400px] flex flex-col">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              {contextMenuType === "strength" ? (
                <Dumbbell className="h-5 w-5" />
              ) : (
                <Star className="h-5 w-5" />
              )}
              {contextMenuType === "strength" ? "Strength" : "Opportunity"}
            </SheetTitle>
          </SheetHeader>

          <div className="flex-1 mt-6 overflow-y-auto">
            {isEditing ? (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="context-edit-name">Name:</Label>
                  <Input
                    id="context-edit-name"
                    value={formData.display_name}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        display_name: e.target.value,
                      })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="context-edit-description">Description:</Label>
                  <Textarea
                    id="context-edit-description"
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        description: e.target.value,
                      })
                    }
                    rows={4}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="font-semibold">Name:</p>
                  <p>
                    {contextMenuType === "strength"
                      ? selectedStrength?.display_name
                      : selectedOpportunity?.display_name}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Description:</p>
                  <p className="text-sm text-dashboard-gray-600">
                    {contextMenuType === "strength"
                      ? selectedStrength?.description
                      : selectedOpportunity?.description}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons - Fixed at bottom */}
          {hasEditAccess && (
            <div className="flex gap-2 pt-4 border-t">
              {isEditing ? (
                <>
                  <Button
                    onClick={() => {
                      setIsEditing(false);
                      if (selectedStrength) {
                        setFormData({
                          display_name: selectedStrength.display_name,
                          description: selectedStrength.description,
                        });
                      } else if (selectedOpportunity) {
                        setFormData({
                          display_name: selectedOpportunity.display_name,
                          description: selectedOpportunity.description,
                        });
                      }
                    }}
                    variant="outline"
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={
                      contextMenuType === "strength"
                        ? handleSave
                        : handleOpportunitySave
                    }
                    className="flex-1"
                  >
                    Save Changes
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    onClick={() => setIsEditing(true)}
                    variant="outline"
                    className="flex-1"
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                  <Button
                    onClick={() => {
                      if (contextMenuType === "strength" && selectedStrength) {
                        setIsContextMenuOpen(false);
                        handleDeleteClick(selectedStrength);
                      } else if (
                        contextMenuType === "opportunity" &&
                        selectedOpportunity
                      ) {
                        setIsContextMenuOpen(false);
                        setIsDeleteOpportunityDialogOpen(true);
                      }
                    }}
                    variant="destructive"
                    className="flex-1"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </Button>
                </>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
};

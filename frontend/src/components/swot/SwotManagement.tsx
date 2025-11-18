import { useState, useMemo } from "react";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import {
  Plus,
  Trash2,
  Star,
  Pencil,
  Dumbbell,
  Unlink,
  ShieldAlert,
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
import type { Weakness, WeaknessCreate } from "@/services/weaknessService";
import type { Risk, RiskCreate, RiskUpdate } from "@/services/riskService";
import {
  useStrengths,
  useOpportunities,
  useCreateStrength,
  useUpdateStrength,
  useDeleteStrength,
  useCreateOpportunity,
  useUpdateOpportunity,
  useDeleteOpportunity,
  useWeaknesses,
  useRisks,
  useCreateWeakness,
  useUpdateWeakness,
  useDeleteWeakness,
  useCreateRisk,
  useUpdateRisk,
  useDeleteRisk,
} from "@/queries/swot";
import {
  StrengthNode,
  OpportunityNode,
  WeaknessNode,
  RiskNode,
} from "./SwotFlowNodes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

// Import knowledge graph components
import {
  ModeSelector,
  KnowledgeGraphCard,
  HorizontalScrollList,
  HorizontalScrollItem,
  GraphVisualizationCard,
  KnowledgeGraphSideSheet,
  DIAGRAM_LAYOUT,
  DEFAULT_EDGE_STYLE,
} from "@/components/knowledge-graph";
import type { ModeConfig } from "@/components/knowledge-graph";

type SwotMode = "strengths" | "weaknesses";

interface SwotManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  display_name: string;
  description: string;
}

const SWOT_MODES: readonly ModeConfig<SwotMode>[] = [
  { value: "strengths", label: "Strengths" },
  { value: "weaknesses", label: "Weaknesses" },
] as const;

export const SwotManagement = ({ hasEditAccess }: SwotManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();

  // Mode state
  const [mode, setMode] = useState<SwotMode>("strengths");

  // Fetch data for both modes
  const { data: strengthsData, isLoading: isLoadingStrengths } = useStrengths(
    mode === "strengths" ? selectedOrgAccount?.accountId || null : null,
  );
  const strengths = strengthsData?.strengths || [];

  const { data: weaknessesData, isLoading: isLoadingWeaknesses } =
    useWeaknesses(
      mode === "weaknesses" ? selectedOrgAccount?.accountId || null : null,
    );
  const weaknesses = weaknessesData?.weaknesses || [];

  // Unified state for selected parent (strength or weakness)
  const [selectedParentId, setSelectedParentId] = useState<string | null>(null);
  const [selectedParent, setSelectedParent] = useState<
    Strength | Weakness | null
  >(null);

  // UI state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    display_name: "",
    description: "",
  });

  // Fetch children based on mode
  const { data: opportunitiesData, isLoading: isLoadingOpportunities } =
    useOpportunities(
      mode === "strengths" ? selectedOrgAccount?.accountId || null : null,
      mode === "strengths" ? selectedParentId : null,
      "strength", // SWOT Strengths create Opportunities
    );
  const opportunities = opportunitiesData?.opportunities || [];

  const { data: risksData, isLoading: isLoadingRisks } = useRisks(
    mode === "weaknesses" ? selectedOrgAccount?.accountId || null : null,
    mode === "weaknesses" ? selectedParentId : null,
  );
  const risks = risksData?.risks || [];

  // Unified child state
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);
  const [selectedChild, setSelectedChild] = useState<Opportunity | Risk | null>(
    null,
  );
  const [isCreateChildModalOpen, setIsCreateChildModalOpen] = useState(false);
  const [childFormData, setChildFormData] = useState<
    OpportunityCreate | RiskCreate
  >({
    display_name: "",
    description: "",
    strength_node_id: "",
    references: [],
  });

  // Context menu state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "parent" | "child" | null
  >(null);
  const [isUnsavedChangesDialogOpen, setIsUnsavedChangesDialogOpen] =
    useState(false);
  const [pendingNode, setPendingNode] = useState<{
    type: "parent" | "child";
    data: Strength | Weakness | Opportunity | Risk;
  } | null>(null);

  // Delete state
  const [isDeleteChildDialogOpen, setIsDeleteChildDialogOpen] = useState(false);

  // React Query mutations - Strengths
  const createStrengthMutation = useCreateStrength();
  const updateStrengthMutation = useUpdateStrength();
  const deleteStrengthMutation = useDeleteStrength();

  // React Query mutations - Weaknesses
  const createWeaknessMutation = useCreateWeakness();
  const updateWeaknessMutation = useUpdateWeakness();
  const deleteWeaknessMutation = useDeleteWeakness();

  // React Query mutations - Opportunities
  const createOpportunityMutation = useCreateOpportunity();
  const updateOpportunityMutation = useUpdateOpportunity();
  const deleteOpportunityMutation = useDeleteOpportunity();

  // React Query mutations - Risks
  const createRiskMutation = useCreateRisk();
  const updateRiskMutation = useUpdateRisk();
  const deleteRiskMutation = useDeleteRisk();

  // Derived values based on mode
  const items = mode === "strengths" ? strengths : weaknesses;
  const isLoadingItems =
    mode === "strengths" ? isLoadingStrengths : isLoadingWeaknesses;
  const children = mode === "strengths" ? opportunities : risks;
  const isLoadingChildren =
    mode === "strengths" ? isLoadingOpportunities : isLoadingRisks;

  // Mode switch handler - clears all selections
  const handleModeSwitch = (newMode: SwotMode) => {
    if (isEditing) {
      const hasChanges =
        (selectedParent &&
          (formData.display_name.trim() !==
            selectedParent.display_name.trim() ||
            formData.description.trim() !==
              selectedParent.description.trim())) ||
        (selectedChild &&
          (formData.display_name.trim() !== selectedChild.display_name.trim() ||
            formData.description.trim() !== selectedChild.description.trim()));

      if (hasChanges) {
        toast({
          title: "Unsaved Changes",
          description:
            "Please save or cancel your changes before switching modes",
          variant: "destructive",
        });
        return;
      }
    }

    setMode(newMode);
    setSelectedParentId(null);
    setSelectedParent(null);
    setSelectedChildId(null);
    setSelectedChild(null);
    setIsContextMenuOpen(false);
    setIsEditing(false);
  };

  const handleCreateClick = () => {
    setFormData({ display_name: "", description: "" });
    setIsCreateModalOpen(true);
  };

  const handleParentClick = (parent: Strength | Weakness) => {
    setSelectedParentId(parent.node_id);
    setSelectedParent(parent);
    setFormData({
      display_name: parent.display_name,
      description: parent.description,
    });
    setIsEditing(false);
  };

  const handleDeleteClick = (parent: Strength | Weakness) => {
    setSelectedParent(parent);
    setIsDeleteDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!selectedOrgAccount?.accountId) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: `${mode === "strengths" ? "Strength" : "Weakness"} name is required`,
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "strength" : "weakness";
      startOperation(`Creating ${label}...`);
      setIsCreateModalOpen(false);

      if (mode === "strengths") {
        await createStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          strength: formData,
        });
      } else {
        await createWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          weakness: formData,
        });
      }

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Strength" : "Weakness"} created successfully`,
      });
    } catch (error) {
      console.error(`Failed to create ${mode}:`, error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || `Failed to create ${mode}`;

        if (status === 409) {
          toast({
            title: "Duplicate",
            description: `A ${mode === "strengths" ? "strength" : "weakness"} with this name already exists`,
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to create ${mode}`,
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
    if (!selectedOrgAccount?.accountId || !selectedParent) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: `${mode === "strengths" ? "Strength" : "Weakness"} name is required`,
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "strength" : "weakness";
      startOperation(`Updating ${label}...`);
      setIsEditing(false);

      if (mode === "strengths") {
        await updateStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedParent.node_id,
          updates: formData,
        });
      } else {
        await updateWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedParent.node_id,
          updates: formData,
        });
      }

      setSelectedParent({
        ...selectedParent,
        display_name: formData.display_name,
        description: formData.description,
      });

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Strength" : "Weakness"} updated successfully`,
      });
    } catch (error) {
      console.error(`Failed to update ${mode}:`, error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || `Failed to update ${mode}`;
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
    if (!selectedOrgAccount?.accountId || !selectedParent) return;

    try {
      const label = mode === "strengths" ? "strength" : "weakness";
      startOperation(`Deleting ${label}...`);
      setIsDeleteDialogOpen(false);

      if (mode === "strengths") {
        await deleteStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedParent.node_id,
        });
      } else {
        await deleteWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedParent.node_id,
        });
      }

      setSelectedParentId(null);
      setSelectedParent(null);
      setSelectedChildId(null);
      setSelectedChild(null);
      setIsContextMenuOpen(false);

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Strength" : "Weakness"} deleted successfully`,
      });
    } catch (error) {
      console.error(`Failed to delete ${mode}:`, error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || `Failed to delete ${mode}`;

        if (status === 400 && message.includes("dependencies")) {
          toast({
            title: "Cannot Delete",
            description: `This ${mode === "strengths" ? "strength" : "weakness"} has ${mode === "strengths" ? "opportunities" : "risks"} linked to it. Remove them first.`,
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
  const nodeTypes =
    mode === "strengths"
      ? { strengthNode: StrengthNode, opportunityNode: OpportunityNode }
      : { weaknessNode: WeaknessNode, riskNode: RiskNode };

  // Generate nodes for React Flow
  const generateNodes = (): Node[] => {
    if (!selectedParent) return [];

    const nodes: Node[] = [];
    const parentType = mode === "strengths" ? "strengthNode" : "weaknessNode";
    const childType = mode === "strengths" ? "opportunityNode" : "riskNode";

    nodes.push({
      id: selectedParent.node_id,
      type: parentType,
      position: {
        x: DIAGRAM_LAYOUT.PARENT_NODE_X,
        y: DIAGRAM_LAYOUT.PARENT_NODE_Y,
      },
      data: {
        label: selectedParent.display_name,
        isSelected:
          selectedParentId === selectedParent.node_id && !selectedChildId,
        ...(mode === "strengths"
          ? { onAddOpportunity: () => setIsCreateChildModalOpen(true) }
          : { onAddRisk: () => setIsCreateChildModalOpen(true) }),
      },
    });

    const childWidth = DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;
    const gap = DIAGRAM_LAYOUT.HORIZONTAL_GAP;
    const totalWidth = children.length * childWidth - gap;
    const startX = DIAGRAM_LAYOUT.PARENT_NODE_X - totalWidth / 2;

    children.forEach((child, index) => {
      nodes.push({
        id: child.node_id,
        type: childType,
        position: {
          x: startX + index * childWidth,
          y: DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING,
        },
        data: {
          label: child.display_name,
          showHandle: selectedChildId === child.node_id,
          isSelected: selectedChildId === child.node_id,
          onAddSubstitute: () => {
            toast({
              title: "Coming Soon",
              description: `Related ${mode === "strengths" ? "opportunities" : "risks"} feature not yet available`,
            });
          },
        },
      });
    });

    return nodes;
  };

  // Generate edges for React Flow
  const generateEdges = (): Edge[] => {
    if (!selectedParent) return [];

    return children.map((child) => ({
      id: `${selectedParent.node_id}-${child.node_id}`,
      source: selectedParent.node_id,
      target: child.node_id,
      type: "smoothstep",
      style: DEFAULT_EDGE_STYLE,
      sourceHandle: "bottom",
      targetHandle: "top",
    }));
  };

  // Handle node clicks in React Flow
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    if (isEditing) {
      const hasChanges =
        (selectedParent &&
          (formData.display_name.trim() !==
            selectedParent.display_name.trim() ||
            formData.description.trim() !==
              selectedParent.description.trim())) ||
        (selectedChild &&
          (formData.display_name.trim() !== selectedChild.display_name.trim() ||
            formData.description.trim() !== selectedChild.description.trim()));

      if (hasChanges) {
        const childItem = children.find((c) => c.node_id === node.id);
        const parentItem = items.find((i) => i.node_id === node.id);

        if (childItem) {
          setPendingNode({ type: "child", data: childItem });
          setIsUnsavedChangesDialogOpen(true);
        } else if (parentItem) {
          setPendingNode({ type: "parent", data: parentItem });
          setIsUnsavedChangesDialogOpen(true);
        }
        return;
      } else {
        setIsEditing(false);
      }
    }

    const isChildNode =
      (mode === "strengths" && node.type === "opportunityNode") ||
      (mode === "weaknesses" && node.type === "riskNode");

    if (isChildNode) {
      const child = children.find((c) => c.node_id === node.id);
      if (!child) return;

      setSelectedChildId(node.id);
      setSelectedChild(child);

      setFormData({
        display_name: child.display_name,
        description: child.description,
      });

      setContextMenuType("child");
      setIsContextMenuOpen(true);
      setIsEditing(false);
    } else {
      const parent = items.find((i) => i.node_id === node.id);
      if (!parent) return;

      setSelectedChildId(null);
      setSelectedChild(null);
      setSelectedParentId(parent.node_id);
      setSelectedParent(parent);

      setFormData({
        display_name: parent.display_name,
        description: parent.description,
      });

      setContextMenuType("parent");
      setIsContextMenuOpen(true);
      setIsEditing(false);
    }
  };

  const handleDiscardChanges = () => {
    if (!pendingNode) return;

    setIsEditing(false);
    setIsUnsavedChangesDialogOpen(false);

    if (pendingNode.type === "child") {
      const child = pendingNode.data as Opportunity | Risk;
      setSelectedChildId(child.node_id);
      setSelectedChild(child);

      setFormData({
        display_name: child.display_name,
        description: child.description,
      });

      setContextMenuType("child");
      setIsContextMenuOpen(true);
    } else {
      const parent = pendingNode.data as Strength | Weakness;

      setSelectedChildId(null);
      setSelectedChild(null);
      setSelectedParentId(parent.node_id);
      setSelectedParent(parent);

      setFormData({
        display_name: parent.display_name,
        description: parent.description,
      });

      setContextMenuType("parent");
      setIsContextMenuOpen(true);
    }

    setPendingNode(null);
  };

  const handleCreateChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedParent) return;
    if (
      !childFormData.display_name.trim() ||
      !childFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: `${mode === "strengths" ? "Opportunity" : "Risk"} name and description are required`,
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "opportunity" : "risk";
      startOperation(`Creating ${label}...`);
      setIsCreateChildModalOpen(false);

      let newChild;
      if (mode === "strengths") {
        const opportunityData: OpportunityCreate = {
          display_name: childFormData.display_name,
          description: childFormData.description,
          strength_node_id: selectedParent.node_id,
          references: childFormData.references?.filter((r) => r.trim()) || [],
        };

        newChild = await createOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          opportunity: opportunityData,
        });
      } else {
        const riskData: RiskCreate = {
          display_name: childFormData.display_name,
          description: childFormData.description,
          weakness_node_id: selectedParent.node_id,
          references: childFormData.references?.filter((r) => r.trim()) || [],
        };

        newChild = await createRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          risk: riskData,
        });
      }

      setSelectedChildId(newChild.node_id);
      setSelectedChild(newChild);

      setFormData({
        display_name: newChild.display_name,
        description: newChild.description,
      });

      setContextMenuType("child");
      setIsContextMenuOpen(true);

      setChildFormData({
        display_name: "",
        description: "",
        strength_node_id: "",
        weakness_node_id: "",
        references: [],
      } as OpportunityCreate | RiskCreate);

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Opportunity" : "Risk"} created successfully`,
      });
    } catch (error) {
      console.error(`Failed to create ${mode}:`, error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail ||
          `Failed to create ${mode === "strengths" ? "opportunity" : "risk"}`;

        if (status === 409) {
          toast({
            title: "Duplicate",
            description: `A ${mode === "strengths" ? "opportunity" : "risk"} with this name already exists`,
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to create ${mode === "strengths" ? "opportunities" : "risks"}`,
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

  const handleChildSave = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild || !selectedParent)
      return;

    if (!formData.display_name.trim() || !formData.description.trim()) {
      toast({
        title: "Validation Error",
        description: `${mode === "strengths" ? "Opportunity" : "Risk"} name and description are required`,
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "opportunity" : "risk";
      startOperation(`Updating ${label}...`);
      setIsEditing(false);

      const updateData = {
        display_name: formData.display_name.trim(),
        description: formData.description.trim(),
      };

      let updatedChild;
      if (mode === "strengths") {
        updatedChild = await updateOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: updateData,
          strengthId: selectedParent.node_id,
        });
      } else {
        updatedChild = await updateRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: updateData,
          weaknessId: selectedParent.node_id,
        });
      }

      setSelectedChild(updatedChild);

      setFormData({
        display_name: updatedChild.display_name,
        description: updatedChild.description,
      });

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Opportunity" : "Risk"} updated successfully`,
      });
    } catch (error) {
      console.error(
        `Failed to update ${mode === "strengths" ? "opportunity" : "risk"}:`,
        error,
      );

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail ||
          `Failed to update ${mode === "strengths" ? "opportunity" : "risk"}`;

        if (status === 409) {
          toast({
            title: "Duplicate",
            description: `A ${mode === "strengths" ? "opportunity" : "risk"} with this name already exists`,
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to edit ${mode === "strengths" ? "opportunities" : "risks"}`,
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

  const handleDeleteChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild || !selectedParent)
      return;

    try {
      const label = mode === "strengths" ? "opportunity" : "risk";
      startOperation(`Deleting ${label}...`);
      setIsDeleteChildDialogOpen(false);

      if (mode === "strengths") {
        await deleteOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          strengthId: selectedParent.node_id,
        });
      } else {
        await deleteRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          weaknessId: selectedParent.node_id,
        });
      }

      setIsContextMenuOpen(false);
      setSelectedChildId(null);
      setSelectedChild(null);

      toast({
        title: "Success",
        description: `${mode === "strengths" ? "Opportunity" : "Risk"} deleted successfully`,
      });
    } catch (error) {
      console.error(
        `Failed to delete ${mode === "strengths" ? "opportunity" : "risk"}:`,
        error,
      );

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail ||
          `Failed to delete ${mode === "strengths" ? "opportunity" : "risk"}`;

        if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to delete ${mode === "strengths" ? "opportunities" : "risks"}`,
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

  const parentIcon = mode === "strengths" ? Dumbbell : Unlink;
  const childIcon = mode === "strengths" ? Star : ShieldAlert;
  const parentLabel = mode === "strengths" ? "Strength" : "Weakness";
  const childLabel = mode === "strengths" ? "Opportunity" : "Risk";
  const childrenLabel = mode === "strengths" ? "Opportunities" : "Risks";

  const nodes = useMemo(
    () => generateNodes(),
    [selectedParent, children, selectedChildId],
  );
  const edges = useMemo(() => generateEdges(), [selectedParent, children]);

  return (
    <>
      {/* Mode Selector - Outside card */}
      <ModeSelector
        modes={SWOT_MODES}
        value={mode}
        onChange={handleModeSwitch}
        className="mb-6"
      />

      {/* Parent Items Card (Strengths or Weaknesses) */}
      <KnowledgeGraphCard
        title={mode === "strengths" ? "Strengths" : "Weaknesses"}
        icon={parentIcon}
        tooltip={
          mode === "strengths"
            ? "Identify your business strengths to help KEN-E understand what your company excels at and how to leverage these advantages."
            : "Identify areas where your business needs improvement to help KEN-E understand potential vulnerabilities."
        }
        actions={
          hasEditAccess ? (
            <Button
              onClick={handleCreateClick}
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0"
            >
              <Plus className="h-5 w-5" />
            </Button>
          ) : undefined
        }
      >
        <HorizontalScrollList
          items={items}
          selectedId={selectedParentId}
          onItemClick={handleParentClick}
          isLoading={isLoadingItems}
          emptyMessage={`No ${mode} found.`}
          emptyMessageWithAction="Click '+' to add one."
          hasEditAccess={hasEditAccess}
          renderItem={(item, isSelected) => {
            const ItemIcon = mode === "strengths" ? Dumbbell : Unlink;
            const bgColor =
              mode === "strengths"
                ? "bg-brand-light-green"
                : "bg-brand-light-red";

            return (
              <HorizontalScrollItem
                label={item.display_name}
                sublabel={parentLabel}
                icon={ItemIcon}
                bgColor={`${bgColor} bg-opacity-30`}
                iconBgColor={bgColor}
                isSelected={isSelected}
                onClick={() => {}}
              />
            );
          }}
        />
      </KnowledgeGraphCard>

      {/* Children Visualization Card (Opportunities or Risks) */}
      <div className="mt-6">
        <GraphVisualizationCard
          title={childrenLabel}
          icon={childIcon}
          tooltip={
            mode === "strengths"
              ? "Identify opportunities that arise from the selected strength. These are potential areas for growth and strategic advantage."
              : "Identify risks that arise from the selected weakness. These are potential threats that need mitigation."
          }
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeClick}
          isLoading={isLoadingChildren}
          showEmpty={!selectedParentId}
          emptyMessage={`Select a ${mode === "strengths" ? "strength" : "weakness"} to view ${mode === "strengths" ? "opportunities" : "risks"}.`}
        />
      </div>

      {/* Create Parent Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create {parentLabel}</DialogTitle>
            <DialogDescription>
              Add a new {mode === "strengths" ? "strength" : "weakness"} to your
              business.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-name">{parentLabel} Name</Label>
              <Input
                id="create-name"
                value={formData.display_name}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value })
                }
                placeholder={
                  mode === "strengths"
                    ? "e.g., Strong Brand Recognition"
                    : "e.g., Limited Market Presence"
                }
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
                placeholder={`Describe this ${mode === "strengths" ? "strength" : "weakness"}...`}
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

      {/* Delete Parent Confirmation */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {parentLabel}?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedParent?.display_name}"?
              This action cannot be undone.
              {selectedParent && (
                <span className="block mt-2 text-dashboard-gray-600">
                  Note: {mode === "strengths" ? "Strengths" : "Weaknesses"} with
                  linked {mode === "strengths" ? "opportunities" : "risks"}{" "}
                  cannot be deleted.
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

      {/* Delete Child Confirmation */}
      <AlertDialog
        open={isDeleteChildDialogOpen}
        onOpenChange={setIsDeleteChildDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {childLabel}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedChild?.display_name}"?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteChild}
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

      {/* Create Child Modal */}
      <Dialog
        open={isCreateChildModalOpen}
        onOpenChange={setIsCreateChildModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create {childLabel}</DialogTitle>
            <DialogDescription>
              Add a new {mode === "strengths" ? "opportunity" : "risk"} to{" "}
              {selectedParent?.display_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-child-name">{childLabel} Name *</Label>
              <Input
                id="create-child-name"
                value={childFormData.display_name}
                onChange={(e) =>
                  setChildFormData({
                    ...childFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder={
                  mode === "strengths"
                    ? "e.g., Expand into new markets"
                    : "e.g., Economic downturn impact"
                }
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="create-child-description">Description *</Label>
              <Textarea
                id="create-child-description"
                value={childFormData.description}
                onChange={(e) =>
                  setChildFormData({
                    ...childFormData,
                    description: e.target.value,
                  })
                }
                placeholder={`Describe this ${mode === "strengths" ? "opportunity" : "risk"}...`}
                rows={4}
                maxLength={4000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateChildModalOpen(false);
                setChildFormData({
                  display_name: "",
                  description: "",
                  strength_node_id: "",
                  weakness_node_id: "",
                  references: [],
                } as OpportunityCreate | RiskCreate);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateChild}
              disabled={
                !childFormData.display_name.trim() ||
                !childFormData.description.trim()
              }
            >
              Create {childLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Node Context Menu Side Sheet */}
      <KnowledgeGraphSideSheet
        open={isContextMenuOpen}
        modal={false}
        onOpenChange={(open) => {
          if (!open && isEditing) {
            const hasChanges =
              (selectedParent &&
                (formData.display_name.trim() !==
                  selectedParent.display_name.trim() ||
                  formData.description.trim() !==
                    selectedParent.description.trim())) ||
              (selectedChild &&
                (formData.display_name.trim() !==
                  selectedChild.display_name.trim() ||
                  formData.description.trim() !==
                    selectedChild.description.trim()));

            if (hasChanges) {
              return;
            }
          }
          setIsContextMenuOpen(open);
          if (!open) {
            setIsEditing(false);
          }
        }}
        title={contextMenuType === "parent" ? parentLabel : childLabel}
        icon={
          contextMenuType === "parent"
            ? mode === "strengths"
              ? Dumbbell
              : Unlink
            : mode === "strengths"
              ? Star
              : ShieldAlert
        }
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onSave={contextMenuType === "parent" ? handleSave : handleChildSave}
        onCancel={() => {
          setIsEditing(false);
          if (selectedParent && contextMenuType === "parent") {
            setFormData({
              display_name: selectedParent.display_name,
              description: selectedParent.description,
            });
          } else if (selectedChild && contextMenuType === "child") {
            setFormData({
              display_name: selectedChild.display_name,
              description: selectedChild.description,
            });
          }
        }}
        onDelete={() => {
          if (contextMenuType === "parent" && selectedParent) {
            setIsContextMenuOpen(false);
            handleDeleteClick(selectedParent);
          } else if (contextMenuType === "child" && selectedChild) {
            setIsContextMenuOpen(false);
            setIsDeleteChildDialogOpen(true);
          }
        }}
        hasEditAccess={hasEditAccess}
        preventClose={isEditing}
      >
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
                {contextMenuType === "parent"
                  ? selectedParent?.display_name
                  : selectedChild?.display_name}
              </p>
            </div>
            <div>
              <p className="font-semibold">Description:</p>
              <p className="text-sm text-dashboard-gray-600">
                {contextMenuType === "parent"
                  ? selectedParent?.description
                  : selectedChild?.description}
              </p>
            </div>
          </div>
        )}
      </KnowledgeGraphSideSheet>
    </>
  );
};

import { useState, useEffect, useRef, useMemo } from "react";
import { ReactFlow, Controls, Background } from "reactflow";
import type { Node, Edge } from "reactflow";
import "reactflow/dist/style.css";
import {
  Plus,
  Trash2,
  Users,
  ChevronLeft,
  ChevronRight,
  Pencil,
  ThumbsUp,
  ThumbsDown,
  Package,
  Loader2,
  Info,
  ShieldAlert,
  Star,
  Megaphone,
  Dumbbell,
  Unlink,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountOperations } from "@/contexts/AccountOperationsContext";
import type {
  Competitor,
  CompetitorCreate,
} from "@/services/competitorService";
import type {
  CompetitorStrength,
  CompetitorStrengthCreate,
} from "@/services/competitorStrengthService";
import type {
  CompetitorWeakness,
  CompetitorWeaknessCreate,
} from "@/services/competitorWeaknessService";
import type {
  SubstituteProduct,
  SubstituteProductCreate,
} from "@/services/substituteProductService";
import type {
  CompetitorTactic,
  CompetitorTacticCreate,
} from "@/services/competitorTacticService";
import type { Risk, RiskCreate } from "@/services/riskService";
import type {
  Opportunity,
  OpportunityCreate,
} from "@/services/opportunityService";
import type {
  ValueProposition,
  ValuePropositionCreate,
} from "@/services/valuePropositionService";
import {
  useCompetitors,
  useCreateCompetitor,
  useUpdateCompetitor,
  useDeleteCompetitor,
  useCompetitorStrengths,
  useCreateCompetitorStrength,
  useUpdateCompetitorStrength,
  useDeleteCompetitorStrength,
  useCompetitorWeaknesses,
  useCreateCompetitorWeakness,
  useUpdateCompetitorWeakness,
  useDeleteCompetitorWeakness,
  useSubstituteProducts,
  useCreateSubstituteProduct,
  useUpdateSubstituteProduct,
  useDeleteSubstituteProduct,
  useCompetitorTactics,
  useCreateCompetitorTactic,
  useUpdateCompetitorTactic,
  useDeleteCompetitorTactic,
} from "@/queries/competitors";
import {
  useRisks,
  useCreateRisk,
  useUpdateRisk,
  useDeleteRisk,
  useOpportunities,
  useCreateOpportunity,
  useUpdateOpportunity,
  useDeleteOpportunity,
} from "@/queries/swot";
import {
  useValuePropositions,
  useCreateValueProposition,
  useUpdateValueProposition,
  useDeleteValueProposition,
} from "@/queries/products";
import {
  CompetitorNode,
  CompetitorStrengthNode,
  CompetitorWeaknessNode,
  SubstituteProductNode,
  RiskNode,
  OpportunityNode,
} from "./CompetitorFlowNodes";
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

type CompetitorMode = "strengths" | "weaknesses" | "substitute-products";

interface CompetitorsManagementProps {
  hasEditAccess: boolean;
}

interface FormDataState {
  display_name: string;
  description: string;
  product_name?: string;
  product_detail_page?: string;
}

export const CompetitorsManagement = ({
  hasEditAccess,
}: CompetitorsManagementProps) => {
  const { selectedOrgAccount } = useAuth();
  const { startOperation, endOperation } = useAccountOperations();
  const { toast } = useToast();

  // Mode state
  const [mode, setMode] = useState<CompetitorMode>("strengths");

  // Fetch competitors
  const { data: competitorsData, isLoading: isLoadingCompetitors } =
    useCompetitors(selectedOrgAccount?.accountId || null);
  const competitors = competitorsData?.competitors || [];

  // Selected competitor state
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<
    string | null
  >(null);
  const [selectedCompetitor, setSelectedCompetitor] =
    useState<Competitor | null>(null);

  // Competitor UI state
  const [isCreateCompetitorModalOpen, setIsCreateCompetitorModalOpen] =
    useState(false);
  const [isDeleteCompetitorDialogOpen, setIsDeleteCompetitorDialogOpen] =
    useState(false);
  const [competitorFormData, setCompetitorFormData] =
    useState<CompetitorCreate>({
      display_name: "",
      description: "",
      references: [],
    });

  // Scroll state
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Child node state (strength, weakness, or substitute product) - MUST be before queries
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);
  const [selectedChild, setSelectedChild] = useState<
    CompetitorStrength | CompetitorWeakness | SubstituteProduct | null
  >(null);

  // Grandchild state (risk or opportunity)
  const [selectedGrandchildId, setSelectedGrandchildId] = useState<
    string | null
  >(null);
  const [selectedGrandchild, setSelectedGrandchild] = useState<
    Risk | Opportunity | null
  >(null);

  // Fetch children based on mode and selected competitor
  const { data: strengthsData, isLoading: isLoadingStrengths } =
    useCompetitorStrengths(
      mode === "strengths" ? selectedOrgAccount?.accountId || null : null,
      mode === "strengths" ? selectedCompetitorId : null,
    );
  const strengths = strengthsData?.strengths || [];

  const { data: weaknessesData, isLoading: isLoadingWeaknesses } =
    useCompetitorWeaknesses(
      mode === "weaknesses" ? selectedOrgAccount?.accountId || null : null,
      mode === "weaknesses" ? selectedCompetitorId : null,
    );
  const weaknesses = weaknessesData?.weaknesses || [];

  const {
    data: substituteProductsData,
    isLoading: isLoadingSubstituteProducts,
  } = useSubstituteProducts(
    mode === "substitute-products"
      ? selectedOrgAccount?.accountId || null
      : null,
    mode === "substitute-products" ? selectedCompetitorId : null,
  );
  const substituteProducts = substituteProductsData?.products || [];

  // Grandchildren (risks from strengths, opportunities from weaknesses)
  const selectedStrength =
    mode === "strengths"
      ? strengths.find((s) => s.node_id === selectedChildId)
      : null;
  const selectedWeakness =
    mode === "weaknesses"
      ? weaknesses.find((w) => w.node_id === selectedChildId)
      : null;

  const { data: risksData, isLoading: isLoadingRisks } = useRisks(
    mode === "strengths" && selectedStrength?.node_id
      ? selectedOrgAccount?.accountId || null
      : null,
    mode === "strengths" && selectedStrength?.node_id
      ? selectedStrength.node_id
      : null,
  );
  const risks = risksData?.risks || [];

  const { data: opportunitiesData, isLoading: isLoadingOpportunities } =
    useOpportunities(
      mode === "weaknesses" && selectedWeakness?.node_id
        ? selectedOrgAccount?.accountId || null
        : null,
      mode === "weaknesses" && selectedWeakness?.node_id
        ? selectedWeakness.node_id
        : null,
    );
  const opportunities = opportunitiesData?.opportunities || [];

  // Context menu state
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [contextMenuType, setContextMenuType] = useState<
    "competitor" | "child" | "grandchild" | null
  >(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormDataState>({
    display_name: "",
    description: "",
  });

  // Create/delete dialogs for children
  const [isCreateChildModalOpen, setIsCreateChildModalOpen] = useState(false);
  const [isDeleteChildDialogOpen, setIsDeleteChildDialogOpen] = useState(false);
  const [isCreateGrandchildModalOpen, setIsCreateGrandchildModalOpen] =
    useState(false);
  const [isDeleteGrandchildDialogOpen, setIsDeleteGrandchildDialogOpen] =
    useState(false);

  // Child form data
  const [childFormData, setChildFormData] = useState<
    | CompetitorStrengthCreate
    | CompetitorWeaknessCreate
    | SubstituteProductCreate
  >({
    display_name: "",
    description: "",
    competitor_node_id: "",
    references: [],
  });

  // Grandchild form data
  const [grandchildFormData, setGrandchildFormData] = useState<
    RiskCreate | OpportunityCreate
  >({
    display_name: "",
    description: "",
    weakness_node_id: "",
    references: [],
  });

  // Tactics state (shown in competitor side sheet)
  const { data: tacticsData, isLoading: isLoadingTactics } =
    useCompetitorTactics(
      selectedCompetitorId ? selectedOrgAccount?.accountId || null : null,
      selectedCompetitorId,
    );
  const tactics = tacticsData?.tactics || [];

  const [selectedTactic, setSelectedTactic] = useState<CompetitorTactic | null>(
    null,
  );
  const [isCreateTacticModalOpen, setIsCreateTacticModalOpen] = useState(false);
  const [isDeleteTacticDialogOpen, setIsDeleteTacticDialogOpen] =
    useState(false);
  const [tacticFormData, setTacticFormData] = useState<CompetitorTacticCreate>({
    display_name: "",
    description: "",
    competitor_node_id: "",
    references: [],
  });

  // Value Propositions state (for substitute products)
  const { data: valuePropositionsData, isLoading: isLoadingVPs } =
    useValuePropositions(
      mode === "substitute-products" && selectedChildId
        ? selectedOrgAccount?.accountId || null
        : null,
      mode === "substitute-products" && selectedChildId
        ? selectedChildId
        : null,
    );
  const valuePropositions = valuePropositionsData?.value_propositions || [];

  const [selectedValueProposition, setSelectedValueProposition] =
    useState<ValueProposition | null>(null);
  const [isCreateVPModalOpen, setIsCreateVPModalOpen] = useState(false);
  const [isDeleteVPDialogOpen, setIsDeleteVPDialogOpen] = useState(false);
  const [valuePropositionFormData, setValuePropositionFormData] =
    useState<ValuePropositionCreate>({
      display_name: "",
      description: "",
      parent_node_id: "",
      parent_node_type: "SubstituteProduct",
      references: [],
    });

  // Mutations
  const createCompetitorMutation = useCreateCompetitor();
  const updateCompetitorMutation = useUpdateCompetitor();
  const deleteCompetitorMutation = useDeleteCompetitor();

  const createStrengthMutation = useCreateCompetitorStrength();
  const updateStrengthMutation = useUpdateCompetitorStrength();
  const deleteStrengthMutation = useDeleteCompetitorStrength();

  const createWeaknessMutation = useCreateCompetitorWeakness();
  const updateWeaknessMutation = useUpdateCompetitorWeakness();
  const deleteWeaknessMutation = useDeleteCompetitorWeakness();

  const createSubstituteProductMutation = useCreateSubstituteProduct();
  const updateSubstituteProductMutation = useUpdateSubstituteProduct();
  const deleteSubstituteProductMutation = useDeleteSubstituteProduct();

  const createRiskMutation = useCreateRisk();
  const updateRiskMutation = useUpdateRisk();
  const deleteRiskMutation = useDeleteRisk();

  const createOpportunityMutation = useCreateOpportunity();
  const updateOpportunityMutation = useUpdateOpportunity();
  const deleteOpportunityMutation = useDeleteOpportunity();

  const createTacticMutation = useCreateCompetitorTactic();
  const updateTacticMutation = useUpdateCompetitorTactic();
  const deleteTacticMutation = useDeleteCompetitorTactic();

  const createVPMutation = useCreateValueProposition();
  const updateVPMutation = useUpdateValueProposition();
  const deleteVPMutation = useDeleteValueProposition();

  // Scroll position check
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
  }, [competitors]);

  // Mode switch handler
  const handleModeSwitch = (newMode: CompetitorMode) => {
    if (isEditing) {
      toast({
        title: "Unsaved Changes",
        description:
          "Please save or cancel your changes before switching modes",
        variant: "destructive",
      });
      return;
    }

    setMode(newMode);
    setSelectedChildId(null);
    setSelectedChild(null);
    setSelectedGrandchildId(null);
    setSelectedGrandchild(null);
    setIsContextMenuOpen(false);
  };

  // Competitor handlers
  const handleCompetitorClick = (competitor: Competitor) => {
    setSelectedCompetitorId(competitor.node_id);
    setSelectedCompetitor(competitor);
    setSelectedChildId(null);
    setSelectedChild(null);
    setSelectedGrandchildId(null);
    setSelectedGrandchild(null);
  };

  const handleCreateCompetitor = async () => {
    if (!selectedOrgAccount?.accountId) return;
    if (!competitorFormData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Competitor name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating competitor...");
      setIsCreateCompetitorModalOpen(false);

      await createCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        competitor: competitorFormData,
      });

      toast({
        title: "Success",
        description: "Competitor created successfully",
      });

      setCompetitorFormData({
        display_name: "",
        description: "",
        references: [],
      });
    } catch (error) {
      console.error("Failed to create competitor:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to create competitor";

        if (status === 409) {
          toast({
            title: "Duplicate Competitor",
            description: "A competitor with this name already exists",
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: "You don't have permission to create competitors",
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

  const handleUpdateCompetitor = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;
    if (!formData.display_name.trim()) {
      toast({
        title: "Validation Error",
        description: "Competitor name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Updating competitor...");
      setIsEditing(false);

      const updatedCompetitor = await updateCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCompetitor.node_id,
        updates: {
          display_name: formData.display_name,
          description: formData.description,
        },
      });

      setSelectedCompetitor(updatedCompetitor);

      toast({
        title: "Success",
        description: "Competitor updated successfully",
      });
    } catch (error) {
      console.error("Failed to update competitor:", error);

      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update competitor";
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

  const handleDeleteCompetitor = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    try {
      startOperation("Deleting competitor...");
      setIsDeleteCompetitorDialogOpen(false);

      await deleteCompetitorMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedCompetitor.node_id,
      });

      setSelectedCompetitorId(null);
      setSelectedCompetitor(null);
      setSelectedChildId(null);
      setSelectedChild(null);
      setIsContextMenuOpen(false);

      toast({
        title: "Success",
        description: "Competitor deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete competitor:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const message =
          error.response?.data?.detail || "Failed to delete competitor";

        if (status === 400 && message.includes("dependencies")) {
          toast({
            title: "Cannot Delete",
            description:
              "This competitor has linked data. Remove strengths, weaknesses, and products first.",
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

  // React Flow node types (no competitor node, only child → grandchild)
  const nodeTypes = useMemo(() => {
    if (mode === "strengths") {
      return {
        competitorStrengthNode: CompetitorStrengthNode,
        riskNode: RiskNode,
      };
    } else if (mode === "weaknesses") {
      return {
        competitorWeaknessNode: CompetitorWeaknessNode,
        opportunityNode: OpportunityNode,
      };
    } else {
      // Should not be used since substitute-products doesn't show React Flow
      return {};
    }
  }, [mode]);

  // Generate nodes for React Flow (only 2 levels: child → grandchildren)
  const generateNodes = (): Node[] => {
    if (!selectedChild) return [];

    const nodes: Node[] = [];
    const gap = 36;

    // Only show child → grandchildren (not competitor)
    if (mode === "strengths") {
      const strength = selectedChild as CompetitorStrength;

      // Child Node (strength) - top center
      nodes.push({
        id: strength.node_id,
        type: "competitorStrengthNode",
        position: { x: 300, y: 50 },
        data: {
          label: strength.display_name,
          isSelected: !selectedGrandchildId,
          onAddRisk: () => setIsCreateGrandchildModalOpen(true),
        },
      });

      // Grandchild nodes (risks) - second row
      const grandchildren = risks;
      const grandchildWidth = 224;
      const grandchildTotalWidth =
        grandchildren.length * (grandchildWidth + gap) - gap;
      const grandchildStartX = 300 - grandchildTotalWidth / 2;

      grandchildren.forEach((risk, index) => {
        nodes.push({
          id: risk.node_id,
          type: "riskNode",
          position: {
            x: grandchildStartX + index * (grandchildWidth + gap),
            y: 224,
          },
          data: {
            label: risk.display_name,
            showHandle: false,
            isSelected: selectedGrandchildId === risk.node_id,
            onAddSubstitute: () => {},
          },
        });
      });
    } else if (mode === "weaknesses") {
      const weakness = selectedChild as CompetitorWeakness;

      // Child Node (weakness) - top center
      nodes.push({
        id: weakness.node_id,
        type: "competitorWeaknessNode",
        position: { x: 300, y: 50 },
        data: {
          label: weakness.display_name,
          isSelected: !selectedGrandchildId,
          onAddOpportunity: () => setIsCreateGrandchildModalOpen(true),
        },
      });

      // Grandchild nodes (opportunities) - second row
      const grandchildren = opportunities;
      const grandchildWidth = 224;
      const grandchildTotalWidth =
        grandchildren.length * (grandchildWidth + gap) - gap;
      const grandchildStartX = 300 - grandchildTotalWidth / 2;

      grandchildren.forEach((opportunity, index) => {
        nodes.push({
          id: opportunity.node_id,
          type: "opportunityNode",
          position: {
            x: grandchildStartX + index * (grandchildWidth + gap),
            y: 224,
          },
          data: {
            label: opportunity.display_name,
            showHandle: false,
            isSelected: selectedGrandchildId === opportunity.node_id,
            onAddSubstitute: () => {},
          },
        });
      });
    }

    return nodes;
  };

  // Generate edges for React Flow (only child → grandchildren edges)
  const generateEdges = (): Edge[] => {
    if (!selectedChild) return [];

    const edges: Edge[] = [];

    // Edges from child to grandchildren only
    if (mode === "strengths" && selectedChildId) {
      risks.forEach((risk) => {
        edges.push({
          id: `${selectedChildId}-${risk.node_id}`,
          source: selectedChildId,
          target: risk.node_id,
          type: "smoothstep",
          style: {
            stroke: "#000",
            strokeWidth: 2,
          },
          sourceHandle: "bottom",
          targetHandle: "top",
        });
      });
    } else if (mode === "weaknesses" && selectedChildId) {
      opportunities.forEach((opportunity) => {
        edges.push({
          id: `${selectedChildId}-${opportunity.node_id}`,
          source: selectedChildId,
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
    }

    return edges;
  };

  // Handle node clicks in React Flow
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    if (isEditing) {
      toast({
        title: "Unsaved Changes",
        description: "Please save or cancel your changes first",
        variant: "destructive",
      });
      return;
    }

    // Child nodes (strength/weakness) - now at top level of diagram
    if (
      node.type === "competitorStrengthNode" ||
      node.type === "competitorWeaknessNode"
    ) {
      // Just open the side sheet for the already-selected child
      if (selectedChild) {
        setFormData({
          display_name: selectedChild.display_name,
          description: selectedChild.description,
        });

        setContextMenuType("child");
        setIsContextMenuOpen(true);
      }
      return;
    }

    // Grandchild nodes (risk or opportunity)
    if (node.type === "riskNode" || node.type === "opportunityNode") {
      const grandchildren = mode === "strengths" ? risks : opportunities;
      const grandchild = grandchildren.find((g) => g.node_id === node.id);
      if (!grandchild) return;

      setSelectedGrandchildId(node.id);
      setSelectedGrandchild(grandchild);

      setFormData({
        display_name: grandchild.display_name,
        description: grandchild.description,
      });

      setContextMenuType("grandchild");
      setIsContextMenuOpen(true);
    }
  };

  // Create child (strength, weakness, or substitute product)
  const handleCreateChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    if (
      !childFormData.display_name.trim() ||
      !childFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Creating ${childType}...`);
      setIsCreateChildModalOpen(false);

      if (mode === "strengths") {
        await createStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          strength: {
            ...childFormData,
            competitor_node_id: selectedCompetitor.node_id,
          } as CompetitorStrengthCreate,
        });
      } else if (mode === "weaknesses") {
        await createWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          weakness: {
            ...childFormData,
            competitor_node_id: selectedCompetitor.node_id,
          } as CompetitorWeaknessCreate,
        });
      } else {
        const subProductData = childFormData as SubstituteProductCreate;
        await createSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          product: {
            product_name: subProductData.display_name,
            description: subProductData.description,
            competitor_node_id: selectedCompetitor.node_id,
            references: subProductData.references || [],
            product_detail_page: (subProductData as any).product_detail_page,
          },
        });
      }

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} created successfully`,
      });

      setChildFormData({
        display_name: "",
        description: "",
        competitor_node_id: "",
        references: [],
      });
    } catch (error) {
      console.error("Failed to create child:", error);

      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const childType =
          mode === "strengths"
            ? "strength"
            : mode === "weaknesses"
              ? "weakness"
              : "substitute product";
        const message =
          error.response?.data?.detail || `Failed to create ${childType}`;

        if (status === 409) {
          toast({
            title: "Duplicate",
            description: `A ${childType} with this name already exists`,
            variant: "destructive",
          });
        } else if (status === 403) {
          toast({
            title: "Permission Denied",
            description: `You don't have permission to create ${childType}s`,
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

  // Update child
  const handleUpdateChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    if (!formData.display_name.trim() && !formData.product_name?.trim()) {
      toast({
        title: "Validation Error",
        description: "Name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Updating ${childType}...`);
      setIsEditing(false);

      if (mode === "strengths") {
        await updateStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            display_name: formData.display_name,
            description: formData.description,
          },
        });
      } else if (mode === "weaknesses") {
        await updateWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            display_name: formData.display_name,
            description: formData.description,
          },
        });
      } else {
        await updateSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
          updates: {
            product_name: formData.product_name,
            description: formData.description,
            product_detail_page: formData.product_detail_page,
          },
        });
      }

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} updated successfully`,
      });
    } catch (error) {
      console.error("Failed to update child:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to update";
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

  // Delete child
  const handleDeleteChild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    try {
      const childType =
        mode === "strengths"
          ? "strength"
          : mode === "weaknesses"
            ? "weakness"
            : "substitute product";
      startOperation(`Deleting ${childType}...`);
      setIsDeleteChildDialogOpen(false);

      if (mode === "strengths") {
        await deleteStrengthMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      } else if (mode === "weaknesses") {
        await deleteWeaknessMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      } else {
        await deleteSubstituteProductMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedChild.node_id,
        });
      }

      setIsContextMenuOpen(false);
      setSelectedChildId(null);
      setSelectedChild(null);
      setSelectedGrandchildId(null);
      setSelectedGrandchild(null);

      toast({
        title: "Success",
        description: `${childType.charAt(0).toUpperCase() + childType.slice(1)} deleted successfully`,
      });
    } catch (error) {
      console.error("Failed to delete child:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to delete";
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

  // Create grandchild (risk or opportunity)
  const handleCreateGrandchild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedChild) return;

    if (
      !grandchildFormData.display_name.trim() ||
      !grandchildFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Creating ${label}...`);
      setIsCreateGrandchildModalOpen(false);

      if (mode === "strengths") {
        await createRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          risk: {
            ...grandchildFormData,
            weakness_node_id: selectedChild.node_id,
          } as RiskCreate,
        });
      } else {
        await createOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          opportunity: {
            ...grandchildFormData,
            strength_node_id: selectedChild.node_id,
          } as OpportunityCreate,
        });
      }

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} created successfully`,
      });

      setGrandchildFormData({
        display_name: "",
        description: "",
        weakness_node_id: "",
        strength_node_id: "",
        references: [],
      } as RiskCreate | OpportunityCreate);
    } catch (error) {
      console.error("Failed to create grandchild:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to create";
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

  // Update grandchild
  const handleUpdateGrandchild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedGrandchild || !selectedChild)
      return;

    if (!formData.display_name.trim() || !formData.description.trim()) {
      toast({
        title: "Validation Error",
        description: "Name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Updating ${label}...`);
      setIsEditing(false);

      const updateData = {
        display_name: formData.display_name.trim(),
        description: formData.description.trim(),
      };

      if (mode === "strengths") {
        await updateRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          updates: updateData,
          weaknessId: selectedChild.node_id,
        });
      } else {
        await updateOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          updates: updateData,
          strengthId: selectedChild.node_id,
        });
      }

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} updated successfully`,
      });
    } catch (error) {
      console.error("Failed to update grandchild:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to update";
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

  // Delete grandchild
  const handleDeleteGrandchild = async () => {
    if (!selectedOrgAccount?.accountId || !selectedGrandchild || !selectedChild)
      return;

    try {
      const label = mode === "strengths" ? "risk" : "opportunity";
      startOperation(`Deleting ${label}...`);
      setIsDeleteGrandchildDialogOpen(false);

      if (mode === "strengths") {
        await deleteRiskMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          weaknessId: selectedChild.node_id,
        });
      } else {
        await deleteOpportunityMutation.mutateAsync({
          accountId: selectedOrgAccount.accountId,
          nodeId: selectedGrandchild.node_id,
          strengthId: selectedChild.node_id,
        });
      }

      setIsContextMenuOpen(false);
      setSelectedGrandchildId(null);
      setSelectedGrandchild(null);

      toast({
        title: "Success",
        description: `${label.charAt(0).toUpperCase() + label.slice(1)} deleted successfully`,
      });
    } catch (error) {
      console.error("Failed to delete grandchild:", error);

      if (axios.isAxiosError(error)) {
        const message = error.response?.data?.detail || "Failed to delete";
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

  // Tactic handlers
  const handleCreateTactic = async () => {
    if (!selectedOrgAccount?.accountId || !selectedCompetitor) return;

    if (
      !tacticFormData.display_name.trim() ||
      !tacticFormData.description.trim()
    ) {
      toast({
        title: "Validation Error",
        description: "Tactic name and description are required",
        variant: "destructive",
      });
      return;
    }

    try {
      startOperation("Creating tactic...");

      await createTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        tactic: {
          ...tacticFormData,
          competitor_node_id: selectedCompetitor.node_id,
        },
      });

      toast({
        title: "Success",
        description: "Tactic created successfully",
      });

      setIsCreateTacticModalOpen(false);
      setTacticFormData({
        display_name: "",
        description: "",
        competitor_node_id: "",
        references: [],
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to create tactic";
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

  const handleUpdateTactic = async () => {
    if (!selectedOrgAccount || !selectedTactic) return;

    try {
      startOperation("Updating tactic...");

      await updateTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedTactic.node_id,
        updates: {
          display_name: tacticFormData.display_name,
          description: tacticFormData.description,
          references: tacticFormData.references,
        },
      });

      toast({
        title: "Success",
        description: "Tactic updated successfully",
      });

      setIsCreateTacticModalOpen(false);
      setSelectedTactic(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update tactic";
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

  const handleDeleteTactic = async () => {
    if (!selectedOrgAccount || !selectedTactic) return;

    try {
      startOperation("Deleting tactic...");

      await deleteTacticMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedTactic.node_id,
      });

      toast({
        title: "Success",
        description: "Tactic deleted successfully",
      });

      setIsDeleteTacticDialogOpen(false);
      setSelectedTactic(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to delete tactic";
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

  // Value Proposition handlers (for substitute products)
  const handleCreateValueProposition = async () => {
    if (!selectedOrgAccount) return;

    try {
      startOperation("Creating value proposition...");

      await createVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        valueProposition: valuePropositionFormData,
      });

      toast({
        title: "Success",
        description: "Value proposition created successfully",
      });

      setIsCreateVPModalOpen(false);
      setValuePropositionFormData({
        display_name: "",
        description: "",
        parent_node_id: "",
        parent_node_type: "SubstituteProduct",
        references: [],
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to create value proposition";
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

  const handleUpdateValueProposition = async () => {
    if (!selectedOrgAccount || !selectedValueProposition) return;

    try {
      startOperation("Updating value proposition...");

      await updateVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedValueProposition.node_id,
        updates: {
          display_name: valuePropositionFormData.display_name,
          description: valuePropositionFormData.description,
          references: valuePropositionFormData.references,
        },
        parentNodeId: valuePropositionFormData.parent_node_id,
      });

      toast({
        title: "Success",
        description: "Value proposition updated successfully",
      });

      setIsCreateVPModalOpen(false);
      setSelectedValueProposition(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to update value proposition";
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

  const handleDeleteValueProposition = async () => {
    if (!selectedOrgAccount || !selectedValueProposition) return;

    try {
      startOperation("Deleting value proposition...");

      await deleteVPMutation.mutateAsync({
        accountId: selectedOrgAccount.accountId,
        nodeId: selectedValueProposition.node_id,
        parentNodeId: valuePropositionFormData.parent_node_id,
      });

      toast({
        title: "Success",
        description: "Value proposition deleted successfully",
      });

      setIsDeleteVPDialogOpen(false);
      setSelectedValueProposition(null);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const message =
          error.response?.data?.detail || "Failed to delete value proposition";
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

  // Derived values
  const isLoadingChildren =
    mode === "strengths"
      ? isLoadingStrengths
      : mode === "weaknesses"
        ? isLoadingWeaknesses
        : isLoadingSubstituteProducts;

  const childLabel =
    mode === "strengths"
      ? "Strength"
      : mode === "weaknesses"
        ? "Weakness"
        : "Substitute Product";

  const childrenLabel =
    mode === "strengths"
      ? "Strengths"
      : mode === "weaknesses"
        ? "Weaknesses"
        : "Substitute Products";

  const grandchildLabel = mode === "strengths" ? "Risk" : "Opportunity";
  const grandchildrenLabel = mode === "strengths" ? "Risks" : "Opportunities";

  // Derived values for children display
  const children =
    mode === "strengths"
      ? strengths
      : mode === "weaknesses"
        ? weaknesses
        : substituteProducts;

  // Get display properties based on mode
  const getChildIcon = () => {
    if (mode === "strengths") return Dumbbell;
    if (mode === "weaknesses") return Unlink;
    return Package;
  };

  const getChildBgColor = () => {
    if (mode === "strengths") return "bg-brand-light-green bg-opacity-30";
    if (mode === "weaknesses") return "bg-brand-light-red bg-opacity-30";
    return "bg-purple-100 bg-opacity-80";
  };

  const getChildIconBgColor = () => {
    if (mode === "strengths") return "bg-brand-light-green";
    if (mode === "weaknesses") return "bg-brand-light-red";
    return "bg-purple-500";
  };

  const ChildIcon = getChildIcon();

  return (
    <>
      {/* Competitors Card */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Competitors
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-dashboard-gray-400" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>
                      Identify key competitors who offer products or services
                      that could be viewed as substitutes by your target
                      customers.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardTitle>
            {hasEditAccess && (
              <Button
                onClick={() => setIsCreateCompetitorModalOpen(true)}
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
          {isLoadingCompetitors ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              Loading competitors...
            </div>
          ) : competitors.length === 0 ? (
            <div className="text-center py-8 text-dashboard-gray-500">
              No competitors found.
              {hasEditAccess && " Click '+' to add one."}
            </div>
          ) : (
            <div className="relative">
              {canScrollLeft && (
                <button
                  className="absolute left-0 top-0 bottom-0 z-20 bg-gray-500 bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity"
                  onClick={scrollLeft}
                >
                  <ChevronLeft className="h-6 w-6 text-white" />
                </button>
              )}

              <div
                ref={scrollContainerRef}
                className="flex gap-3 overflow-x-auto px-2 py-2"
                onScroll={checkScrollPosition}
              >
                {competitors.map((competitor) => (
                  <div
                    key={competitor.node_id}
                    className={`flex-shrink-0 p-4 rounded-lg transition-colors cursor-pointer ${
                      selectedCompetitorId === competitor.node_id
                        ? "ring-2 ring-brand-medium-blue"
                        : "hover:ring-2 hover:ring-gray-300"
                    }`}
                    onClick={() => handleCompetitorClick(competitor)}
                  >
                    <div className="flex items-center">
                      <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
                        <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
                          Competitor
                        </p>
                        <p className="font-semibold text-dashboard-gray-900 leading-tight">
                          {competitor.display_name}
                        </p>
                      </div>

                      <div className="flex-shrink-0 -ml-12 relative z-10">
                        <div
                          className="rounded-full bg-brand-light-blue flex items-center justify-center"
                          style={{ width: "72px", height: "72px" }}
                        >
                          <Users
                            className="text-white"
                            style={{ width: "48px", height: "48px" }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

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

      {/* Children Card (Strengths/Weaknesses/Substitutes) */}
      {selectedCompetitorId && (
        <div className="mt-6">
          <Card className="h-[600px]">
            {/* Mode Switcher - Left justified inside card, above header */}
            <div className="flex p-6 pb-0">
              <div className="inline-flex rounded-md border border-input bg-muted p-1 gap-1">
                <Button
                  variant={mode === "strengths" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeSwitch("strengths")}
                  className="px-6"
                >
                  Strengths
                </Button>
                <Button
                  variant={mode === "weaknesses" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeSwitch("weaknesses")}
                  className="px-6"
                >
                  Weaknesses
                </Button>
                <Button
                  variant={mode === "substitute-products" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeSwitch("substitute-products")}
                  className="px-6"
                >
                  Substitutes
                </Button>
              </div>
            </div>

            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="flex items-center gap-2">
                  <ChildIcon className="h-5 w-5" />
                  {childrenLabel}
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-4 w-4 text-dashboard-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p>
                          {mode === "strengths"
                            ? "Competitor strengths create risks for your business. Identify their advantages and the threats they pose."
                            : mode === "weaknesses"
                              ? "Competitor weaknesses create opportunities for your business. Identify their disadvantages and how you can capitalize."
                              : "Substitute products offered by this competitor that compete with your products or services."}
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </CardTitle>
                {hasEditAccess && (
                  <Button
                    onClick={() => setIsCreateChildModalOpen(true)}
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
              {/* Children horizontal scroll section */}
              {isLoadingChildren ? (
                <div className="text-center py-8 text-dashboard-gray-500">
                  Loading {childrenLabel.toLowerCase()}...
                </div>
              ) : children.length === 0 ? (
                <div className="text-center py-8 text-dashboard-gray-500">
                  No {childrenLabel.toLowerCase()} found.
                  {hasEditAccess && " Click '+' to add one."}
                </div>
              ) : (
                <div className="relative">
                  <div className="flex gap-3 overflow-x-auto px-2 py-2">
                    {children.map((child) => {
                      const isSelected = selectedChildId === child.node_id;
                      const displayName =
                        mode === "substitute-products"
                          ? (child as SubstituteProduct).product_name
                          : child.display_name;

                      return (
                        <div
                          key={child.node_id}
                          className={`flex-shrink-0 p-4 rounded-lg transition-colors cursor-pointer ${
                            isSelected
                              ? "ring-2 ring-brand-medium-blue"
                              : "hover:ring-2 hover:ring-gray-300"
                          }`}
                          onClick={() => {
                            setSelectedChildId(child.node_id);
                            setSelectedChild(child);
                            setSelectedGrandchildId(null);
                            setSelectedGrandchild(null);

                            // For substitute products (no React Flow), open side sheet directly
                            // For strengths/weaknesses, side sheet opens when clicking React Flow nodes
                            if (mode === "substitute-products") {
                              const subProduct = child as SubstituteProduct;
                              setFormData({
                                display_name: "",
                                description: subProduct.description,
                                product_name: subProduct.product_name,
                                product_detail_page:
                                  subProduct.product_detail_page || "",
                              });
                              setContextMenuType("child");
                              setIsContextMenuOpen(true);
                            }
                          }}
                        >
                          <div className="flex items-center">
                            <div
                              className={`${getChildBgColor()} rounded-lg pl-4 pr-16 py-2`}
                            >
                              <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
                                {childLabel}
                              </p>
                              <p className="font-semibold text-dashboard-gray-900 leading-tight">
                                {displayName}
                              </p>
                            </div>

                            <div className="flex-shrink-0 -ml-12 relative z-10">
                              <div
                                className={`rounded-full ${getChildIconBgColor()} flex items-center justify-center`}
                                style={{ width: "72px", height: "72px" }}
                              >
                                <ChildIcon
                                  className="text-white"
                                  style={{ width: "48px", height: "48px" }}
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* React Flow section (only if child selected and not substitutes mode) */}
              {selectedChildId && mode !== "substitute-products" && (
                <div className="mt-6 rounded-lg border bg-card shadow-sm p-6">
                  <div className="flex items-center gap-2 mb-4">
                    {mode === "strengths" ? (
                      <ShieldAlert className="h-5 w-5" />
                    ) : (
                      <Star className="h-5 w-5" />
                    )}
                    <h3 className="text-lg font-semibold">
                      {grandchildrenLabel}
                    </h3>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-4 w-4 text-dashboard-gray-400" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p>
                            {mode === "strengths"
                              ? "Risks created by this competitor strength."
                              : "Opportunities created by this competitor weakness."}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div className="h-[520px]">
                    {isLoadingChildren ||
                    (mode === "strengths" && isLoadingRisks) ||
                    (mode === "weaknesses" && isLoadingOpportunities) ? (
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
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Create Competitor Modal */}
      <Dialog
        open={isCreateCompetitorModalOpen}
        onOpenChange={setIsCreateCompetitorModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Competitor</DialogTitle>
            <DialogDescription>
              Add a new competitor to track in your competitive analysis.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-competitor-name">Competitor Name *</Label>
              <Input
                id="create-competitor-name"
                value={competitorFormData.display_name}
                onChange={(e) =>
                  setCompetitorFormData({
                    ...competitorFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder="e.g., Acme Corp"
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="create-competitor-description">
                Description *
              </Label>
              <Textarea
                id="create-competitor-description"
                value={competitorFormData.description}
                onChange={(e) =>
                  setCompetitorFormData({
                    ...competitorFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Describe this competitor's business, positioning, and market presence..."
                rows={4}
                maxLength={4000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateCompetitorModalOpen(false);
                setCompetitorFormData({
                  display_name: "",
                  description: "",
                  references: [],
                });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateCompetitor}
              disabled={
                !competitorFormData.display_name.trim() ||
                !competitorFormData.description.trim()
              }
            >
              Create Competitor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Competitor Dialog */}
      <AlertDialog
        open={isDeleteCompetitorDialogOpen}
        onOpenChange={setIsDeleteCompetitorDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Competitor</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "
              {selectedCompetitor?.display_name}
              "? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteCompetitor}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Child Modal (Strength, Weakness, or Substitute Product) */}
      <Dialog
        open={isCreateChildModalOpen}
        onOpenChange={setIsCreateChildModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create {childLabel}</DialogTitle>
            <DialogDescription>
              Add a new {childLabel.toLowerCase()} to{" "}
              {selectedCompetitor?.display_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-child-name">
                {mode === "substitute-products" ? "Product Name" : "Name"} *
              </Label>
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
                    ? "e.g., Strong Brand Recognition"
                    : mode === "weaknesses"
                      ? "e.g., Limited Distribution Network"
                      : "e.g., Premium Air Purifier Pro"
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
                placeholder={`Describe this ${childLabel.toLowerCase()}...`}
                rows={4}
                maxLength={4000}
              />
            </div>
            {mode === "substitute-products" && (
              <div>
                <Label htmlFor="create-child-product-page">
                  Product Detail Page (Optional)
                </Label>
                <Input
                  id="create-child-product-page"
                  type="url"
                  value={(childFormData as any).product_detail_page || ""}
                  onChange={(e) =>
                    setChildFormData({
                      ...childFormData,
                      product_detail_page: e.target.value,
                    } as any)
                  }
                  placeholder="https://..."
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateChildModalOpen(false);
                setChildFormData({
                  display_name: "",
                  description: "",
                  competitor_node_id: "",
                  references: [],
                });
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

      {/* Delete Child Dialog */}
      <AlertDialog
        open={isDeleteChildDialogOpen}
        onOpenChange={setIsDeleteChildDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {childLabel}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "
              {mode === "substitute-products"
                ? (selectedChild as SubstituteProduct)?.product_name
                : selectedChild?.display_name}
              "? This action cannot be undone.
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

      {/* Create Grandchild Modal (Risk or Opportunity) */}
      <Dialog
        open={isCreateGrandchildModalOpen}
        onOpenChange={setIsCreateGrandchildModalOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create {grandchildLabel}</DialogTitle>
            <DialogDescription>
              Add a {grandchildLabel.toLowerCase()} created by{" "}
              {selectedChild?.display_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="create-grandchild-name">Name *</Label>
              <Input
                id="create-grandchild-name"
                value={grandchildFormData.display_name}
                onChange={(e) =>
                  setGrandchildFormData({
                    ...grandchildFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder={
                  mode === "strengths"
                    ? "e.g., Market share erosion"
                    : "e.g., Expand into underserved segments"
                }
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="create-grandchild-description">
                Description *
              </Label>
              <Textarea
                id="create-grandchild-description"
                value={grandchildFormData.description}
                onChange={(e) =>
                  setGrandchildFormData({
                    ...grandchildFormData,
                    description: e.target.value,
                  })
                }
                placeholder={`Describe this ${grandchildLabel.toLowerCase()}...`}
                rows={4}
                maxLength={4000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateGrandchildModalOpen(false);
                setGrandchildFormData({
                  display_name: "",
                  description: "",
                  weakness_node_id: "",
                  strength_node_id: "",
                  references: [],
                } as RiskCreate | OpportunityCreate);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateGrandchild}
              disabled={
                !grandchildFormData.display_name.trim() ||
                !grandchildFormData.description.trim()
              }
            >
              Create {grandchildLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Grandchild Dialog */}
      <AlertDialog
        open={isDeleteGrandchildDialogOpen}
        onOpenChange={setIsDeleteGrandchildDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {grandchildLabel}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "
              {selectedGrandchild?.display_name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteGrandchild}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create/Edit Tactic Modal */}
      <Dialog
        open={isCreateTacticModalOpen}
        onOpenChange={(open) => {
          setIsCreateTacticModalOpen(open);
          if (!open) {
            setSelectedTactic(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedTactic ? "Edit" : "Create"} Marketing Tactic
            </DialogTitle>
            <DialogDescription>
              {selectedTactic
                ? "Update the tactic details"
                : `Add a marketing tactic used by ${selectedCompetitor?.display_name}`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="tactic-display-name">Tactic Name *</Label>
              <Input
                id="tactic-display-name"
                value={tacticFormData.display_name}
                onChange={(e) =>
                  setTacticFormData({
                    ...tacticFormData,
                    display_name: e.target.value,
                  })
                }
                placeholder="e.g., Annual Industry Conference"
                maxLength={200}
              />
            </div>
            <div>
              <Label htmlFor="tactic-description">Description *</Label>
              <Textarea
                id="tactic-description"
                value={tacticFormData.description}
                onChange={(e) =>
                  setTacticFormData({
                    ...tacticFormData,
                    description: e.target.value,
                  })
                }
                placeholder="Describe how this tactic is used to bring products to market..."
                rows={4}
                maxLength={4000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateTacticModalOpen(false);
                setSelectedTactic(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={selectedTactic ? handleUpdateTactic : handleCreateTactic}
              disabled={
                !tacticFormData.display_name.trim() ||
                !tacticFormData.description.trim()
              }
            >
              {selectedTactic ? "Save Changes" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Tactic Dialog */}
      <AlertDialog
        open={isDeleteTacticDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteTacticDialogOpen(open);
          if (!open) {
            setSelectedTactic(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Tactic</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedTactic?.display_name}"?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSelectedTactic(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteTactic}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create/Edit Value Proposition Modal (for substitute products) */}
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
                : `Add a value proposition for ${(selectedChild as SubstituteProduct)?.product_name}`}
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
                placeholder="e.g., Advanced HEPA Filtration"
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
                placeholder="Describe the value this provides to customers..."
                rows={4}
                maxLength={4000}
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
              onClick={
                selectedValueProposition
                  ? handleUpdateValueProposition
                  : handleCreateValueProposition
              }
              disabled={
                !valuePropositionFormData.display_name.trim() ||
                !valuePropositionFormData.description.trim()
              }
            >
              {selectedValueProposition ? "Save Changes" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Value Proposition Dialog */}
      <AlertDialog
        open={isDeleteVPDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteVPDialogOpen(open);
          if (!open) {
            setSelectedValueProposition(null);
          }
        }}
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
            <AlertDialogCancel
              onClick={() => setSelectedValueProposition(null)}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteValueProposition}
              className="bg-brand-red hover:bg-brand-red/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Context Menu Side Sheet */}
      <Sheet
        open={isContextMenuOpen}
        modal={false}
        onOpenChange={(open) => {
          if (
            !open &&
            (isCreateTacticModalOpen ||
              isDeleteTacticDialogOpen ||
              isCreateVPModalOpen ||
              isDeleteVPDialogOpen)
          ) {
            return;
          }

          if (!open && isEditing) {
            toast({
              title: "Unsaved Changes",
              description: "Please save or cancel your changes first",
              variant: "destructive",
            });
            return;
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
              {contextMenuType === "competitor" ? (
                <Users className="h-5 w-5" />
              ) : contextMenuType === "child" ? (
                mode === "strengths" ? (
                  <ThumbsUp className="h-5 w-5" />
                ) : mode === "weaknesses" ? (
                  <ThumbsDown className="h-5 w-5" />
                ) : (
                  <Package className="h-5 w-5" />
                )
              ) : mode === "strengths" ? (
                <ShieldAlert className="h-5 w-5" />
              ) : (
                <Star className="h-5 w-5" />
              )}
              {contextMenuType === "competitor"
                ? "Competitor"
                : contextMenuType === "child"
                  ? childLabel
                  : grandchildLabel}
            </SheetTitle>
          </SheetHeader>

          <div className="flex-1 mt-6 overflow-y-auto">
            {isEditing ? (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="context-edit-name">
                    {mode === "substitute-products" &&
                    contextMenuType === "child"
                      ? "Product Name:"
                      : "Name:"}
                  </Label>
                  <Input
                    id="context-edit-name"
                    value={
                      mode === "substitute-products" &&
                      contextMenuType === "child"
                        ? formData.product_name || ""
                        : formData.display_name
                    }
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        ...(mode === "substitute-products" &&
                        contextMenuType === "child"
                          ? { product_name: e.target.value }
                          : { display_name: e.target.value }),
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
                {mode === "substitute-products" &&
                  contextMenuType === "child" && (
                    <div>
                      <Label htmlFor="context-edit-product-page">
                        Product Detail Page (Optional):
                      </Label>
                      <Input
                        id="context-edit-product-page"
                        type="url"
                        value={formData.product_detail_page || ""}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            product_detail_page: e.target.value,
                          })
                        }
                        placeholder="https://..."
                      />
                    </div>
                  )}
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="font-semibold">
                    {mode === "substitute-products" &&
                    contextMenuType === "child"
                      ? "Product Name:"
                      : "Name:"}
                  </p>
                  <p>
                    {contextMenuType === "competitor"
                      ? selectedCompetitor?.display_name
                      : contextMenuType === "child"
                        ? mode === "substitute-products"
                          ? (selectedChild as SubstituteProduct)?.product_name
                          : selectedChild?.display_name
                        : selectedGrandchild?.display_name}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Description:</p>
                  <p className="text-sm text-dashboard-gray-600">
                    {contextMenuType === "competitor"
                      ? selectedCompetitor?.description
                      : contextMenuType === "child"
                        ? selectedChild?.description
                        : selectedGrandchild?.description}
                  </p>
                </div>
                {mode === "substitute-products" &&
                  contextMenuType === "child" &&
                  (selectedChild as SubstituteProduct)?.product_detail_page && (
                    <div>
                      <p className="font-semibold">Product Detail Page:</p>
                      <a
                        href={
                          (selectedChild as SubstituteProduct)
                            .product_detail_page
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-600 hover:text-blue-800 underline break-all"
                      >
                        {
                          (selectedChild as SubstituteProduct)
                            .product_detail_page
                        }
                      </a>
                    </div>
                  )}
              </div>
            )}

            {/* Tactics Section (for competitor context menu) */}
            {contextMenuType === "competitor" && !isEditing && (
              <div className="mt-6 pt-6 border-t">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold">Marketing Tactics</p>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-4 w-4 text-dashboard-gray-400" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm">
                          <p>
                            Specific tactics this competitor uses to bring
                            products to market, such as social media campaigns,
                            events, or advertising strategies.
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
                        setTacticFormData({
                          display_name: "",
                          description: "",
                          competitor_node_id: selectedCompetitor?.node_id || "",
                          references: [],
                        });
                        setIsCreateTacticModalOpen(true);
                      }}
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Add
                    </Button>
                  )}
                </div>

                {isLoadingTactics ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : tactics.length === 0 ? (
                  <p className="text-sm text-dashboard-gray-500 italic">
                    No tactics yet
                  </p>
                ) : (
                  <div className="space-y-2">
                    {tactics.map((tactic) => (
                      <div
                        key={tactic.node_id}
                        className="p-3 rounded-md border border-dashboard-gray-200
                                 bg-dashboard-gray-50 hover:bg-dashboard-gray-100
                                 transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="font-medium text-sm">
                              {tactic.display_name}
                            </p>
                            <p className="text-xs text-dashboard-gray-600 mt-1">
                              {tactic.description}
                            </p>
                          </div>
                          {hasEditAccess && (
                            <div className="flex gap-1 ml-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedTactic(tactic);
                                  setTacticFormData({
                                    display_name: tactic.display_name,
                                    description: tactic.description,
                                    competitor_node_id:
                                      selectedCompetitor?.node_id || "",
                                    references: tactic.references || [],
                                  });
                                  setIsCreateTacticModalOpen(true);
                                }}
                              >
                                <Pencil className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedTactic(tactic);
                                  setIsDeleteTacticDialogOpen(true);
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
            )}

            {/* Value Propositions Section (for substitute products) */}
            {mode === "substitute-products" &&
              contextMenuType === "child" &&
              !isEditing && (
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
                              Key reasons why customers might choose this
                              substitute product over your offerings.
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
                            parent_node_id: selectedChild?.node_id || "",
                            parent_node_type: "SubstituteProduct",
                            references: [],
                          });
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
                                      parent_node_id:
                                        selectedChild?.node_id || "",
                                      parent_node_type: "SubstituteProduct",
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
                                    setValuePropositionFormData({
                                      ...valuePropositionFormData,
                                      parent_node_id:
                                        selectedChild?.node_id || "",
                                    });
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
              )}
          </div>

          {/* Action Buttons */}
          {hasEditAccess && (
            <div className="flex gap-2 pt-4 border-t">
              {isEditing ? (
                <>
                  <Button
                    onClick={() => {
                      setIsEditing(false);
                      if (
                        contextMenuType === "competitor" &&
                        selectedCompetitor
                      ) {
                        setFormData({
                          display_name: selectedCompetitor.display_name,
                          description: selectedCompetitor.description,
                        });
                      } else if (contextMenuType === "child" && selectedChild) {
                        if (mode === "substitute-products") {
                          const subProduct = selectedChild as SubstituteProduct;
                          setFormData({
                            display_name: "",
                            description: subProduct.description,
                            product_name: subProduct.product_name,
                            product_detail_page:
                              subProduct.product_detail_page || "",
                          });
                        } else {
                          setFormData({
                            display_name: selectedChild.display_name,
                            description: selectedChild.description,
                          });
                        }
                      } else if (
                        contextMenuType === "grandchild" &&
                        selectedGrandchild
                      ) {
                        setFormData({
                          display_name: selectedGrandchild.display_name,
                          description: selectedGrandchild.description,
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
                      contextMenuType === "competitor"
                        ? handleUpdateCompetitor
                        : contextMenuType === "child"
                          ? handleUpdateChild
                          : handleUpdateGrandchild
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
                      setIsContextMenuOpen(false);
                      if (contextMenuType === "competitor") {
                        setIsDeleteCompetitorDialogOpen(true);
                      } else if (contextMenuType === "child") {
                        setIsDeleteChildDialogOpen(true);
                      } else {
                        setIsDeleteGrandchildDialogOpen(true);
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

import { useState } from "react";
import { Filter, Pencil, Loader2 } from "lucide-react";
import { KnowledgeGraphCard, ModeSelector } from "@/components/knowledge-graph";
import type { ModeConfig } from "@/components/knowledge-graph";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { FunnelStage } from "./FunnelStage";
import type {
  MarketingStrategy,
  StrategyType,
} from "@/services/marketingStrategyService";
import { useToast } from "@/hooks/use-toast";

interface RollupStrategiesData {
  problemAwareness: MarketingStrategy | null;
  brandAwareness: MarketingStrategy | null;
  consideration: MarketingStrategy | null;
  conversion: MarketingStrategy | null;
  loyalty: MarketingStrategy | null;
}

interface MarketingFunnelVisualizationProps {
  strategies: RollupStrategiesData | null;
  isLoading: boolean;
  selectedStrategyMode: StrategyType;
  onStrategyModeChange: (mode: StrategyType) => void;
  onSaveDescription: (
    strategyMode: StrategyType,
    description: string,
  ) => Promise<void>;
  hasEditAccess: boolean;
  isSaving: boolean;
}

const STRATEGY_MODES: readonly ModeConfig<StrategyType>[] = [
  { value: "problem-awareness", label: "Problem Awareness" },
  { value: "brand-awareness", label: "Brand Awareness" },
  { value: "consideration", label: "Consideration" },
  { value: "conversion", label: "Conversion" },
  { value: "loyalty", label: "Loyalty" },
];

const STRATEGY_MODE_TO_INDEX: Record<StrategyType, number> = {
  "problem-awareness": 0,
  "brand-awareness": 1,
  consideration: 2,
  conversion: 3,
  loyalty: 4,
};

const FUNNEL_STAGES = [
  { label: "Total Addressable Market", baseColor: "fill-dashboard-gray-300" },
  { label: "Problem Aware", baseColor: "fill-dashboard-gray-300" },
  { label: "Brand Aware", baseColor: "fill-dashboard-gray-300" },
  { label: "Considering", baseColor: "fill-dashboard-gray-300" },
  { label: "Customers", baseColor: "fill-dashboard-gray-300" },
  { label: "Advocates", baseColor: "fill-dashboard-gray-300" },
];

export const MarketingFunnelVisualization = ({
  strategies,
  isLoading,
  selectedStrategyMode,
  onStrategyModeChange,
  onSaveDescription,
  hasEditAccess,
  isSaving,
}: MarketingFunnelVisualizationProps) => {
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [editedDescription, setEditedDescription] = useState("");
  const [originalDescription, setOriginalDescription] = useState("");

  const getCurrentStrategy = (): MarketingStrategy | null => {
    if (!strategies) return null;

    const strategyMap: Record<StrategyType, MarketingStrategy | null> = {
      "problem-awareness": strategies.problemAwareness,
      "brand-awareness": strategies.brandAwareness,
      consideration: strategies.consideration,
      conversion: strategies.conversion,
      loyalty: strategies.loyalty,
    };

    return strategyMap[selectedStrategyMode];
  };

  const getStageColor = (stageIndex: number): string => {
    const strategyIndex = STRATEGY_MODE_TO_INDEX[selectedStrategyMode];
    const fromStage = strategyIndex;
    const toStage = strategyIndex + 1;

    if (stageIndex === fromStage) return "fill-brand-dark-blue";
    if (stageIndex === toStage) return "fill-brand-medium-blue";
    return "fill-dashboard-gray-300";
  };

  const handleEdit = () => {
    const currentStrategy = getCurrentStrategy();
    if (!currentStrategy) return;

    setEditedDescription(currentStrategy.description);
    setOriginalDescription(currentStrategy.description);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (editedDescription.trim() === originalDescription.trim()) {
      setIsEditing(false);
      return;
    }

    try {
      await onSaveDescription(selectedStrategyMode, editedDescription);
      setIsEditing(false);
      toast({
        title: "Success",
        description: "Strategy description updated successfully",
      });
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred";
      toast({
        title: "Error",
        description: `Failed to update strategy description: ${errorMessage}`,
        variant: "destructive",
      });
    }
  };

  const handleCancel = () => {
    setEditedDescription(originalDescription);
    setIsEditing(false);
  };

  const currentStrategy = getCurrentStrategy();

  return (
    <KnowledgeGraphCard
      title="Marketing Strategy Rollup"
      icon={Filter}
      tooltip="Select a marketing strategy to view how it moves customers through the funnel. Edit the rollup strategy description to customize your overall approach."
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Strategy Mode Selector */}
          <div className="px-6 pt-4">
            <ModeSelector
              modes={STRATEGY_MODES}
              value={selectedStrategyMode}
              onChange={onStrategyModeChange}
            />
          </div>

          {/* Funnel Visualization + Description */}
          <div className="flex gap-6 px-6 pb-6">
            {/* Left: Funnel */}
            <div className="flex-1 flex justify-center items-center">
              <svg
                width="280"
                height="360"
                viewBox="0 0 280 360"
                className="w-full max-w-xs"
              >
                {FUNNEL_STAGES.map((stage, index) => (
                  <FunnelStage
                    key={stage.label}
                    label={stage.label}
                    color={getStageColor(index)}
                    width={100 - index * 12}
                    yPosition={index * 60}
                    height={55}
                  />
                ))}
              </svg>
            </div>

            {/* Right: Description */}
            <div className="flex-1 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-base">
                  {
                    STRATEGY_MODES.find((m) => m.value === selectedStrategyMode)
                      ?.label
                  }
                </h3>
                {hasEditAccess && !isEditing && (
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

              {isEditing ? (
                <div className="space-y-3">
                  <Textarea
                    value={editedDescription}
                    onChange={(e) => setEditedDescription(e.target.value)}
                    className="min-h-[200px]"
                    placeholder="Enter strategy description..."
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={handleCancel}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="flex-1"
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          Saving...
                        </>
                      ) : (
                        "Save"
                      )}
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-dashboard-gray-600 leading-relaxed">
                  {currentStrategy?.description ||
                    "No description available for this strategy."}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </KnowledgeGraphCard>
  );
};

import { useState } from "react";
import { Filter, Pencil, Loader2, Info, Play } from "lucide-react";
import { KnowledgeGraphCard, ModeSelector } from "@/components/knowledge-graph";
import type { ModeConfig } from "@/components/knowledge-graph";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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

const STRATEGY_FULL_NAMES: Record<StrategyType, string> = {
  "problem-awareness": "Problem Awareness Strategy",
  "brand-awareness": "Brand Awareness Strategy",
  consideration: "Consideration Strategy",
  conversion: "Conversion Strategy",
  loyalty: "Loyalty Strategy",
};

const STRATEGY_DESCRIPTIONS: Record<StrategyType, string> = {
  "problem-awareness":
    "Educate prospects about problems they may not know they have. Build awareness of pain points and challenges your product solves.",
  "brand-awareness":
    "Increase visibility and recognition of your brand. Make prospects aware of your company and what you offer.",
  consideration:
    "Help prospects evaluate your solution against alternatives. Provide detailed information to aid their decision-making process.",
  conversion:
    "Persuade prospects to become paying customers. Remove friction from the purchase process and provide compelling reasons to buy.",
  loyalty:
    "Turn customers into repeat buyers and advocates. Build long-term relationships through excellent service and engagement.",
};

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
                height="390"
                viewBox="0 0 280 390"
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
                {/* Render arrow after all stages so it appears on top */}
                {(() => {
                  const strategyIndex =
                    STRATEGY_MODE_TO_INDEX[selectedStrategyMode];
                  const yPos = strategyIndex * 60;
                  const height = 55;
                  return (
                    <foreignObject
                      x={140 - 12}
                      y={yPos + height + 2}
                      width={24}
                      height={24}
                    >
                      <div className="flex items-center justify-center">
                        <Play
                          className="h-6 w-6 text-white fill-white rotate-90"
                          strokeWidth={0}
                        />
                      </div>
                    </foreignObject>
                  );
                })()}
              </svg>
            </div>

            {/* Right: Description */}
            <div className="flex-1 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-base">
                    {STRATEGY_FULL_NAMES[selectedStrategyMode]}
                  </h3>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-4 w-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p>{STRATEGY_DESCRIPTIONS[selectedStrategyMode]}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
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

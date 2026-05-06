import { ModeSelector } from "@/components/knowledge-graph";
import type { ModeConfig } from "@/components/knowledge-graph";
import { FunnelStage } from "./FunnelStage";
import type {
  StrategyType,
  MarketingStrategy,
} from "@/services/marketingStrategyService";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info, Play } from "lucide-react";

const STRATEGY_MODES: readonly ModeConfig<StrategyType>[] = [
  { value: "problem-awareness", label: "Problem" },
  { value: "brand-awareness", label: "Brand" },
  { value: "consideration", label: "Consider" },
  { value: "conversion", label: "Convert" },
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

interface MiniMarketingFunnelProps {
  strategies: MarketingStrategy[];
  selectedMode: StrategyType;
  onModeChange: (mode: StrategyType) => void;
  onDescriptionChange: (mode: StrategyType, value: string) => void;
  descriptions: Record<StrategyType, string>;
  isEditing: boolean;
}

export const MiniMarketingFunnel = ({
  strategies,
  selectedMode,
  onModeChange,
  onDescriptionChange,
  descriptions,
  isEditing,
}: MiniMarketingFunnelProps) => {
  const getStageColor = (stageIndex: number): string => {
    const strategyIndex = STRATEGY_MODE_TO_INDEX[selectedMode];
    const fromStage = strategyIndex;
    const toStage = strategyIndex + 1;

    if (stageIndex === fromStage) return "fill-brand-dark-blue";
    if (stageIndex === toStage) return "fill-brand-medium-blue";
    return "fill-dashboard-gray-300";
  };

  const getCurrentStrategy = (): MarketingStrategy | null => {
    // Map strategy type to node_id prefix
    const prefixMap: Record<StrategyType, string> = {
      "problem-awareness": "problemaware_",
      "brand-awareness": "brandaware_",
      consideration: "consideration_",
      conversion: "conversion_",
      loyalty: "loyalty_",
    };

    const prefix = prefixMap[selectedMode];
    return strategies.find((s) => s.node_id.startsWith(prefix)) || null;
  };

  const currentStrategy = getCurrentStrategy();

  return (
    <div className="space-y-4">
      {/* Mode Selector */}
      <ModeSelector
        modes={STRATEGY_MODES}
        value={selectedMode}
        onChange={onModeChange}
      />

      {/* Mini Funnel + Description */}
      <div className="flex gap-4">
        {/* Funnel (scaled down to ~43%) */}
        <svg
          width="120"
          height="180"
          viewBox="0 0 120 180"
          className="flex-shrink-0"
        >
          {[...Array(6)].map((_, index) => (
            <FunnelStage
              key={index}
              label=""
              color={getStageColor(index)}
              width={100 - index * 12}
              yPosition={index * 25.8}
              height={23.7}
              baseWidth={120}
            />
          ))}
          {/* Render arrow after all stages so it appears on top */}
          {(() => {
            const strategyIndex = STRATEGY_MODE_TO_INDEX[selectedMode];
            const yPos = strategyIndex * 25.8;
            const height = 23.7;
            return (
              <foreignObject
                x={60 - 8}
                y={yPos + height + 1}
                width={16}
                height={16}
              >
                <div className="flex items-center justify-center">
                  <Play
                    className="h-4 w-4 text-white fill-white rotate-90"
                    strokeWidth={0}
                  />
                </div>
              </foreignObject>
            );
          })()}
        </svg>

        {/* Description */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label>{STRATEGY_FULL_NAMES[selectedMode]}</Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>{STRATEGY_DESCRIPTIONS[selectedMode]}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <Textarea
                value={descriptions[selectedMode]}
                onChange={(e) =>
                  onDescriptionChange(selectedMode, e.target.value)
                }
                rows={5}
                placeholder="Enter strategy description..."
                className="text-sm"
              />
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <p className="font-semibold text-sm">
                  {STRATEGY_FULL_NAMES[selectedMode]}
                </p>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>{STRATEGY_DESCRIPTIONS[selectedMode]}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p className="text-sm text-[var(--color-text-tertiary)] leading-relaxed">
                {currentStrategy?.description || "No description provided yet."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

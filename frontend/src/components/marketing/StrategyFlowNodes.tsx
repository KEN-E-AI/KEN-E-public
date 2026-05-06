import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import {
  AlertCircle,
  Eye,
  ThumbsUp,
  ShoppingCart,
  Heart,
  Users,
  Filter,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface CustomerProfileNodeProps {
  data: {
    label: string;
    isSelected: boolean;
    hasStrategies?: boolean;
  };
}

export const CustomerProfileNode = ({ data }: CustomerProfileNodeProps) => {
  return (
    <div className="relative">
      {/* Badge matching horizontal scroll design */}
      <div className="flex items-center">
        {/* Text Box - Left */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className="bg-brand-medium-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
                style={{ width: "200px" }}
              >
                <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
                  Customer Profile
                </p>
                <p className="font-semibold text-[var(--color-text-primary)] leading-tight truncate">
                  {data.label}
                </p>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>{data.label}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {/* Circle with Icon - Right */}
        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-medium-blue flex items-center justify-center"
            style={{
              width: "72px",
              height: "72px",
              boxShadow: data.isSelected
                ? "0 0 0 3px rgba(70, 143, 208, 0.4)"
                : "none",
            }}
          >
            <Users
              className="text-white"
              style={{ width: "48px", height: "48px" }}
            />
          </div>
        </div>
      </div>

      {/* Top Handle for incoming connections - positioned at circle top center */}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="opacity-0"
        style={{ right: "30px", left: "auto" }}
      />

      {/* Bottom Handle for outgoing connections (show if has strategies) */}
      {data.hasStrategies && (
        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="opacity-0"
          style={{ right: "30px", left: "auto" }}
        />
      )}
    </div>
  );
};

interface StrategyBundleNodeData {
  label: string;
  isSelected: boolean;
}

export const StrategyBundleNode = ({
  data,
}: NodeProps<StrategyBundleNodeData>) => {
  return (
    <div className="relative">
      <div className="flex items-center">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className="bg-brand-dark-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
                style={{ width: "200px" }}
              >
                <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
                  Marketing Strategies
                </p>
                <p className="font-semibold text-[var(--color-text-primary)] leading-tight truncate">
                  {data.label}
                </p>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>{data.label}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-dark-blue flex items-center justify-center"
            style={{
              width: "72px",
              height: "72px",
              boxShadow: data.isSelected
                ? "0 0 0 3px rgba(27, 66, 111, 0.4)"
                : "none",
            }}
          >
            <Filter
              className="text-white"
              style={{ width: "48px", height: "48px" }}
            />
          </div>
        </div>
      </div>

      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="opacity-0"
        style={{ right: "30px", left: "auto" }}
      />
    </div>
  );
};

interface IndividualStrategyNodeProps {
  data: {
    strategyType:
      | "ProblemAwarenessStrategy"
      | "BrandAwarenessStrategy"
      | "ConsiderationStrategy"
      | "ConversionStrategy"
      | "LoyaltyStrategy";
    isSelected: boolean;
  };
}

const STRATEGY_CONFIG = {
  ProblemAwarenessStrategy: {
    label: "Problem Awareness",
    icon: AlertCircle,
    bgColor: "bg-red-50",
    iconColor: "text-red-600",
    borderColor: "border-red-300",
    selectedBorder: "border-red-600",
    selectedRing: "ring-red-600",
  },
  BrandAwarenessStrategy: {
    label: "Brand Awareness",
    icon: Eye,
    bgColor: "bg-blue-50",
    iconColor: "text-blue-600",
    borderColor: "border-blue-300",
    selectedBorder: "border-blue-600",
    selectedRing: "ring-blue-600",
  },
  ConsiderationStrategy: {
    label: "Consideration",
    icon: ThumbsUp,
    bgColor: "bg-yellow-50",
    iconColor: "text-yellow-600",
    borderColor: "border-yellow-300",
    selectedBorder: "border-yellow-600",
    selectedRing: "ring-yellow-600",
  },
  ConversionStrategy: {
    label: "Conversion",
    icon: ShoppingCart,
    bgColor: "bg-green-50",
    iconColor: "text-green-600",
    borderColor: "border-green-300",
    selectedBorder: "border-green-600",
    selectedRing: "ring-green-600",
  },
  LoyaltyStrategy: {
    label: "Loyalty",
    icon: Heart,
    bgColor: "bg-purple-50",
    iconColor: "text-purple-600",
    borderColor: "border-purple-300",
    selectedBorder: "border-purple-600",
    selectedRing: "ring-purple-600",
  },
};

export const IndividualStrategyNode = ({
  data,
}: IndividualStrategyNodeProps) => {
  const config = STRATEGY_CONFIG[data.strategyType];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "px-3 py-2 rounded-lg border-2 shadow-sm transition-all",
        "min-w-[140px] max-w-[180px]",
        config.bgColor,
        data.isSelected
          ? cn(
              config.selectedBorder,
              "ring-2",
              config.selectedRing,
              "ring-offset-2",
            )
          : cn(config.borderColor, "hover:opacity-80"),
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="!bg-brand-medium-blue"
      />

      <div className="flex items-center gap-2">
        <div className="flex-shrink-0">
          <Icon className={cn("h-4 w-4", config.iconColor)} />
        </div>
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              "text-xs font-medium truncate",
              data.isSelected
                ? "text-[var(--color-text-primary)]"
                : "text-[var(--color-text-secondary)]",
            )}
          >
            {config.label}
          </p>
        </div>
      </div>
    </div>
  );
};

import { Handle, Position } from "reactflow";
import {
  AlertCircle,
  Eye,
  ThumbsUp,
  ShoppingCart,
  Heart,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CustomerProfileNodeProps {
  data: {
    label: string;
    isSelected: boolean;
  };
}

export const CustomerProfileNode = ({ data }: CustomerProfileNodeProps) => {
  return (
    <div
      className={cn(
        "px-4 py-3 rounded-lg border-2 bg-white shadow-sm transition-all",
        "min-w-[160px] max-w-[200px]",
        data.isSelected
          ? "border-brand-dark-blue ring-2 ring-brand-dark-blue ring-offset-2"
          : "border-dashboard-gray-300 hover:border-brand-medium-blue",
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="!bg-brand-medium-blue"
      />

      <div className="flex items-center gap-2">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-light-blue flex items-center justify-center">
          <Users className="h-4 w-4 text-brand-dark-blue" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-dashboard-gray-900 truncate">
            {data.label}
          </p>
          <p className="text-xs text-dashboard-gray-500">Customer Profile</p>
        </div>
      </div>

      {data.isSelected && (
        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="!bg-brand-medium-blue"
        />
      )}
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
                ? "text-dashboard-gray-900"
                : "text-dashboard-gray-700",
            )}
          >
            {config.label}
          </p>
        </div>
      </div>
    </div>
  );
};

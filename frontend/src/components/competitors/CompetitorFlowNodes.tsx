import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import {
  Plus,
  Users,
  Dumbbell,
  Unlink,
  Package,
  Box,
  ShieldAlert,
  Star,
} from "lucide-react";

// ==================== COMPETITOR NODE ====================

interface CompetitorNodeData {
  label: string;
  isSelected: boolean;
  onAddChild: () => void;
}

export const CompetitorNode = memo(
  ({ data }: NodeProps<CompetitorNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Competitor
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-light-blue flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(159, 206, 237, 0.4)"
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

        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="opacity-0"
          style={{ right: "30px", left: "auto" }}
        />

        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onAddChild();
          }}
          className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-light-blue flex items-center justify-center z-20"
        >
          <Plus className="h-4 w-4 text-white" />
        </button>
      </div>
    );
  },
);

CompetitorNode.displayName = "CompetitorNode";

// ==================== COMPETITOR STRENGTH NODE ====================

interface CompetitorStrengthNodeData {
  label: string;
  isSelected: boolean;
  onAddRisk: () => void;
}

export const CompetitorStrengthNode = memo(
  ({ data }: NodeProps<CompetitorStrengthNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div className="bg-brand-light-red bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Strength
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-light-red flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(255, 153, 153, 0.4)"
                  : "none",
              }}
            >
              <Dumbbell
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

        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="opacity-0"
          style={{ right: "30px", left: "auto" }}
        />

        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onAddRisk();
          }}
          className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-light-red flex items-center justify-center z-20"
        >
          <Plus className="h-4 w-4 text-white" />
        </button>
      </div>
    );
  },
);

CompetitorStrengthNode.displayName = "CompetitorStrengthNode";

// ==================== COMPETITOR WEAKNESS NODE ====================

interface CompetitorWeaknessNodeData {
  label: string;
  isSelected: boolean;
  onAddOpportunity: () => void;
}

export const CompetitorWeaknessNode = memo(
  ({ data }: NodeProps<CompetitorWeaknessNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div className="bg-brand-light-green bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Weakness
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-light-green flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(184, 226, 175, 0.4)"
                  : "none",
              }}
            >
              <Unlink
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

        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="opacity-0"
          style={{ right: "30px", left: "auto" }}
        />

        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onAddOpportunity();
          }}
          className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-light-green flex items-center justify-center z-20"
        >
          <Plus className="h-4 w-4 text-white" />
        </button>
      </div>
    );
  },
);

CompetitorWeaknessNode.displayName = "CompetitorWeaknessNode";

// ==================== SUBSTITUTE PRODUCT NODE ====================

interface SubstituteProductNodeData {
  label: string;
  isSelected: boolean;
  showHandle: boolean;
  onAddProduct: () => void;
}

export const SubstituteProductNode = memo(
  ({ data }: NodeProps<SubstituteProductNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div
            className="bg-brand-yellow bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
            style={{ width: "200px" }}
          >
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Substitute Product
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight truncate">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-yellow flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(234, 185, 70, 0.4)"
                  : "none",
              }}
            >
              <Package
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

        {data.showHandle && (
          <>
            <Handle
              type="source"
              position={Position.Bottom}
              id="bottom"
              className="opacity-0"
              style={{ right: "30px", left: "auto" }}
            />

            <button
              onClick={(e) => {
                e.stopPropagation();
                data.onAddProduct();
              }}
              className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-yellow flex items-center justify-center z-20"
            >
              <Plus className="h-4 w-4 text-white" />
            </button>
          </>
        )}
      </div>
    );
  },
);

SubstituteProductNode.displayName = "SubstituteProductNode";

// ==================== OUR PRODUCT NODE (for substitute product relationships) ====================

interface OurProductNodeData {
  label: string;
  isSelected: boolean;
}

export const OurProductNode = memo(
  ({ data }: NodeProps<OurProductNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div
            className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
            style={{ width: "200px" }}
          >
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Our Product
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight truncate">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-medium-blue flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(99, 179, 237, 0.4)"
                  : "none",
              }}
            >
              <Box
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
  },
);

OurProductNode.displayName = "OurProductNode";

// ==================== RISK NODE (Reused from SWOT) ====================

interface RiskNodeData {
  label: string;
  showHandle: boolean;
  isSelected: boolean;
  onAddSubstitute: () => void;
}

export const RiskNode = memo(({ data }: NodeProps<RiskNodeData>) => {
  return (
    <div className="relative">
      <div className="flex items-center">
        <div
          className="bg-brand-red bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
          style={{ width: "200px" }}
        >
          <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
            Risk
          </p>
          <p className="font-semibold text-dashboard-gray-900 leading-tight truncate">
            {data.label}
          </p>
        </div>

        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-red flex items-center justify-center"
            style={{
              width: "72px",
              height: "72px",
              boxShadow: data.isSelected
                ? "0 0 0 3px rgba(255, 107, 107, 0.4)"
                : "none",
            }}
          >
            <ShieldAlert
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
});

RiskNode.displayName = "RiskNode";

// ==================== OPPORTUNITY NODE (Reused from SWOT) ====================

interface OpportunityNodeData {
  label: string;
  showHandle: boolean;
  isSelected: boolean;
  onAddSubstitute: () => void;
}

export const OpportunityNode = memo(
  ({ data }: NodeProps<OpportunityNodeData>) => {
    return (
      <div className="relative">
        <div className="flex items-center">
          <div
            className="bg-brand-dark-green bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
            style={{ width: "200px" }}
          >
            <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
              Opportunity
            </p>
            <p className="font-semibold text-dashboard-gray-900 leading-tight truncate">
              {data.label}
            </p>
          </div>

          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-dark-green flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(58, 116, 57, 0.4)"
                  : "none",
              }}
            >
              <Star
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
  },
);

OpportunityNode.displayName = "OpportunityNode";

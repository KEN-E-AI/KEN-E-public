import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { Plus, Star, Dumbbell, Unlink, ShieldAlert } from "lucide-react";

// ==================== STRENGTHS ====================

interface StrengthNodeData {
  label: string;
  isSelected: boolean;
  onAddOpportunity: () => void;
}

export const StrengthNode = memo(({ data }: NodeProps<StrengthNodeData>) => {
  return (
    <div className="relative">
      <div className="flex items-center">
        <div className="bg-brand-light-green bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
          <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
            Strength
          </p>
          <p className="font-semibold text-[var(--color-text-primary)] leading-tight">
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
            <Dumbbell
              className="text-white"
              style={{ width: "3rem", height: "3rem" }}
            />
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        className="opacity-0"
        style={{ right: "1.875rem", left: "auto" }}
      />

      <button
        onClick={(e) => {
          e.stopPropagation();
          data.onAddOpportunity();
        }}
        className="absolute -bottom-[0.75rem] right-[1.5625rem] w-6 h-6 rounded-full bg-brand-light-green flex items-center justify-center z-20"
      >
        <Plus className="h-4 w-4 text-white" />
      </button>
    </div>
  );
});

StrengthNode.displayName = "StrengthNode";

// ==================== OPPORTUNITIES ====================

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
            style={{ width: "12.5rem" }}
          >
            <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
              Opportunity
            </p>
            <p className="font-semibold text-[var(--color-text-primary)] leading-tight truncate">
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
                style={{ width: "3rem", height: "3rem" }}
              />
            </div>
          </div>
        </div>

        <Handle
          type="target"
          position={Position.Top}
          id="top"
          className="opacity-0"
          style={{ right: "1.875rem", left: "auto" }}
        />

        {data.showHandle && (
          <>
            <Handle
              type="source"
              position={Position.Bottom}
              id="bottom"
              className="opacity-0"
              style={{ right: "1.875rem", left: "auto" }}
            />

            <button
              onClick={(e) => {
                e.stopPropagation();
                data.onAddSubstitute();
              }}
              className="absolute -bottom-[0.75rem] right-[1.5625rem] w-6 h-6 rounded-full bg-brand-dark-green flex items-center justify-center z-20"
            >
              <Plus className="h-4 w-4 text-white" />
            </button>
          </>
        )}
      </div>
    );
  },
);

OpportunityNode.displayName = "OpportunityNode";

// ==================== WEAKNESSES ====================

interface WeaknessNodeData {
  label: string;
  isSelected: boolean;
  onAddRisk: () => void;
}

export const WeaknessNode = memo(({ data }: NodeProps<WeaknessNodeData>) => {
  return (
    <div className="relative">
      <div className="flex items-center">
        <div className="bg-brand-light-red bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
          <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
            Weakness
          </p>
          <p className="font-semibold text-[var(--color-text-primary)] leading-tight">
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
            <Unlink
              className="text-white"
              style={{ width: "3rem", height: "3rem" }}
            />
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        className="opacity-0"
        style={{ right: "1.875rem", left: "auto" }}
      />

      <button
        onClick={(e) => {
          e.stopPropagation();
          data.onAddRisk();
        }}
        className="absolute -bottom-[0.75rem] right-[1.5625rem] w-6 h-6 rounded-full bg-brand-light-red flex items-center justify-center z-20"
      >
        <Plus className="h-4 w-4 text-white" />
      </button>
    </div>
  );
});

WeaknessNode.displayName = "WeaknessNode";

// ==================== RISKS ====================

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
          style={{ width: "12.5rem" }}
        >
          <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
            Risk
          </p>
          <p className="font-semibold text-[var(--color-text-primary)] leading-tight truncate">
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
              style={{ width: "3rem", height: "3rem" }}
            />
          </div>
        </div>
      </div>

      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="opacity-0"
        style={{ right: "1.875rem", left: "auto" }}
      />

      {data.showHandle && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="bottom"
            className="opacity-0"
            style={{ right: "1.875rem", left: "auto" }}
          />

          <button
            onClick={(e) => {
              e.stopPropagation();
              data.onAddSubstitute();
            }}
            className="absolute -bottom-[0.75rem] right-[1.5625rem] w-6 h-6 rounded-full bg-brand-red flex items-center justify-center z-20"
          >
            <Plus className="h-4 w-4 text-white" />
          </button>
        </>
      )}
    </div>
  );
});

RiskNode.displayName = "RiskNode";

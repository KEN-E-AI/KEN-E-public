import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { Users, Blocks, Plus } from "lucide-react";

interface CustomerProfileNodeData {
  label: string;
  isSelected: boolean;
  onAddCategory: () => void;
}

export const CustomerProfileNode = memo(
  ({ data }: NodeProps<CustomerProfileNodeData>) => {
    return (
      <div className="relative">
        {/* Badge matching horizontal scroll design */}
        <div className="flex items-center">
          {/* Text Box - Left */}
          <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
            <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
              Ideal Customer Profile
            </p>
            <p className="font-semibold text-[var(--color-text-primary)] leading-tight">
              {data.label}
            </p>
          </div>

          {/* Circle with Icon - Right */}
          <div className="flex-shrink-0 -ml-12 relative z-10">
            <div
              className="rounded-full bg-brand-light-blue flex items-center justify-center"
              style={{
                width: "72px",
                height: "72px",
                boxShadow: data.isSelected
                  ? "0 0 0 3px rgba(108, 198, 242, 0.4)"
                  : "none",
              }}
            >
              <Users
                className="text-white"
                style={{ width: "3rem", height: "3rem" }}
              />
            </div>
          </div>
        </div>

        {/* React Flow Handle (invisible) - positioned at circle bottom center */}
        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          className="opacity-0"
          style={{ right: "1.875rem", left: "auto" }}
        />

        {/* Custom "+" Button - centered under circle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onAddCategory();
          }}
          className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-light-blue flex items-center justify-center z-20"
        >
          <Plus className="h-4 w-4 text-white" />
        </button>
      </div>
    );
  },
);

CustomerProfileNode.displayName = "CustomerProfileNode";

interface ProductCategoryNodeData {
  label: string;
  isSelected: boolean;
  strategyCount?: number;
}

export const ProductCategoryNode = memo(
  ({ data }: NodeProps<ProductCategoryNodeData>) => {
    return (
      <div className="relative">
        {/* Badge matching horizontal scroll design */}
        <div className="flex items-center">
          {/* Text Box - Left - Fixed width for consistent spacing */}
          <div
            className="bg-brand-medium-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
            style={{ width: "12.5rem" }}
          >
            <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
              Product Category
            </p>
            <p className="font-semibold text-[var(--color-text-primary)] leading-tight truncate">
              {data.label}
            </p>
          </div>

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
              <Blocks
                className="text-white"
                style={{ width: "3rem", height: "3rem" }}
              />
            </div>

            {/* Strategy Count Badge */}
            {data.strategyCount !== undefined && data.strategyCount > 0 && (
              <div
                className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-brand-green flex items-center justify-center"
                style={{ fontSize: "0.6875rem", fontWeight: "600" }}
              >
                <span className="text-white">{data.strategyCount}</span>
              </div>
            )}
          </div>
        </div>

        {/* Top Handle for incoming connections - positioned at circle top center */}
        <Handle
          type="target"
          position={Position.Top}
          id="top"
          className="opacity-0"
          style={{ right: "1.875rem", left: "auto" }}
        />
      </div>
    );
  },
);

ProductCategoryNode.displayName = "ProductCategoryNode";

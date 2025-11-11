import { memo } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { Plus, Blocks, Package } from "lucide-react";

interface CategoryNodeData {
  label: string;
  onAddProduct: () => void;
}

export const CategoryNode = memo(({ data }: NodeProps<CategoryNodeData>) => {
  return (
    <div className="relative">
      {/* Badge matching horizontal scroll design */}
      <div className="flex items-center">
        {/* Text Box - Left */}
        <div className="bg-brand-light-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2">
          <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
            Product Category
          </p>
          <p className="font-semibold text-dashboard-gray-900 leading-tight">
            {data.label}
          </p>
        </div>

        {/* Circle with Icon - Right */}
        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className="rounded-full bg-brand-light-blue flex items-center justify-center"
            style={{ width: "72px", height: "72px" }}
          >
            <Blocks
              className="text-white"
              style={{ width: "48px", height: "48px" }}
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
        style={{ right: "30px", left: "auto" }}
      />

      {/* Custom "+" Button - centered under circle */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          data.onAddProduct();
        }}
        className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-light-blue flex items-center justify-center z-20"
      >
        <Plus className="h-4 w-4 text-white" />
      </button>
    </div>
  );
});

CategoryNode.displayName = "CategoryNode";

interface ProductNodeData {
  label: string;
  showHandle: boolean;
  isSelected: boolean;
  onAddSubstitute: () => void;
}

export const ProductNode = memo(({ data }: NodeProps<ProductNodeData>) => {
  return (
    <div className="relative">
      {/* Badge matching horizontal scroll design */}
      <div className="flex items-center">
        {/* Text Box - Left - Fixed width for consistent spacing */}
        <div
          className="bg-brand-medium-blue bg-opacity-30 rounded-lg pl-4 pr-16 py-2"
          style={{ width: "200px" }}
        >
          <p className="text-sm text-dashboard-gray-600 leading-tight mb-0">
            Product
          </p>
          <p className="font-semibold text-dashboard-gray-900 leading-tight truncate">
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
            <Package
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

      {/* Bottom Handle for outgoing connections (when selected) */}
      {data.showHandle && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="bottom"
            className="opacity-0"
            style={{ right: "30px", left: "auto" }}
          />

          {/* Custom "+" Button - centered under circle (only when showHandle is true) */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              data.onAddSubstitute();
            }}
            className="absolute -bottom-[12px] right-[25px] w-6 h-6 rounded-full bg-brand-medium-blue flex items-center justify-center z-20"
          >
            <Plus className="h-4 w-4 text-white" />
          </button>
        </>
      )}
    </div>
  );
});

ProductNode.displayName = "ProductNode";

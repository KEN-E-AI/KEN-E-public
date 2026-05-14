import type { HorizontalScrollItemVisualProps } from "../types";

/**
 * Visual representation of a single item in horizontal scroll list
 * Consistent badge + icon layout used across all knowledge graph pages
 */
export function HorizontalScrollItem({
  label,
  sublabel,
  icon: Icon,
  bgColor,
  iconBgColor,
  isSelected,
  onClick,
}: HorizontalScrollItemVisualProps) {
  return (
    <div
      className={`flex-shrink-0 p-4 rounded-lg transition-colors cursor-pointer ${
        isSelected
          ? "ring-2 ring-brand-medium-blue"
          : "hover:ring-2 hover:ring-gray-300"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center">
        {/* Text Box - Left */}
        <div className={`${bgColor} rounded-lg pl-4 pr-16 py-2`}>
          {sublabel && (
            <p className="text-sm text-[var(--color-text-tertiary)] leading-tight mb-0">
              {sublabel}
            </p>
          )}
          <p className="font-semibold text-[var(--color-text-primary)] leading-tight">
            {label}
          </p>
        </div>

        {/* Circle with Icon - Right */}
        <div className="flex-shrink-0 -ml-12 relative z-10">
          <div
            className={`rounded-full ${iconBgColor} flex items-center justify-center`}
            style={{ width: "4.5rem", height: "4.5rem" }}
          >
            <Icon
              className="text-white"
              style={{ width: "3rem", height: "3rem" }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

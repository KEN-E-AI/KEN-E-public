import { cn } from "@/lib/utils";

interface FunnelStageProps {
  label: string;
  color: string;
  width: number;
  yPosition: number;
  height: number;
  baseWidth?: number;
}

export const FunnelStage = ({
  label,
  color,
  width,
  yPosition,
  height,
  baseWidth = 280,
}: FunnelStageProps) => {
  const stageWidth = baseWidth * (width / 100);
  const nextWidth = stageWidth - 40;
  const xOffset = (baseWidth - stageWidth) / 2;

  const isHighlighted =
    color === "fill-brand-dark-blue" || color === "fill-brand-medium-blue";
  const textColorClass = isHighlighted
    ? "fill-white font-semibold"
    : "fill-dashboard-gray-800 font-medium";

  return (
    <g>
      <path
        d={`
          M ${xOffset} ${yPosition}
          L ${xOffset + stageWidth} ${yPosition}
          L ${xOffset + stageWidth - 20} ${yPosition + height}
          L ${xOffset + 20} ${yPosition + height}
          Z
        `}
        className={cn("transition-colors duration-300", color)}
      />
      <text
        x={baseWidth / 2}
        y={yPosition + height / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        className={cn("text-xs transition-colors duration-300", textColorClass)}
      >
        {label}
      </text>
    </g>
  );
};

import { cn } from "@/lib/utils";

interface FunnelStageProps {
  label: string;
  color: string;
  width: number;
  yPosition: number;
  height: number;
}

export const FunnelStage = ({
  label,
  color,
  width,
  yPosition,
  height,
}: FunnelStageProps) => {
  const baseWidth = 280;
  const stageWidth = baseWidth * (width / 100);
  const nextWidth = stageWidth - 40;
  const xOffset = (baseWidth - stageWidth) / 2;

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
        stroke="#64748b"
        strokeWidth="1"
      />
      <text
        x={baseWidth / 2}
        y={yPosition + height / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        className="text-xs font-medium fill-dashboard-gray-800"
      >
        {label}
      </text>
    </g>
  );
};

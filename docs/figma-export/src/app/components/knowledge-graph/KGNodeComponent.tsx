import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  Building2, Megaphone, Swords, Package, Users, Radio,
  FileText, Gauge, Lightbulb, Palette, Target, CircleUser,
} from 'lucide-react';

const iconMap: Record<string, React.FC<{ className?: string }>> = {
  Building2, Megaphone, Swords, Package, Users, Radio,
  FileText, Gauge, Lightbulb, Palette, Target, CircleUser,
};

export interface KGNodeData {
  label: string;
  nodeType: string;
  color: string;
  bgColor: string;
  icon: string;
  dimmed: boolean;
  highlighted: boolean;
}

function KGNodeComponentInner({ data, selected }: NodeProps & { data: KGNodeData }) {
  const Icon = iconMap[data.icon] || Building2;
  const isDimmed = data.dimmed;
  const isHighlighted = data.highlighted;

  return (
    <div
      className="flex flex-col items-center gap-1.5 transition-opacity"
      style={{
        opacity: isDimmed ? 0.2 : 1,
        transitionDuration: 'var(--duration-default)',
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-0 !h-0" />
      <div
        className="size-11 rounded-full flex items-center justify-center transition-all cursor-pointer"
        style={{
          backgroundColor: data.color,
          boxShadow: selected || isHighlighted
            ? `0 0 0 3px ${data.bgColor}, 0 4px 16px ${data.color}40`
            : `0 2px 8px ${data.color}25`,
          transform: selected ? 'scale(1.15)' : isHighlighted ? 'scale(1.08)' : 'scale(1)',
          transitionTimingFunction: 'var(--ease-bounce)',
          transitionDuration: 'var(--duration-fast)',
        }}
      >
        <Icon className="size-5 text-white" />
      </div>
      <span
        className="text-[11px] text-center max-w-[100px] truncate px-1.5 py-0.5 rounded-[var(--radius-sm)]"
        style={{
          fontWeight: selected ? 600 : 500,
          backgroundColor: selected || isHighlighted ? data.bgColor : 'transparent',
          color: selected || isHighlighted ? data.color : 'var(--color-text-secondary)',
        }}
      >
        {data.label}
      </span>
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-0 !h-0" />
    </div>
  );
}

export const KGNodeComponent = memo(KGNodeComponentInner);
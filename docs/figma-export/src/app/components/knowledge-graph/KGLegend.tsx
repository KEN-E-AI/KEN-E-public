import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { KGNodeType, KGRelationshipType } from '../../data/knowledgeGraphData';

interface KGLegendProps {
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
}

export function KGLegend({ nodeTypes, relationshipTypes }: KGLegendProps) {
  const [collapsed, setCollapsed] = useState(true);

  return (
    <div
      className="absolute top-4 left-4 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-md z-10 select-none"
      style={{ maxWidth: 260 }}
    >
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
        style={{ fontWeight: 600 }}
      >
        Legend
        {collapsed ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
      </button>

      {!collapsed && (
        <div className="px-3 pb-3">
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            {nodeTypes.map(nt => (
              <div key={nt.id} className="flex items-center gap-1.5">
                <div className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: nt.color }} />
                <span className="text-[10px] truncate">{nt.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
import { memo } from 'react';
import {
  BaseEdge,
  getBezierPath,
  EdgeLabelRenderer,
  type EdgeProps,
} from '@xyflow/react';

export interface KGEdgeData {
  relType: string;
  relLabel: string;
  color: string;
  dimmed: boolean;
  highlighted: boolean;
}

function KGEdgeComponentInner({
  id,
  sourceX, sourceY,
  targetX, targetY,
  sourcePosition, targetPosition,
  selected,
  data,
  markerEnd,
}: EdgeProps & { data: KGEdgeData }) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY,
    targetX, targetY,
    sourcePosition, targetPosition,
  });

  const isDimmed = data?.dimmed ?? false;
  const isHighlighted = data?.highlighted ?? false;
  const color = data?.color ?? '#94A3B8';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: selected || isHighlighted ? color : '#CBD5E1',
          strokeWidth: selected ? 2.5 : isHighlighted ? 2 : 1.5,
          opacity: isDimmed ? 0.1 : 1,
          transition: 'all var(--duration-default) var(--ease-default)',
        }}
      />
      {(selected || isHighlighted) && !isDimmed && (
        <EdgeLabelRenderer>
          <div
            className="absolute pointer-events-auto px-2 py-0.5 rounded-[var(--radius-pill)] text-[0.5625rem] border nodrag nopan"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              backgroundColor: 'var(--color-bg-elevated)',
              borderColor: color,
              color: color,
              fontWeight: 600,
              boxShadow: `0 2px 8px ${color}20`,
            }}
          >
            {data?.relLabel ?? data?.relType}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const KGEdgeComponent = memo(KGEdgeComponentInner);

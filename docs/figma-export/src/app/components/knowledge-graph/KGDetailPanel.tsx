import { X, ExternalLink, ArrowRight, Building2, Megaphone, Swords, Package, Users, Radio, FileText, Gauge, Lightbulb, Palette, Target, CircleUser } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Separator } from '../ui/separator';
import type { KGNode, KGRelationship, KGNodeType, KGRelationshipType } from '../../data/knowledgeGraphData';

const iconMap: Record<string, React.FC<{ className?: string }>> = {
  Building2, Megaphone, Swords, Package, Users, Radio,
  FileText, Gauge, Lightbulb, Palette, Target, CircleUser,
};

interface KGDetailPanelProps {
  selectedNode: KGNode | null;
  selectedRelationship: KGRelationship | null;
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
  allNodes: KGNode[];
  allRelationships: KGRelationship[];
  onClose: () => void;
  onNavigateToNode: (nodeId: string) => void;
}

export function KGDetailPanel({
  selectedNode,
  selectedRelationship,
  nodeTypes,
  relationshipTypes,
  allNodes,
  allRelationships,
  onClose,
  onNavigateToNode,
}: KGDetailPanelProps) {
  const isOpen = !!selectedNode || !!selectedRelationship;

  if (!isOpen) return null;

  return (
    <div
      className="absolute top-0 right-0 h-full w-[23.75rem] bg-[var(--color-bg-elevated)] border-l border-[var(--color-border-default)] shadow-lg z-20 flex flex-col animate-in slide-in-from-right duration-300"
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-1 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] text-muted-foreground hover:text-foreground transition-colors z-10"
      >
        <X className="size-4" />
      </button>

      {selectedNode && (
        <NodeDetail
          node={selectedNode}
          nodeTypes={nodeTypes}
          relationshipTypes={relationshipTypes}
          allNodes={allNodes}
          allRelationships={allRelationships}
          onNavigateToNode={onNavigateToNode}
        />
      )}

      {!selectedNode && selectedRelationship && (
        <RelationshipDetail
          relationship={selectedRelationship}
          nodeTypes={nodeTypes}
          relationshipTypes={relationshipTypes}
          allNodes={allNodes}
          onNavigateToNode={onNavigateToNode}
        />
      )}
    </div>
  );
}

// ─── Node Detail ───

function NodeDetail({
  node,
  nodeTypes,
  relationshipTypes,
  allNodes,
  allRelationships,
  onNavigateToNode,
}: {
  node: KGNode;
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
  allNodes: KGNode[];
  allRelationships: KGRelationship[];
  onNavigateToNode: (id: string) => void;
}) {
  const nt = nodeTypes.find(t => t.id === node.type);
  const Icon = iconMap[nt?.icon ?? 'Building2'] || Building2;

  // Find connected relationships
  const connectedRels = allRelationships.filter(
    r => r.sourceId === node.id || r.targetId === node.id
  );

  // Group by relationship type
  const grouped = new Map<string, { rel: KGRelationship; connectedNode: KGNode; direction: 'out' | 'in' }[]>();
  for (const rel of connectedRels) {
    const otherId = rel.sourceId === node.id ? rel.targetId : rel.sourceId;
    const other = allNodes.find(n => n.id === otherId);
    if (!other) continue;
    const dir = rel.sourceId === node.id ? 'out' : 'in';
    if (!grouped.has(rel.type)) grouped.set(rel.type, []);
    grouped.get(rel.type)!.push({ rel, connectedNode: other, direction: dir });
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-5 pr-12">
        <div className="flex items-center gap-3 mb-2">
          <div
            className="size-10 rounded-full flex items-center justify-center shrink-0"
            style={{
              backgroundColor: nt?.color,
              boxShadow: `0 4px 16px ${nt?.color}30`,
            }}
          >
            <Icon className="size-5 text-white" />
          </div>
          <div className="min-w-0">
            <h3 className="truncate">{node.label}</h3>
            <Badge
              variant="secondary"
              className="text-[0.625rem] px-1.5 py-0 mt-0.5"
              style={{ backgroundColor: nt?.bgColor, color: nt?.color }}
            >
              {nt?.label ?? node.type}
            </Badge>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Node ID: {node.id}
        </p>
      </div>

      <Separator />

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Properties */}
        <div>
          <h4 className="text-xs text-muted-foreground mb-2" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Properties
          </h4>
          <div className="space-y-2">
            {Object.entries(node.properties).map(([key, value]) => (
              <PropertyRow key={key} propKey={key} value={value} />
            ))}
          </div>
        </div>

        {/* Connected Relationships */}
        {connectedRels.length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="text-xs text-muted-foreground mb-3" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Relationships ({connectedRels.length})
              </h4>
              <div className="space-y-3">
                {Array.from(grouped.entries()).map(([relType, items]) => {
                  const rt = relationshipTypes.find(t => t.id === relType);
                  return (
                    <div key={relType}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <div className="size-2 rounded-full" style={{ backgroundColor: rt?.color ?? '#94A3B8' }} />
                        <span className="text-[0.6875rem] text-muted-foreground" style={{ fontWeight: 600 }}>
                          {rt?.label ?? relType}
                        </span>
                        <Badge variant="secondary" className="text-[0.5625rem] px-1 py-0 ml-auto">
                          {items.length}
                        </Badge>
                      </div>
                      <div className="space-y-1">
                        {items.map(({ rel, connectedNode, direction }) => {
                          const cnt = nodeTypes.find(t => t.id === connectedNode.type);
                          return (
                            <button
                              key={rel.id}
                              onClick={() => onNavigateToNode(connectedNode.id)}
                              className="w-full flex items-center gap-2 p-2 rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)] hover:bg-[var(--color-bg-secondary)] transition-colors text-left group"
                            >
                              <ArrowRight
                                className="size-3 text-muted-foreground shrink-0"
                                style={{ transform: direction === 'in' ? 'rotate(180deg)' : undefined }}
                              />
                              <div
                                className="size-5 rounded-full flex items-center justify-center shrink-0"
                                style={{ backgroundColor: cnt?.color ?? '#94A3B8' }}
                              >
                                {(() => {
                                  const CI = iconMap[cnt?.icon ?? 'Building2'] || Building2;
                                  return <CI className="size-2.5 text-white" />;
                                })()}
                              </div>
                              <span className="text-xs truncate flex-1">{connectedNode.label}</span>
                              <span className="text-[0.625rem] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                                View
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Relationship Detail ───

function RelationshipDetail({
  relationship,
  nodeTypes,
  relationshipTypes,
  allNodes,
  onNavigateToNode,
}: {
  relationship: KGRelationship;
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
  allNodes: KGNode[];
  onNavigateToNode: (id: string) => void;
}) {
  const rt = relationshipTypes.find(t => t.id === relationship.type);
  const source = allNodes.find(n => n.id === relationship.sourceId);
  const target = allNodes.find(n => n.id === relationship.targetId);
  const sourceType = nodeTypes.find(t => t.id === source?.type);
  const targetType = nodeTypes.find(t => t.id === target?.type);

  const SourceIcon = iconMap[sourceType?.icon ?? 'Building2'] || Building2;
  const TargetIcon = iconMap[targetType?.icon ?? 'Building2'] || Building2;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-5 pr-12">
        <Badge
          className="text-[0.625rem] px-2 py-0.5 mb-3"
          style={{
            backgroundColor: `${rt?.color ?? '#94A3B8'}15`,
            color: rt?.color ?? '#94A3B8',
            borderColor: `${rt?.color ?? '#94A3B8'}30`,
          }}
        >
          {rt?.label ?? relationship.type}
        </Badge>
        <h3 className="mb-1">Relationship Details</h3>
        <p className="text-xs text-muted-foreground">
          ID: {relationship.id}
        </p>
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Source → Target */}
        <div>
          <h4 className="text-xs text-muted-foreground mb-2" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Connected Nodes
          </h4>
          <div className="flex items-center gap-2">
            <button
              onClick={() => source && onNavigateToNode(source.id)}
              className="flex-1 flex items-center gap-2 p-3 rounded-[var(--radius-md)] border border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] transition-colors bg-card"
            >
              <div
                className="size-7 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: sourceType?.color }}
              >
                <SourceIcon className="size-3.5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="text-xs truncate">{source?.label ?? 'Unknown'}</p>
                <p className="text-[0.625rem] text-muted-foreground">{sourceType?.label}</p>
              </div>
            </button>

            <ArrowRight className="size-4 text-muted-foreground shrink-0" />

            <button
              onClick={() => target && onNavigateToNode(target.id)}
              className="flex-1 flex items-center gap-2 p-3 rounded-[var(--radius-md)] border border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] transition-colors bg-card"
            >
              <div
                className="size-7 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: targetType?.color }}
              >
                <TargetIcon className="size-3.5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="text-xs truncate">{target?.label ?? 'Unknown'}</p>
                <p className="text-[0.625rem] text-muted-foreground">{targetType?.label}</p>
              </div>
            </button>
          </div>
        </div>

        {/* Properties */}
        {Object.keys(relationship.properties).length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="text-xs text-muted-foreground mb-2" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Properties
              </h4>
              <div className="space-y-2">
                {Object.entries(relationship.properties).map(([key, value]) => (
                  <PropertyRow key={key} propKey={key} value={value} />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Property Renderer ───

function PropertyRow({ propKey, value }: { propKey: string; value: unknown }) {
  const label = propKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const renderValue = () => {
    if (value === null || value === undefined) {
      return <span className="text-muted-foreground italic">null</span>;
    }
    if (typeof value === 'boolean') {
      return (
        <Badge variant={value ? 'default' : 'secondary'} className="text-[0.625rem] px-1.5 py-0">
          {value ? 'Yes' : 'No'}
        </Badge>
      );
    }
    if (typeof value === 'number') {
      return <span className="text-sm">{value.toLocaleString()}</span>;
    }
    if (typeof value === 'string') {
      if (value.startsWith('http://') || value.startsWith('https://')) {
        return (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[var(--color-blue-500)] hover:underline flex items-center gap-1"
          >
            {value.replace(/^https?:\/\//, '')}
            <ExternalLink className="size-3 shrink-0" />
          </a>
        );
      }
      return <span className="text-sm">{value}</span>;
    }
    if (Array.isArray(value)) {
      return (
        <div className="flex flex-wrap gap-1">
          {value.map((item, i) => (
            <Badge key={i} variant="outline" className="text-[0.625rem] px-1.5 py-0">
              {String(item)}
            </Badge>
          ))}
        </div>
      );
    }
    if (typeof value === 'object') {
      return (
        <div className="space-y-1 mt-1">
          {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
            <div key={k} className="flex items-start gap-2 pl-2 border-l-2 border-[var(--color-border-subtle)]">
              <span className="text-[0.625rem] text-muted-foreground shrink-0" style={{ fontWeight: 500 }}>{k}:</span>
              <span className="text-[0.6875rem]">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
            </div>
          ))}
        </div>
      );
    }
    return <span className="text-sm">{String(value)}</span>;
  };

  return (
    <div className="p-2.5 rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)]">
      <div className="text-[0.625rem] text-muted-foreground mb-1" style={{ fontWeight: 600 }}>
        {label}
      </div>
      {renderValue()}
    </div>
  );
}
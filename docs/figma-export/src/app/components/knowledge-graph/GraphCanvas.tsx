import { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  type OnSelectionChangeParams,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import * as dagre from '@dagrejs/dagre';

import { KGNodeComponent, type KGNodeData } from './KGNodeComponent';
import { KGEdgeComponent, type KGEdgeData } from './KGEdgeComponent';
import { KGLegend } from './KGLegend';
import type {
  KGNode as KGNodeModel,
  KGRelationship,
  KGNodeType,
  KGRelationshipType,
} from '../../data/knowledgeGraphData';

const rfNodeTypes = { kgNode: KGNodeComponent };
const rfEdgeTypes = { kgEdge: KGEdgeComponent };

// ─── Dagre Layout ───

function getLayoutedElements(
  graphNodes: KGNodeModel[],
  graphEdges: KGRelationship[],
  nodeTypesMap: Map<string, KGNodeType>,
) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 100, edgesep: 40 });

  for (const node of graphNodes) {
    g.setNode(node.id, { width: 120, height: 70 });
  }
  for (const edge of graphEdges) {
    if (g.hasNode(edge.sourceId) && g.hasNode(edge.targetId)) {
      g.setEdge(edge.sourceId, edge.targetId);
    }
  }

  dagre.layout(g);

  const positions = new Map<string, { x: number; y: number }>();
  for (const node of graphNodes) {
    const pos = g.node(node.id);
    positions.set(node.id, { x: (pos?.x ?? 0) - 60, y: (pos?.y ?? 0) - 35 });
  }

  return positions;
}

function buildRfNodes(
  graphNodes: KGNodeModel[],
  positions: Map<string, { x: number; y: number }>,
  nodeTypesMap: Map<string, KGNodeType>,
): Node<KGNodeData>[] {
  return graphNodes.map(node => {
    const pos = positions.get(node.id) ?? { x: 0, y: 0 };
    const nt = nodeTypesMap.get(node.type);
    return {
      id: node.id,
      type: 'kgNode',
      position: { x: pos.x, y: pos.y },
      data: {
        label: node.label,
        nodeType: node.type,
        color: nt?.color ?? '#94A3B8',
        bgColor: nt?.bgColor ?? '#F1F5F9',
        icon: nt?.icon ?? 'Building2',
        dimmed: false,
        highlighted: false,
      },
    };
  });
}

// ─── Props ───

interface GraphCanvasProps {
  graphNodes: KGNodeModel[];
  graphEdges: KGRelationship[];
  nodeTypesData: KGNodeType[];
  relationshipTypesData: KGRelationshipType[];
  visibleNodeIds: Set<string>;
  visibleEdgeIds: Set<string>;
  searchHighlightIds: Set<string>;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectionChange: (nodeId: string | null, edgeId: string | null) => void;
  onPanToNode: React.MutableRefObject<((nodeId: string) => void) | null>;
}

export function GraphCanvas({
  graphNodes,
  graphEdges,
  nodeTypesData,
  relationshipTypesData,
  visibleNodeIds,
  visibleEdgeIds,
  searchHighlightIds,
  selectedNodeId,
  selectedEdgeId,
  onSelectionChange,
  onPanToNode,
}: GraphCanvasProps) {
  const nodeTypesMap = useMemo(() => new Map(nodeTypesData.map(nt => [nt.id, nt])), [nodeTypesData]);
  const relTypesMap = useMemo(() => new Map(relationshipTypesData.map(rt => [rt.id, rt])), [relationshipTypesData]);

  // Compute full layout once for all nodes
  const allPositions = useMemo(
    () => getLayoutedElements(graphNodes, graphEdges, nodeTypesMap),
    [graphNodes, graphEdges, nodeTypesMap],
  );

  const initialNodes = useMemo(
    () => buildRfNodes(graphNodes, allPositions, nodeTypesMap),
    [graphNodes, allPositions, nodeTypesMap],
  );

  const initialEdges = useMemo<Edge<KGEdgeData>[]>(
    () => graphEdges.map(edge => {
      const rt = relTypesMap.get(edge.type);
      return {
        id: edge.id,
        source: edge.sourceId,
        target: edge.targetId,
        type: 'kgEdge',
        markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#CBD5E1' },
        data: {
          relType: edge.type,
          relLabel: rt?.label ?? edge.type,
          color: rt?.color ?? '#94A3B8',
          dimmed: false,
          highlighted: false,
        },
      };
    }),
    [graphEdges, relTypesMap],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { setCenter, getNode, fitView } = useReactFlow();
  const isFirstRender = useRef(true);

  // Center on Account node on initial mount
  useEffect(() => {
    const accountNode = graphNodes.find(n => n.type === 'Account');
    if (accountNode) {
      const pos = allPositions.get(accountNode.id);
      if (pos) {
        // Small delay to let React Flow finish initial render
        setTimeout(() => {
          setCenter(pos.x + 60, pos.y + 35, { zoom: 1.0, duration: 0 });
        }, 50);
      }
    }
  }, []); // only on mount

  // Re-layout visible nodes when filters change
  useEffect(() => {
    const hasSearch = searchHighlightIds.size > 0;
    const isAllVisible = visibleNodeIds.size === graphNodes.length;

    // Compute positions: use full layout when unfiltered, re-layout visible subset when filtered
    let positions: Map<string, { x: number; y: number }>;
    if (isAllVisible) {
      positions = allPositions;
    } else {
      const visibleNodes = graphNodes.filter(n => visibleNodeIds.has(n.id));
      const visibleRels = graphEdges.filter(e => visibleEdgeIds.has(e.id));
      positions = getLayoutedElements(visibleNodes, visibleRels, nodeTypesMap);
    }

    setNodes(prev => prev.map(n => {
      const newPos = positions.get(n.id);
      return {
        ...n,
        hidden: !visibleNodeIds.has(n.id),
        position: newPos ?? n.position,
        data: {
          ...n.data,
          dimmed: hasSearch && !searchHighlightIds.has(n.id),
          highlighted: hasSearch && searchHighlightIds.has(n.id),
        },
      };
    }));

    setEdges(prev => prev.map(e => ({
      ...e,
      hidden: !visibleEdgeIds.has(e.id),
      data: {
        ...e.data,
        dimmed: hasSearch,
        highlighted: false,
      },
    })));

    // Fit view to show re-laid-out nodes (skip initial render since ReactFlow fitView handles it)
    if (isFirstRender.current) {
      isFirstRender.current = false;
    } else {
      // Small delay to let React Flow process position updates
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 400, nodes: [...visibleNodeIds].map(id => ({ id })) });
      }, 50);
    }
  }, [visibleNodeIds, visibleEdgeIds, searchHighlightIds, graphNodes, graphEdges, allPositions, nodeTypesMap, fitView]);

  // Pan to node function
  useEffect(() => {
    onPanToNode.current = (nodeId: string) => {
      const rfNode = getNode(nodeId);
      if (rfNode) {
        setCenter(rfNode.position.x + 60, rfNode.position.y + 35, { zoom: 1.2, duration: 600 });
        onSelectionChange(nodeId, null);
      }
    };
  }, [getNode, setCenter, onSelectionChange, onPanToNode]);

  // Selection change
  const handleSelectionChange = useCallback(({ nodes: selNodes, edges: selEdges }: OnSelectionChangeParams) => {
    if (selNodes.length > 0) {
      onSelectionChange(selNodes[0].id, null);
    } else if (selEdges.length > 0) {
      onSelectionChange(null, selEdges[0].id);
    }
  }, [onSelectionChange]);

  // Click on pane deselects
  const handlePaneClick = useCallback(() => {
    onSelectionChange(null, null);
  }, [onSelectionChange]);

  return (
    <div className="relative w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onSelectionChange={handleSelectionChange}
        onPaneClick={handlePaneClick}
        nodeTypes={rfNodeTypes}
        edgeTypes={rfEdgeTypes}
        minZoom={0.1}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ animated: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--color-border-subtle)" />
        <Controls
          showInteractive={false}
          className="!bg-[var(--color-bg-elevated)] !border-[var(--color-border-default)] !rounded-[var(--radius-md)] !shadow-md"
        />
        <MiniMap
          nodeColor={(node: Node) => {
            const data = node.data as KGNodeData;
            return data?.color ?? '#94A3B8';
          }}
          maskColor="rgba(250, 251, 252, 0.7)"
          className="!bg-[var(--color-bg-elevated)] !border-[var(--color-border-default)] !rounded-[var(--radius-md)]"
          style={{ width: 140, height: 90 }}
        />
        <KGLegend nodeTypes={nodeTypesData} relationshipTypes={relationshipTypesData} />
      </ReactFlow>
    </div>
  );
}
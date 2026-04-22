import { useState, useCallback, useMemo, useRef } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { GraphCanvas } from '../../components/knowledge-graph/GraphCanvas';
import { KGDetailPanel } from '../../components/knowledge-graph/KGDetailPanel';
import { KGSearchBar } from '../../components/knowledge-graph/KGSearchBar';
import {
  knowledgeGraph,
} from '../../data/knowledgeGraphData';

export function KnowledgeGraphPage() {
  const { nodeTypes, relationshipTypes, nodes, relationships } = knowledgeGraph;

  // Selection
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');

  // Filters
  const [activeNodeTypeFilters, setActiveNodeTypeFilters] = useState<Set<string>>(new Set());
  const [activeRelTypeFilters, setActiveRelTypeFilters] = useState<Set<string>>(new Set());

  // Pan-to-node ref
  const panToNodeRef = useRef<((nodeId: string) => void) | null>(null);

  // ─── Derived: visible nodes & edges ───

  const visibleNodeIds = useMemo(() => {
    if (activeNodeTypeFilters.size === 0) {
      return new Set(nodes.map(n => n.id));
    }
    return new Set(nodes.filter(n => activeNodeTypeFilters.has(n.type)).map(n => n.id));
  }, [nodes, activeNodeTypeFilters]);

  const visibleEdgeIds = useMemo(() => {
    const edgeSet = new Set<string>();
    for (const rel of relationships) {
      if (!visibleNodeIds.has(rel.sourceId) || !visibleNodeIds.has(rel.targetId)) continue;
      if (activeRelTypeFilters.size > 0 && !activeRelTypeFilters.has(rel.type)) continue;
      edgeSet.add(rel.id);
    }
    return edgeSet;
  }, [relationships, visibleNodeIds, activeRelTypeFilters]);

  // ─── Search highlights ───

  const searchHighlightIds = useMemo(() => {
    if (!searchQuery.trim()) return new Set<string>();
    const q = searchQuery.toLowerCase();
    return new Set(
      nodes
        .filter(n => {
          if (n.label.toLowerCase().includes(q)) return true;
          for (const v of Object.values(n.properties)) {
            if (typeof v === 'string' && v.toLowerCase().includes(q)) return true;
          }
          return false;
        })
        .map(n => n.id)
    );
  }, [nodes, searchQuery]);

  // ─── Selection ───

  const handleSelectionChange = useCallback((nodeId: string | null, edgeId: string | null) => {
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(edgeId);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, []);

  const handleNavigateToNode = useCallback((nodeId: string) => {
    panToNodeRef.current?.(nodeId);
  }, []);

  // ─── Filters ───

  const toggleNodeTypeFilter = useCallback((typeId: string) => {
    setActiveNodeTypeFilters(prev => {
      const next = new Set(prev);
      if (next.has(typeId)) next.delete(typeId);
      else next.add(typeId);
      return next;
    });
  }, []);

  const toggleRelTypeFilter = useCallback((typeId: string) => {
    setActiveRelTypeFilters(prev => {
      const next = new Set(prev);
      if (next.has(typeId)) next.delete(typeId);
      else next.add(typeId);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setActiveNodeTypeFilters(new Set());
    setActiveRelTypeFilters(new Set());
    setSearchQuery('');
  }, []);

  const handleSelectSearchResult = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
    panToNodeRef.current?.(nodeId);
  }, []);

  // Resolved selection objects
  const selectedNode = selectedNodeId ? nodes.find(n => n.id === selectedNodeId) ?? null : null;
  const selectedRelationship = selectedEdgeId ? relationships.find(r => r.id === selectedEdgeId) ?? null : null;

  return (
    <div className="flex flex-col h-full max-w-none">
      {/* Search / Filter Toolbar */}
      <div className="px-6 py-3 border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
        <KGSearchBar
          nodeTypes={nodeTypes}
          relationshipTypes={relationshipTypes}
          allNodes={nodes}
          activeNodeTypeFilters={activeNodeTypeFilters}
          activeRelTypeFilters={activeRelTypeFilters}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onToggleNodeTypeFilter={toggleNodeTypeFilter}
          onToggleRelTypeFilter={toggleRelTypeFilter}
          onClearFilters={clearFilters}
          onSelectSearchResult={handleSelectSearchResult}
          visibleNodeCount={visibleNodeIds.size}
          totalNodeCount={nodes.length}
          visibleEdgeCount={visibleEdgeIds.size}
          totalEdgeCount={relationships.length}
        />
      </div>

      {/* Graph + Detail Panel */}
      <div className="flex-1 relative overflow-hidden">
        <ReactFlowProvider>
          <GraphCanvas
            graphNodes={nodes}
            graphEdges={relationships}
            nodeTypesData={nodeTypes}
            relationshipTypesData={relationshipTypes}
            visibleNodeIds={visibleNodeIds}
            visibleEdgeIds={visibleEdgeIds}
            searchHighlightIds={searchHighlightIds}
            selectedNodeId={selectedNodeId}
            selectedEdgeId={selectedEdgeId}
            onSelectionChange={handleSelectionChange}
            onPanToNode={panToNodeRef}
          />
        </ReactFlowProvider>

        {/* Detail Panel */}
        <KGDetailPanel
          selectedNode={selectedNode}
          selectedRelationship={selectedRelationship}
          nodeTypes={nodeTypes}
          relationshipTypes={relationshipTypes}
          allNodes={nodes}
          allRelationships={relationships}
          onClose={handleClosePanel}
          onNavigateToNode={handleNavigateToNode}
        />
      </div>
    </div>
  );
}
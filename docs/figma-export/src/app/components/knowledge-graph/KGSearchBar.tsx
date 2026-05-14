import { useState, useRef, useEffect } from 'react';
import { Search, X, Filter, ChevronDown } from 'lucide-react';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import type { KGNodeType, KGRelationshipType, KGNode } from '../../data/knowledgeGraphData';
import { cn } from '../ui/utils';

interface KGSearchBarProps {
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
  allNodes: KGNode[];
  activeNodeTypeFilters: Set<string>;
  activeRelTypeFilters: Set<string>;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onToggleNodeTypeFilter: (typeId: string) => void;
  onToggleRelTypeFilter: (typeId: string) => void;
  onClearFilters: () => void;
  onSelectSearchResult: (nodeId: string) => void;
  visibleNodeCount: number;
  totalNodeCount: number;
  visibleEdgeCount: number;
  totalEdgeCount: number;
}

export function KGSearchBar({
  nodeTypes,
  relationshipTypes,
  allNodes,
  activeNodeTypeFilters,
  activeRelTypeFilters,
  searchQuery,
  onSearchChange,
  onToggleNodeTypeFilter,
  onToggleRelTypeFilter,
  onClearFilters,
  onSelectSearchResult,
  visibleNodeCount,
  totalNodeCount,
  visibleEdgeCount,
  totalEdgeCount,
}: KGSearchBarProps) {
  const [showRelDropdown, setShowRelDropdown] = useState(false);
  const [showNodeTypeDropdown, setShowNodeTypeDropdown] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const nodeTypeDropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowRelDropdown(false);
      }
      if (nodeTypeDropdownRef.current && !nodeTypeDropdownRef.current.contains(e.target as Node)) {
        setShowNodeTypeDropdown(false);
      }
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearchResults(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Search results
  const searchResults = searchQuery.trim().length > 0
    ? allNodes.filter(n => {
        const q = searchQuery.toLowerCase();
        if (n.label.toLowerCase().includes(q)) return true;
        for (const v of Object.values(n.properties)) {
          if (typeof v === 'string' && v.toLowerCase().includes(q)) return true;
        }
        return false;
      }).slice(0, 8)
    : [];

  const hasActiveFilters = activeNodeTypeFilters.size > 0 || activeRelTypeFilters.size > 0;
  const activeRelCount = activeRelTypeFilters.size;
  const activeNodeCount = activeNodeTypeFilters.size;

  return (
    <div className="flex items-center gap-3 min-w-0">
      {/* Search */}
      <div className="relative" ref={searchRef}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={e => {
              onSearchChange(e.target.value);
              setShowSearchResults(true);
            }}
            onFocus={() => setShowSearchResults(true)}
            className="pl-9 w-[15rem] h-9"
          />
          {searchQuery && (
            <button
              onClick={() => { onSearchChange(''); setShowSearchResults(false); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        {/* Search results dropdown */}
        {showSearchResults && searchResults.length > 0 && (
          <div className="absolute top-full mt-1 left-0 w-[18.75rem] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg z-30 max-h-[17.5rem] overflow-y-auto">
            {searchResults.map(node => {
              const nt = nodeTypes.find(t => t.id === node.type);
              return (
                <button
                  key={node.id}
                  onClick={() => {
                    onSelectSearchResult(node.id);
                    setShowSearchResults(false);
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-[var(--color-bg-secondary)] transition-colors text-left"
                >
                  <div
                    className="size-6 rounded-full flex items-center justify-center shrink-0"
                    style={{ backgroundColor: nt?.color }}
                  >
                    <span className="text-white text-[0.5625rem]" style={{ fontWeight: 700 }}>
                      {nt?.label?.charAt(0) ?? '?'}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm truncate">{node.label}</p>
                    <p className="text-[0.625rem] text-muted-foreground">{nt?.label ?? node.type}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-[var(--color-border-default)]" />

      {/* Node Type Filter Dropdown */}
      <div className="relative shrink-0" ref={nodeTypeDropdownRef}>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 h-8 text-[0.6875rem]"
          onClick={() => setShowNodeTypeDropdown(!showNodeTypeDropdown)}
        >
          <Filter className="size-3" />
          Node Types
          {activeNodeCount > 0 && (
            <Badge variant="default" className="text-[0.5625rem] px-1 py-0 ml-0.5">
              {activeNodeCount}
            </Badge>
          )}
          <ChevronDown className={cn("size-3 transition-transform", showNodeTypeDropdown && "rotate-180")} />
        </Button>

        {showNodeTypeDropdown && (
          <div className="absolute top-full mt-1 left-0 w-[13.75rem] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg z-30 p-2 space-y-0.5 max-h-[20rem] overflow-y-auto">
            {nodeTypes.map(nt => (
              <label
                key={nt.id}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
              >
                <Checkbox
                  checked={activeNodeTypeFilters.has(nt.id)}
                  onCheckedChange={() => onToggleNodeTypeFilter(nt.id)}
                />
                <div className="size-2 rounded-full shrink-0" style={{ backgroundColor: nt.color }} />
                <span className="text-xs">{nt.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-[var(--color-border-default)] shrink-0" />

      {/* Relationship Type Filter Dropdown */}
      <div className="relative shrink-0" ref={dropdownRef}>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 h-8 text-[0.6875rem]"
          onClick={() => setShowRelDropdown(!showRelDropdown)}
        >
          <Filter className="size-3" />
          Relationships
          {activeRelCount > 0 && (
            <Badge variant="default" className="text-[0.5625rem] px-1 py-0 ml-0.5">
              {activeRelCount}
            </Badge>
          )}
          <ChevronDown className={cn("size-3 transition-transform", showRelDropdown && "rotate-180")} />
        </Button>

        {showRelDropdown && (
          <div className="absolute top-full mt-1 right-0 w-[13.75rem] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg z-30 p-2 space-y-0.5">
            {relationshipTypes.map(rt => (
              <label
                key={rt.id}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
              >
                <Checkbox
                  checked={activeRelTypeFilters.has(rt.id)}
                  onCheckedChange={() => onToggleRelTypeFilter(rt.id)}
                />
                <div className="size-2 rounded-full shrink-0" style={{ backgroundColor: rt.color }} />
                <span className="text-xs">{rt.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Clear Filters */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-[0.6875rem] text-muted-foreground shrink-0"
          onClick={onClearFilters}
        >
          <X className="size-3 mr-1" />
          Clear
        </Button>
      )}

      {/* Counts */}
      <span className="text-[0.6875rem] text-muted-foreground ml-auto shrink-0 whitespace-nowrap">
        {visibleNodeCount === totalNodeCount
          ? `${totalNodeCount} nodes`
          : `${visibleNodeCount} of ${totalNodeCount} nodes`
        }
        {' / '}
        {visibleEdgeCount === totalEdgeCount
          ? `${totalEdgeCount} relationships`
          : `${visibleEdgeCount} of ${totalEdgeCount}`
        }
      </span>
    </div>
  );
}
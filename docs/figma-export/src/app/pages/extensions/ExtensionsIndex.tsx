import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  Search,
  ArrowRight,
  CheckCircle2,
  Power,
  Zap,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { extensionCatalog, type ExtensionDefinition } from '../../data/extensionRegistry';
import { useExtensions } from '../../contexts/ExtensionsContext';
import { ExtensionActivatePanel } from './ExtensionActivatePanel';

type SourceFilter = 'all' | 'official' | 'community';

export function ExtensionsIndex() {
  const { isActive } = useExtensions();
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [activatingExtension, setActivatingExtension] = useState<ExtensionDefinition | null>(null);

  const filteredExtensions = extensionCatalog.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = sourceFilter === 'all' || p.source === sourceFilter;
    return matchesSearch && matchesSource;
  });

  const activeCount = extensionCatalog.filter((p) => isActive(p.id)).length;
  const officialCount = extensionCatalog.filter((p) => p.source === 'official').length;
  const communityCount = extensionCatalog.filter((p) => p.source === 'community').length;

  const filterButtons: { value: SourceFilter; label: string; count: number }[] = [
    { value: 'all', label: 'All Extensions', count: extensionCatalog.length },
    { value: 'official', label: 'Official', count: officialCount },
    { value: 'community', label: 'Community', count: communityCount },
  ];

  return (
    <div className="px-6 pb-6">
      {/* Stats row */}
      <div className="flex items-center gap-4 mb-5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Zap className="size-4 text-violet-500" />
          <span>
            <span className="text-foreground">{activeCount}</span> of {extensionCatalog.length} extensions
            active
          </span>
        </div>
      </div>

      {/* Filter tabs + Search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
        <div className="flex items-center gap-1 p-1 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)]">
          {filterButtons.map((fb) => (
            <button
              key={fb.value}
              onClick={() => setSourceFilter(fb.value)}
              className={`px-3 py-1.5 rounded-[var(--radius-sm)] text-xs transition-all flex items-center gap-1.5 ${
                sourceFilter === fb.value
                  ? 'bg-[var(--color-violet-500)] text-[var(--color-text-inverse)]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-[var(--color-bg-secondary)]'
              }`}
            >
              {fb.value === 'official' && <ShieldCheck className="size-3" />}
              {fb.value === 'community' && <Users className="size-3" />}
              {fb.label}
              <span
                className={`ml-0.5 text-[0.625rem] ${
                  sourceFilter === fb.value ? 'opacity-80' : 'opacity-60'
                }`}
              >
                {fb.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative flex-1 w-full sm:w-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search extensions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)] text-sm focus:outline-none focus:border-[var(--color-violet-500)] transition-colors"
          />
        </div>
      </div>

      {/* Extension Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredExtensions.map((extension) => (
          <ExtensionCard
            key={extension.id}
            extension={extension}
            active={isActive(extension.id)}
            onActivate={() => setActivatingExtension(extension)}
          />
        ))}
      </div>

      {filteredExtensions.length === 0 && (
        <div className="text-center py-12">
          <Search className="size-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No extensions match your search.</p>
        </div>
      )}

      {/* Activation Panel */}
      {activatingExtension && (
        <ExtensionActivatePanel
          extension={activatingExtension}
          onClose={() => setActivatingExtension(null)}
        />
      )}
    </div>
  );
}

function ExtensionCard({
  extension,
  active,
  onActivate,
}: {
  extension: ExtensionDefinition;
  active: boolean;
  onActivate: () => void;
}) {
  const navigate = useNavigate();

  return (
    <div
      className="group relative p-5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all bg-card cursor-pointer"
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
      onClick={() => {
        if (active) {
          navigate(`/extensions/${extension.slug}`);
        } else {
          onActivate();
        }
      }}
    >
      {/* Top-right badges */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        {extension.source === 'official' ? (
          <Badge variant="outline" className="gap-1 text-[0.625rem] px-1.5 py-0.5 border-violet-300 text-violet-600">
            <ShieldCheck className="size-2.5" />
            KEN-E
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1 text-[0.625rem] px-1.5 py-0.5 border-sky-300 text-sky-600">
            <Users className="size-2.5" />
            Community
          </Badge>
        )}
        {active && (
          <Badge variant="default" className="gap-1 bg-green-600 text-white">
            <CheckCircle2 className="size-3" />
            Active
          </Badge>
        )}
      </div>

      {/* Icon */}
      <div
        className={`size-11 rounded-[var(--radius-md)] flex items-center justify-center mb-4 ${extension.rotation}`}
        style={{ backgroundColor: extension.color, boxShadow: extension.shadow }}
      >
        <extension.icon className="size-5 text-[var(--color-text-inverse)]" />
      </div>

      {/* Content */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-sm">{extension.name}</h3>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{extension.description}</p>
        {extension.author && (
          <p className="text-[0.625rem] text-muted-foreground mt-1.5">
            by <span className="text-foreground">{extension.author}</span>
          </p>
        )}
      </div>

      {/* Category + Action */}
      <div className="flex items-center justify-between">
        <Badge variant="outline">{extension.category}</Badge>
        {active ? (
          <div className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-violet-500 transition-colors">
            Open
            <ArrowRight className="size-3" />
          </div>
        ) : (
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            onClick={(e) => {
              e.stopPropagation();
              onActivate();
            }}
          >
            <Power className="size-3" />
            Activate
          </Button>
        )}
      </div>
    </div>
  );
}
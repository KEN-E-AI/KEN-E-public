import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Plus,
  Bot,
  Wrench,
  Zap,
  Cpu,
  Puzzle,
  BarChart3,
  Megaphone,
  FileText,
  Settings,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { OriginBadge } from '../../components/OriginBadge';
import { Sheet, SheetContent } from '../../components/ui/sheet';
import { ConfigureAgentPanel } from '../../components/ConfigureAgentPanel';
import { mockAgents, availableModels } from '../../data/mockData';
import type { Agent } from '../../data/mockData';
import { useWorkflowFilter } from './WorkflowsLayout';

const AGENT_STYLES: Record<string, { icon: typeof Bot; accent: string; shadow: string }> = {
  'agent-1': { icon: BarChart3, accent: 'var(--color-blue-500)', shadow: 'var(--shadow-color-blue, 0 4px 12px rgba(59,130,246,0.25))' },
  'agent-2': { icon: Megaphone, accent: 'var(--color-amber-500)', shadow: 'var(--shadow-color-amber, 0 4px 12px rgba(245,158,11,0.25))' },
  'agent-3': { icon: Bot, accent: 'var(--color-violet-500)', shadow: 'var(--shadow-color-violet, 0 4px 12px rgba(139,92,246,0.25))' },
  'agent-4': { icon: FileText, accent: 'var(--color-teal-500)', shadow: 'var(--shadow-color-teal, 0 4px 12px rgba(20,184,166,0.25))' },
};

const FALLBACK_ACCENTS = [
  { accent: 'var(--color-blue-500)', shadow: '0 4px 12px rgba(59,130,246,0.25)' },
  { accent: 'var(--color-amber-500)', shadow: '0 4px 12px rgba(245,158,11,0.25)' },
  { accent: 'var(--color-violet-500)', shadow: '0 4px 12px rgba(139,92,246,0.25)' },
  { accent: 'var(--color-teal-500)', shadow: '0 4px 12px rgba(20,184,166,0.25)' },
];

export function AgentsPage() {
  const sourceFilter = useWorkflowFilter();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const agents = useMemo(() => {
    if (sourceFilter === 'custom') return mockAgents.filter(a => !a.extensionId);
    if (sourceFilter === 'extension') return mockAgents.filter(a => !!a.extensionId);
    return mockAgents;
  }, [sourceFilter]);

  return (
    <div className="px-6 pb-6">
      {/* Description */}
      <div className="mb-4 p-4 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)]">
        <p className="text-sm text-muted-foreground">
          Agents are AI assistants equipped with specific tools and skills. Configure an agent with a model,
          instructions, and capabilities — then use it to generate powerful automations.
        </p>
      </div>

      {/* Actions */}
      <div className="flex justify-end mb-4">
        <Link to="/workflows/agents/new">
          <Button
            className="gap-2"
            style={{
              transitionTimingFunction: 'var(--ease-bounce)',
              transitionDuration: 'var(--duration-default)',
            }}
          >
            <Plus className="size-4" />
            New Agent
          </Button>
        </Link>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {agents.map((agent, idx) => (
          <AgentCard key={agent.id} agent={agent} index={idx} onConfigure={setSelectedAgent} />
        ))}

        {agents.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Bot className="size-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              {sourceFilter === 'custom' ? 'No custom agents yet.' : sourceFilter === 'extension' ? 'No extension-managed agents.' : 'No agents created yet.'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Create an agent to get started with AI-powered workflows.</p>
          </div>
        )}
      </div>

      <Sheet open={selectedAgent !== null} onOpenChange={() => setSelectedAgent(null)}>
        <SheetContent className="sm:max-w-md p-0 gap-0">
          {selectedAgent && (
            <ConfigureAgentPanel
              agent={selectedAgent}
              onClose={() => setSelectedAgent(null)}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function AgentCard({ agent, index, onConfigure }: { agent: Agent; index: number; onConfigure: (agent: Agent) => void }) {
  const model = availableModels.find(m => m.id === agent.model);
  const nativeTools = agent.tools.filter(t => t.category === 'native').length;
  const integrationTools = agent.tools.filter(t => t.category === 'integration').length;
  const totalTools = nativeTools + integrationTools;
  const skillTools = agent.tools.filter(t => t.category === 'skill').length;

  const style = AGENT_STYLES[agent.id] ?? {
    icon: Bot,
    accent: FALLBACK_ACCENTS[index % FALLBACK_ACCENTS.length].accent,
    shadow: FALLBACK_ACCENTS[index % FALLBACK_ACCENTS.length].shadow,
  };
  const IconComponent = style.icon;

  return (
    <div
      className="relative p-4 rounded-[14px] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all cursor-pointer bg-card overflow-hidden flex flex-col"
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
      onClick={() => onConfigure(agent)}
    >
      {/* Configure gear (top-right) */}
      <button
        type="button"
        className="absolute top-3 right-3 size-7 rounded-[var(--radius-sm)] flex items-center justify-center text-[var(--color-text-secondary)] cursor-pointer transition-colors hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-violet-500)]"
        onClick={(e) => { e.stopPropagation(); onConfigure(agent); }}
        aria-label={`Configure ${agent.name}`}
      >
        <Settings className="size-4" />
      </button>

      {/* Icon */}
      <div className="mb-3">
        <div
          className="size-11 rounded-xl flex items-center justify-center"
          style={{ background: style.accent, boxShadow: `0 4px 12px color-mix(in srgb, ${style.accent} 25%, transparent)` }}
        >
          <IconComponent className="size-5 text-white" />
        </div>
      </div>

      {/* Name + Status */}
      <div className="flex items-center gap-1.5 flex-wrap mb-1.5 pr-8" style={{ minHeight: 22 }}>
        <span className="text-[13px]" style={{ fontWeight: 700, lineHeight: 1.25 }}>{agent.name}</span>
        {agent.status === 'inactive' && (
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wide bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
            style={{ fontWeight: 700, lineHeight: 1.4 }}
          >
            <span className="size-1.5 rounded-full bg-[var(--color-text-disabled)]" />
            Inactive
          </span>
        )}
      </div>

      {/* Model */}
      <div className="flex items-center gap-1 text-[11px] text-[var(--color-text-tertiary)] mb-2.5">
        <span>{model?.icon}</span>
        {model?.name ?? agent.model}
      </div>

      {/* Chips */}
      <div className="flex flex-wrap gap-1 mb-3">
        {totalTools > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]" style={{ fontWeight: 700 }}>
            {totalTools} tool{totalTools !== 1 ? 's' : ''}
          </span>
        )}
        {skillTools > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-violet-100)] text-[var(--color-violet-500)]" style={{ fontWeight: 700 }}>
            {skillTools} skill{skillTools !== 1 ? 's' : ''}
          </span>
        )}
        {agent.automationsGenerated > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-teal-100)] text-[var(--color-teal-500)]" style={{ fontWeight: 700 }}>
            {agent.automationsGenerated} auto{agent.automationsGenerated !== 1 ? 's' : ''}
          </span>
        )}
        {agent.extensionId && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-amber-100)] text-[var(--color-amber-500)]" style={{ fontWeight: 700 }}>
            Extension
          </span>
        )}
      </div>

    </div>
  );
}
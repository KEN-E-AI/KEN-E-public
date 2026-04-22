import { useMemo } from 'react';
import {
  Plus,
  Lightbulb,
  Sparkles,
  Bot,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { OriginBadge } from '../../components/OriginBadge';
import { mockSkills, mockAgents } from '../../data/mockData';
import type { Skill } from '../../data/mockData';
import { useWorkflowFilter } from './WorkflowsLayout';

export function SkillsPage() {
  const sourceFilter = useWorkflowFilter();

  const skills = useMemo(() => {
    if (sourceFilter === 'custom') return mockSkills.filter(s => !s.extensionId);
    if (sourceFilter === 'extension') return mockSkills.filter(s => !!s.extensionId);
    return mockSkills;
  }, [sourceFilter]);

  return (
    <div className="px-6 pb-6">
      {/* Description */}
      <div className="mb-4 p-4 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)]">
        <p className="text-sm text-muted-foreground">
          Procedural knowledge that agents can apply on-demand using the Anthropic Agent Skills standard.
          KEN-E invokes these automatically when needed or when you explicitly request them.
        </p>
      </div>

      {/* Actions */}
      <div className="flex justify-end mb-4">
        <Button
          className="gap-2"
          style={{
            transitionTimingFunction: 'var(--ease-bounce)',
            transitionDuration: 'var(--duration-default)',
          }}
        >
          <Plus className="size-4" />
          New Skill
        </Button>
      </div>

      {/* Skills List */}
      <div className="space-y-3">
        {skills.map(skill => (
          <SkillCard key={skill.id} skill={skill} />
        ))}

        {skills.length === 0 && (
          <div className="text-center py-12">
            <Lightbulb className="size-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              {sourceFilter === 'custom' ? 'No custom skills yet.' : sourceFilter === 'extension' ? 'No extension-managed skills.' : 'No skills created yet.'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Create skills to automate tasks like SEO optimization, content repurposing, and more.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function SkillCard({ skill }: { skill: Skill }) {
  const agentNames = skill.usedByAgents
    .map(id => mockAgents.find(a => a.id === id)?.name)
    .filter(Boolean);

  return (
    <div
      className="flex items-center gap-4 p-5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all cursor-pointer bg-card"
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-fast)',
      }}
    >
      <div
        className="size-10 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0 rotate-2"
        style={{ boxShadow: 'var(--shadow-color-violet)' }}
      >
        <Lightbulb className="size-5 text-[var(--color-text-inverse)]" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm truncate">{skill.name}</p>
          <Badge variant="secondary" className="capitalize">
            {skill.category}
          </Badge>
          <OriginBadge extensionId={skill.extensionId} />
        </div>
        <p className="text-xs text-muted-foreground truncate">{skill.description}</p>
        {agentNames.length > 0 && (
          <div className="flex items-center gap-1 mt-1.5 text-xs text-[var(--color-teal-500)]">
            <Bot className="size-3" />
            Used by {agentNames.join(', ')}
          </div>
        )}
      </div>

      <div className="shrink-0 text-right space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-end">
          <Sparkles className="size-3" />
          {skill.uses} uses
        </div>
      </div>

      <Button variant="outline" size="sm" className="shrink-0">
        Run
      </Button>
    </div>
  );
}
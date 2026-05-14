import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Bot,
  Wrench,
  Zap,
  Sparkles,
  Plus,
  X,
  Link2Off,
  Info,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { availableModels, availableTools, skillTools } from '../../data/mockData';
import type { AgentTool } from '../../data/mockData';
import { cn } from '../../components/ui/utils';

const STEPS = [
  { id: 1, label: 'Identity & Model' },
  { id: 2, label: 'Tools & Skills' },
  { id: 3, label: 'Review & Create' },
];

export function AgentCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  // Step 1 state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [model, setModel] = useState('goldilocks');
  const [instructions, setInstructions] = useState('');

  // Step 2 state
  const [equippedToolIds, setEquippedToolIds] = useState<Set<string>>(new Set());

  // Combined tool catalog
  const allTools = useMemo(() => [...availableTools, ...skillTools], []);

  const equippedTools = useMemo(
    () => allTools.filter(t => equippedToolIds.has(t.id)),
    [allTools, equippedToolIds]
  );

  const selectedModel = availableModels.find(m => m.id === model);

  const canProceedStep1 = name.trim().length > 0 && model.length > 0;
  const canProceedStep2 = true; // tools are optional

  const toggleTool = (toolId: string) => {
    setEquippedToolIds(prev => {
      const next = new Set(prev);
      if (next.has(toolId)) next.delete(toolId);
      else next.add(toolId);
      return next;
    });
  };

  const handleCreate = () => {
    // In a real app this would POST to an API. For now, navigate back.
    navigate('/workflows');
  };

  return (
    <div className="px-6 pb-6">
      {/* Back button */}
      <Link to="/workflows">
        <Button variant="ghost" size="sm" className="gap-2 mb-4 -ml-2 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
          Back to Agents
        </Button>
      </Link>

      <h1 className="mb-1">Create Agent</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Configure an AI agent with a model, instructions, and the tools it needs.
      </p>

      {/* Stepper */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2">
            <button
              onClick={() => {
                if (s.id < step) setStep(s.id);
              }}
              disabled={s.id > step}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-pill)] transition-all text-sm",
                s.id === step
                  ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                  : s.id < step
                    ? "bg-[var(--color-teal-100)] text-[var(--color-teal-500)] cursor-pointer hover:-translate-y-0.5"
                    : "bg-[var(--color-bg-secondary)] text-muted-foreground cursor-default"
              )}
              style={{
                transitionTimingFunction: 'var(--ease-bounce)',
                transitionDuration: 'var(--duration-fast)',
              }}
            >
              {s.id < step ? (
                <Check className="size-3.5" />
              ) : (
                <span className="size-5 flex items-center justify-center rounded-full bg-white/20 text-xs">{s.id}</span>
              )}
              <span>{s.label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <div className="w-8 h-px bg-[var(--color-border-default)]" />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      {step === 1 && (
        <StepIdentity
          name={name}
          setName={setName}
          description={description}
          setDescription={setDescription}
          model={model}
          setModel={setModel}
          instructions={instructions}
          setInstructions={setInstructions}
        />
      )}
      {step === 2 && (
        <StepTools
          allTools={allTools}
          equippedToolIds={equippedToolIds}
          toggleTool={toggleTool}
        />
      )}
      {step === 3 && (
        <StepReview
          name={name}
          description={description}
          model={selectedModel}
          instructions={instructions}
          equippedTools={equippedTools}
        />
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between mt-8 pt-6" style={{ borderTop: '2px dashed var(--color-border-default)' }}>
        <div>
          {step > 1 && (
            <Button variant="outline" onClick={() => setStep(step - 1)} className="gap-2">
              <ArrowLeft className="size-4" />
              Previous
            </Button>
          )}
        </div>
        <div>
          {step < 3 && (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !canProceedStep1}
              className="gap-2"
            >
              Next
              <ArrowRight className="size-4" />
            </Button>
          )}
          {step === 3 && (
            <Button onClick={handleCreate} className="gap-2">
              <Bot className="size-4" />
              Create Agent
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Step 1: Identity & Model ───

function StepIdentity({
  name, setName,
  description, setDescription,
  model, setModel,
  instructions, setInstructions,
}: {
  name: string; setName: (v: string) => void;
  description: string; setDescription: (v: string) => void;
  model: string; setModel: (v: string) => void;
  instructions: string; setInstructions: (v: string) => void;
}) {
  return (
    <div className="space-y-6 max-w-2xl">
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="agent-name">Agent Name</Label>
        <Input
          id="agent-name"
          placeholder="e.g. Content Strategist, SEO Analyst..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="max-w-md"
        />
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="agent-description">Description</Label>
        <Textarea
          id="agent-description"
          placeholder="e.g. Specializes in analyzing Google Analytics data and providing actionable SEO recommendations..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="max-w-xl resize-y"
        />
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-[var(--color-violet-100)] border border-[var(--color-violet-300)]">
          <Info className="size-4 text-[var(--color-violet-500)] mt-0.5 shrink-0" />
          <p className="text-xs text-[var(--color-violet-500)]">
            The description is used by KEN-E (the orchestrator agent) to understand this agent's purpose and decide when tasks should be delegated to it. A clear, specific description improves task routing accuracy.
          </p>
        </div>
      </div>

      {/* Model Selector */}
      <div className="space-y-2">
        <Label>Model Tier</Label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {availableModels.map(m => (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={cn(
                "flex flex-col items-center p-4 rounded-[var(--radius-md)] border-2 transition-all text-center",
                model === m.id
                  ? "border-[var(--color-violet-500)] bg-[var(--color-violet-100)]"
                  : "border-[var(--color-border-default)] bg-card hover:border-[var(--color-border-strong)] hover:-translate-y-0.5"
              )}
              style={{
                transitionTimingFunction: 'var(--ease-bounce)',
                transitionDuration: 'var(--duration-fast)',
              }}
            >
              <span className="text-2xl mb-2">{m.icon}</span>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm" style={{ fontWeight: 600 }}>{m.name}</span>
                {m.badge && (
                  <Badge variant="secondary" className="text-[0.625rem] px-1.5 py-0">
                    {m.badge}
                  </Badge>
                )}
              </div>
              <span className="text-xs text-muted-foreground">{m.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Instructions */}
      <div className="space-y-2">
        <Label htmlFor="agent-instructions">Instructions</Label>
        <p className="text-xs text-muted-foreground">
          Define the agent's persona, behavior, and any constraints. Be specific about how it should approach tasks.
        </p>
        <Textarea
          id="agent-instructions"
          placeholder="You are a marketing expert who specializes in..."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          className="min-h-[8.75rem]"
        />
      </div>
    </div>
  );
}

// ─── Step 2: Tools & Skills ───

function StepTools({
  allTools,
  equippedToolIds,
  toggleTool,
}: {
  allTools: AgentTool[];
  equippedToolIds: Set<string>;
  toggleTool: (id: string) => void;
}) {
  const [filter, setFilter] = useState<'all' | 'native' | 'integration' | 'skill'>('all');

  const filteredTools = filter === 'all'
    ? allTools
    : allTools.filter(t => t.category === filter);

  const equipped = allTools.filter(t => equippedToolIds.has(t.id));

  const categoryIcon = (cat: string) => {
    if (cat === 'native') return <Wrench className="size-3" />;
    if (cat === 'integration') return <Zap className="size-3" />;
    return <Sparkles className="size-3" />;
  };

  const categoryBadgeVariant = (cat: string): 'secondary' | 'outline' | 'default' => {
    if (cat === 'native') return 'secondary';
    if (cat === 'integration') return 'outline';
    return 'default';
  };

  return (
    <div className="flex gap-6 min-h-[25rem]">
      {/* Left: Available Tools */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm">Available Tools & Skills</h3>
          <span className="text-xs text-muted-foreground">{filteredTools.length} items</span>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 mb-3 p-1 bg-[var(--color-bg-secondary)] rounded-[var(--radius-sm)] w-fit">
          {(['all', 'native', 'integration', 'skill'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1 rounded-[var(--radius-sm)] text-xs transition-all capitalize",
                filter === f
                  ? "bg-[var(--color-bg-elevated)] text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f === 'all' ? 'All' : f === 'native' ? 'Native' : f === 'integration' ? 'Integrations' : 'Skills'}
            </button>
          ))}
        </div>

        {/* Tool List */}
        <div className="space-y-2 max-h-[28.125rem] overflow-y-auto pr-1">
          {filteredTools.map(tool => {
            const isEquipped = equippedToolIds.has(tool.id);
            const isDisconnected = tool.category === 'integration' && tool.connected === false;

            return (
              <button
                key={tool.id}
                onClick={() => toggleTool(tool.id)}
                className={cn(
                  "w-full flex items-start gap-3 p-3 rounded-[var(--radius-md)] border transition-all text-left",
                  isEquipped
                    ? "border-[var(--color-teal-500)] bg-[var(--color-teal-100)]"
                    : "border-[var(--color-border-default)] bg-card hover:border-[var(--color-border-strong)]"
                )}
                style={{
                  transitionTimingFunction: 'var(--ease-default)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-sm">{tool.name}</span>
                    <Badge variant={categoryBadgeVariant(tool.category)} className="text-[0.625rem] px-1.5 py-0 gap-1">
                      {categoryIcon(tool.category)}
                      {tool.category === 'native' ? 'Native' : tool.category === 'integration' ? 'Integration' : 'Skill'}
                    </Badge>
                    {isDisconnected && (
                      <Badge variant="outline" className="text-[0.625rem] px-1.5 py-0 gap-1 text-amber-600 border-amber-300">
                        <Link2Off className="size-3" />
                        Not Connected
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{tool.description}</p>
                </div>
                <div className="shrink-0 mt-1">
                  {isEquipped ? (
                    <div className="size-6 rounded-full bg-[var(--color-teal-500)] flex items-center justify-center">
                      <Check className="size-3.5 text-white" />
                    </div>
                  ) : (
                    <div className="size-6 rounded-full border-2 border-[var(--color-border-default)] flex items-center justify-center">
                      <Plus className="size-3 text-muted-foreground" />
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: Equipped Panel */}
      <div className="w-72 shrink-0">
        <div className="sticky top-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm">Equipped ({equipped.length})</h3>
          </div>
          <div className="p-4 rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] min-h-[12.5rem]">
            {equipped.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[11.25rem] text-center">
                <Info className="size-6 text-muted-foreground mb-2" />
                <p className="text-xs text-muted-foreground">
                  Click tools on the left to equip them to this agent.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {equipped.map(tool => (
                  <div
                    key={tool.id}
                    className="flex items-center gap-2 p-2 rounded-[var(--radius-sm)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)]"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs truncate">{tool.name}</p>
                      <Badge variant={categoryBadgeVariant(tool.category)} className="text-[0.5625rem] px-1 py-0 mt-0.5 gap-0.5">
                        {categoryIcon(tool.category)}
                        {tool.category}
                      </Badge>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleTool(tool.id); }}
                      className="shrink-0 size-5 rounded-full hover:bg-red-100 flex items-center justify-center text-muted-foreground hover:text-red-500 transition-colors"
                    >
                      <X className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Step 3: Review ───

function StepReview({
  name,
  description,
  model,
  instructions,
  equippedTools,
}: {
  name: string;
  description: string;
  model: typeof availableModels[number] | undefined;
  instructions: string;
  equippedTools: AgentTool[];
}) {
  const nativeTools = equippedTools.filter(t => t.category === 'native');
  const integrationTools = equippedTools.filter(t => t.category === 'integration');
  const skillToolsList = equippedTools.filter(t => t.category === 'skill');

  return (
    <div className="max-w-2xl space-y-6">
      {/* Summary Card */}
      <div className="p-6 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-card space-y-5">
        {/* Agent Identity */}
        <div className="flex items-start gap-4">
          <div
            className="size-12 rounded-[var(--radius-md)] bg-[var(--color-teal-500)] flex items-center justify-center shrink-0 rotate-2"
            style={{ boxShadow: 'var(--shadow-color-teal)' }}
          >
            <Bot className="size-6 text-[var(--color-text-inverse)]" />
          </div>
          <div>
            <h2 className="text-lg mb-0.5">{name || 'Untitled Agent'}</h2>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">
                {model?.icon} {model?.name ?? 'No model selected'}
              </Badge>
            </div>
          </div>
        </div>

        {/* Description */}
        {description && (
          <div>
            <Label className="text-xs text-muted-foreground mb-1 block">Description</Label>
            <p className="text-sm bg-[var(--color-bg-secondary)] p-3 rounded-[var(--radius-sm)] whitespace-pre-wrap">
              {description}
            </p>
          </div>
        )}

        {/* Instructions */}
        {instructions && (
          <div>
            <Label className="text-xs text-muted-foreground mb-1 block">Instructions</Label>
            <p className="text-sm bg-[var(--color-bg-secondary)] p-3 rounded-[var(--radius-sm)] whitespace-pre-wrap">
              {instructions}
            </p>
          </div>
        )}

        {/* Tools breakdown */}
        <div>
          <Label className="text-xs text-muted-foreground mb-2 block">
            Equipped Tools & Skills ({equippedTools.length})
          </Label>
          {equippedTools.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">No tools equipped. The agent will operate with model-only capabilities.</p>
          ) : (
            <div className="space-y-3">
              {nativeTools.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
                    <Wrench className="size-3" />
                    Native Tools ({nativeTools.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {nativeTools.map(t => (
                      <Badge key={t.id} variant="secondary">{t.name}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {integrationTools.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
                    <Zap className="size-3" />
                    Integrations ({integrationTools.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {integrationTools.map(t => (
                      <Badge key={t.id} variant="outline" className="gap-1">
                        {t.name}
                        {t.connected === false && (
                          <Link2Off className="size-3 text-amber-500" />
                        )}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {skillToolsList.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-[var(--color-violet-500)] mb-1.5">
                    <Sparkles className="size-3" />
                    Skills ({skillToolsList.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {skillToolsList.map(t => (
                      <Badge key={t.id} variant="default">{t.name}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Disconnected integrations warning */}
      {integrationTools.some(t => t.connected === false) && (
        <div className="flex items-start gap-3 p-4 rounded-[var(--radius-md)] bg-[var(--color-amber-100)] border border-[var(--color-amber-300)]">
          <Link2Off className="size-4 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-amber-800">
              Some integration tools are not connected yet. The agent will be created, but those tools
              won't function until you connect them in Settings.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
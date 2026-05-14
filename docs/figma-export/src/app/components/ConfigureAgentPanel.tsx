import { useState } from 'react';
import { Bot, ChevronDown, Plus, X } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { Agent, availableModels, availableTools } from '../data/mockData';
import type { AgentTool } from '../data/mockData';

interface ConfigureAgentPanelProps {
  agent: Agent;
  onClose: () => void;
}

export function ConfigureAgentPanel({ agent, onClose }: ConfigureAgentPanelProps) {
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState(agent.instructions);
  const [model, setModel] = useState(agent.model);
  const [selectedTools, setSelectedTools] = useState<string[]>(agent.tools.map(t => t.id));
  const [isActive, setIsActive] = useState(agent.status === 'active');

  const skillTools = availableTools.filter(t => t.category === 'skill');
  const nativeTools = availableTools.filter(t => t.category === 'native');

  const toggleTool = (toolId: string) => {
    setSelectedTools(prev =>
      prev.includes(toolId) ? prev.filter(id => id !== toolId) : [...prev, toolId]
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4 pr-12">
        <div className="flex items-center gap-3 mb-1">
          <div
            className="size-8 rounded-[var(--radius-md)] bg-[var(--color-teal-500)] flex items-center justify-center shrink-0"
            style={{ boxShadow: 'var(--shadow-color-teal)' }}
          >
            <Bot className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <h3 className="truncate">Configure Agent</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          Modify this agent's settings, skills, and tools.
        </p>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
        {/* Name */}
        <div>
          <Label htmlFor="agent-name">Name</Label>
          <Input
            id="agent-name"
            value={name}
            onChange={e => setName(e.target.value)}
            className="mt-1.5"
          />
        </div>

        {/* Description */}
        <div>
          <Label htmlFor="agent-description">Description</Label>
          <Input
            id="agent-description"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="A brief description of what this agent does"
            className="mt-1.5"
          />
        </div>

        {/* Instructions */}
        <div>
          <Label htmlFor="agent-instructions">Instructions</Label>
          <Textarea
            id="agent-instructions"
            value={instructions}
            onChange={e => setInstructions(e.target.value)}
            rows={8}
            className="mt-1.5 min-h-[10rem] resize-y"
          />
          <p className="text-xs text-muted-foreground mt-1.5">
            Tell the agent how to behave and what to focus on.
          </p>
        </div>

        <Separator />

        {/* Model */}
        <div>
          <Label>Model Tier</Label>
          <div className="grid grid-cols-3 gap-2 mt-1.5">
            {availableModels.map(m => (
              <button
                key={m.id}
                onClick={() => setModel(m.id)}
                className={`flex flex-col items-center p-3 rounded-[var(--radius-md)] border-2 transition-all text-center ${
                  model === m.id
                    ? 'border-[var(--color-violet-500)] bg-[var(--color-violet-100)]'
                    : 'border-[var(--color-border-default)] bg-card hover:border-[var(--color-border-strong)]'
                }`}
                style={{
                  transitionTimingFunction: 'var(--ease-bounce)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                <span className="text-base mb-1">{m.icon}</span>
                <span className="text-xs" style={{ fontWeight: 600 }}>{m.name}</span>
                {m.badge && (
                  <Badge variant="secondary" className="text-[0.5625rem] px-1 py-0 mt-1">
                    {m.badge}
                  </Badge>
                )}
              </button>
            ))}
          </div>
        </div>

        <Separator />

        {/* Skills & Tools Accordion */}
        <Accordion type="multiple" defaultValue={['skills', 'tools']}>
          <AccordionItem value="skills">
            <AccordionTrigger className="py-3">
              <div className="flex items-center gap-2">
                <span className="text-sm" style={{ fontWeight: 500 }}>Skills</span>
                <Badge variant="secondary" className="text-[0.625rem] px-1.5 py-0">
                  {selectedTools.filter(id => skillTools.some(s => s.id === id)).length}/{skillTools.length}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <p className="text-xs text-muted-foreground mb-2">
                Skills extend what this agent can do.
              </p>
              <div className="space-y-2">
                {skillTools.length > 0 ? skillTools.map(tool => (
                  <label
                    key={tool.id}
                    className="flex items-center gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)] cursor-pointer hover:bg-muted/80 transition-colors"
                  >
                    <Checkbox
                      checked={selectedTools.includes(tool.id)}
                      onCheckedChange={() => toggleTool(tool.id)}
                    />
                    <div className="min-w-0">
                      <p className="text-sm truncate">{tool.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
                    </div>
                  </label>
                )) : (
                  <p className="text-xs text-muted-foreground py-2">No skills available. Create skills in the Skills tab.</p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="tools">
            <AccordionTrigger className="py-3">
              <div className="flex items-center gap-2">
                <span className="text-sm" style={{ fontWeight: 500 }}>Tools</span>
                <Badge variant="secondary" className="text-[0.625rem] px-1.5 py-0">
                  {selectedTools.filter(id => nativeTools.some(n => n.id === id)).length}/{nativeTools.length}
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <p className="text-xs text-muted-foreground mb-2">
                Native tools the agent can use.
              </p>
              <div className="space-y-2">
                {nativeTools.map(tool => (
                  <label
                    key={tool.id}
                    className="flex items-center gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)] cursor-pointer hover:bg-muted/80 transition-colors"
                  >
                    <Checkbox
                      checked={selectedTools.includes(tool.id)}
                      onCheckedChange={() => toggleTool(tool.id)}
                    />
                    <div className="min-w-0">
                      <p className="text-sm truncate">{tool.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 p-4 border-t border-[var(--color-border-default)]">
        <Button
          variant="outline"
          size="sm"
          className={isActive
            ? 'text-[var(--color-error-text)] border-[var(--color-error-text)] hover:bg-[var(--color-error-bg)]'
            : 'text-[var(--color-success-text)] border-[var(--color-success-text)] hover:bg-[var(--color-success-bg)]'
          }
          onClick={() => setIsActive(!isActive)}
        >
          {isActive ? 'Deactivate' : 'Activate'}
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={onClose}>
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
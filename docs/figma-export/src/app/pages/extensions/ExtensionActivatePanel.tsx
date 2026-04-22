import { useState } from 'react';
import { useNavigate } from 'react-router';
import { X, Check, ChevronRight, ChevronLeft } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { useExtensions } from '../../contexts/ExtensionsContext';
import { availableTools } from '../../data/mockData';
import type { ExtensionDefinition } from '../../data/extensionRegistry';

interface Props {
  extension: ExtensionDefinition;
  onClose: () => void;
}

export function ExtensionActivatePanel({ extension, onClose }: Props) {
  const { activateExtension } = useExtensions();
  const navigate = useNavigate();
  const hasConfig = extension.configSteps.length > 0;
  const [currentStep, setCurrentStep] = useState(0);
  const [config, setConfig] = useState<Record<string, unknown>>({});

  const totalSteps = extension.configSteps.length + 1; // config steps + confirmation

  const handleActivate = () => {
    activateExtension(extension.id, config);
    onClose();
    navigate(`/extensions/${extension.slug}`);
  };

  const isConfirmationStep = hasConfig ? currentStep === extension.configSteps.length : true;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="relative bg-[var(--color-bg-elevated)] rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] shadow-xl w-full max-w-lg mx-4 max-h-[80vh] overflow-auto">
        {/* Header */}
        <div className="p-5 border-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`size-9 rounded-[var(--radius-md)] flex items-center justify-center ${extension.rotation}`}
              style={{ backgroundColor: extension.color, boxShadow: extension.shadow }}
            >
              <extension.icon className="size-4 text-[var(--color-text-inverse)]" />
            </div>
            <div>
              <h2 className="text-sm">Activate {extension.name}</h2>
              {hasConfig && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  Step {currentStep + 1} of {totalSteps}
                </p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {hasConfig && !isConfirmationStep ? (
            <ConfigStepContent
              stepId={extension.configSteps[currentStep].id}
              step={extension.configSteps[currentStep]}
              config={config}
              onConfigChange={setConfig}
            />
          ) : (
            <ConfirmationContent extension={extension} config={config} />
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t flex items-center justify-between">
          {hasConfig && currentStep > 0 ? (
            <Button variant="outline" size="sm" className="gap-1" onClick={() => setCurrentStep((s) => s - 1)}>
              <ChevronLeft className="size-3" />
              Back
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
          )}

          {isConfirmationStep ? (
            <Button size="sm" className="gap-1" onClick={handleActivate}>
              <Check className="size-3" />
              Activate Extension
            </Button>
          ) : (
            <Button size="sm" className="gap-1" onClick={() => setCurrentStep((s) => s + 1)}>
              Next
              <ChevronRight className="size-3" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function ConfirmationContent({
  extension,
  config,
}: {
  extension: ExtensionDefinition;
  config: Record<string, unknown>;
}) {
  const selectedSources = (config['data-sources'] as string[] | undefined) || [];

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{extension.longDescription}</p>

      {selectedSources.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground mb-2">Selected data sources:</p>
          <div className="flex flex-wrap gap-1.5">
            {selectedSources.map((id) => {
              const tool = availableTools.find((t) => t.id === id);
              return (
                <Badge key={id} variant="secondary">
                  {tool?.name || id}
                </Badge>
              );
            })}
          </div>
        </div>
      )}

      <div className="p-3 rounded-[var(--radius-md)] bg-violet-500/5 border border-violet-500/20">
        <p className="text-xs text-muted-foreground">
          This will add <span className="text-foreground">{extension.name}</span> to your Extensions menu.
          You can deactivate it at any time.
        </p>
      </div>
    </div>
  );
}

function ConfigStepContent({
  stepId,
  step,
  config,
  onConfigChange,
}: {
  stepId: string;
  step: { title: string; description: string };
  config: Record<string, unknown>;
  onConfigChange: (c: Record<string, unknown>) => void;
}) {
  // For now, only the "data-sources" step exists
  if (stepId === 'data-sources') {
    return <DataSourcesStep config={config} onConfigChange={onConfigChange} step={step} />;
  }

  return (
    <div>
      <h3 className="text-sm mb-1">{step.title}</h3>
      <p className="text-xs text-muted-foreground">{step.description}</p>
    </div>
  );
}

function DataSourcesStep({
  config,
  onConfigChange,
  step,
}: {
  config: Record<string, unknown>;
  onConfigChange: (c: Record<string, unknown>) => void;
  step: { title: string; description: string };
}) {
  const integrationTools = availableTools.filter((t) => t.category === 'integration');
  const selected = (config['data-sources'] as string[] | undefined) || [];

  const toggle = (toolId: string) => {
    const next = selected.includes(toolId)
      ? selected.filter((id) => id !== toolId)
      : [...selected, toolId];
    onConfigChange({ ...config, 'data-sources': next });
  };

  return (
    <div>
      <h3 className="text-sm mb-1">{step.title}</h3>
      <p className="text-xs text-muted-foreground mb-4">{step.description}</p>

      <div className="space-y-2">
        {integrationTools.map((tool) => {
          const isSelected = selected.includes(tool.id);
          return (
            <button
              key={tool.id}
              onClick={() => toggle(tool.id)}
              className={`w-full flex items-center gap-3 p-3 rounded-[var(--radius-md)] border-2 transition-all text-left ${
                isSelected
                  ? 'border-[var(--color-violet-500)] bg-violet-500/5'
                  : 'border-[var(--color-border-default)] hover:border-[var(--color-border-strong)]'
              }`}
            >
              <div
                className={`size-5 rounded-[var(--radius-sm)] border-2 flex items-center justify-center transition-colors ${
                  isSelected
                    ? 'bg-[var(--color-violet-500)] border-[var(--color-violet-500)]'
                    : 'border-[var(--color-border-default)]'
                }`}
              >
                {isSelected && <Check className="size-3 text-white" />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm">{tool.name}</p>
                <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
              </div>
              {tool.connected && (
                <Badge variant="secondary" className="shrink-0">
                  Connected
                </Badge>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

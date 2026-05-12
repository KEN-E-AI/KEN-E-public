import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Bot } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  useAgentConfig,
  useUpsertAgentConfigOverlay,
  useDeleteAgentConfig,
} from "@/queries/agentConfigs";
import type {
  AgentConfigId,
  AgentConfigOverlayUpdate,
} from "@/lib/api/agentConfigs";
import { SUPPORTED_MODELS } from "@/lib/api/agentConfigs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DisabledPlaceholderRow } from "./DisabledPlaceholderRow";

// ─── Customization badge (reused from list) ───────────────────────────────────

const STATUS_LABELS = {
  default: "Default",
  customized: "Customized",
  custom_agent: "Custom Agent",
} as const;

const STATUS_CLASSES = {
  default: "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]",
  customized: "bg-[var(--color-violet-100)] text-[var(--color-violet-500)]",
  custom_agent: "bg-[var(--color-teal-100)] text-[var(--color-teal-500)]",
} as const;

// ─── Dot indicator for dirty fields ──────────────────────────────────────────

function DirtyDot({ dirty }: { dirty: boolean }) {
  if (!dirty) return null;
  return (
    <span
      className="inline-block size-1.5 rounded-full bg-[var(--color-violet-500)] ml-1"
      aria-label="field modified"
      data-testid="dirty-indicator"
    />
  );
}

// ─── AgentEditView ────────────────────────────────────────────────────────────

export type AgentEditViewProps = {
  configId: AgentConfigId;
  onClose: () => void;
};

export function AgentEditView({ configId, onClose }: AgentEditViewProps) {
  const { selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;

  const {
    data: config,
    isLoading,
    isError,
  } = useAgentConfig(accountId, configId);
  const upsertMutation = useUpsertAgentConfigOverlay(accountId);
  const deleteMutation = useDeleteAgentConfig(accountId);

  // Form state (initialised from loaded config)
  const [instruction, setInstruction] = useState("");
  const [temperature, setTemperature] = useState<number>(0.3);
  const [model, setModel] = useState("");
  const [description, setDescription] = useState("");

  // Seed local state once config is loaded
  useEffect(() => {
    if (!config) return;
    setInstruction(config.instruction);
    setTemperature(config.temperature ?? 0.3);
    setModel(config.model);
    setDescription(config.description ?? "");
  }, [config]);

  if (isLoading) {
    return (
      <div className="flex flex-col h-full p-6 gap-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (isError || !config) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <Bot className="size-8 text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">
          Failed to load agent configuration.
        </p>
        <Button variant="ghost" size="sm" className="mt-3" onClick={onClose}>
          Close
        </Button>
      </div>
    );
  }

  // Per-field dirty detection (compared to loaded config values)
  const isDirtyInstruction = instruction !== config.instruction;
  const isDirtyTemperature = temperature !== (config.temperature ?? 0.3);
  const isDirtyModel = model !== config.model;
  const isDirtyDescription = description !== (config.description ?? "");
  const hasAnyDirty =
    isDirtyInstruction ||
    isDirtyTemperature ||
    isDirtyModel ||
    isDirtyDescription;

  const isCustomAgent = config.customization_status === "custom_agent";
  const isDefault = config.customization_status === "default";

  const revertLabel = isCustomAgent ? "Delete agent" : "Revert to default";

  function handleSave() {
    const dirty: AgentConfigOverlayUpdate = {};
    if (isDirtyInstruction) dirty.instruction = instruction;
    if (isDirtyTemperature) dirty.temperature = temperature;
    if (isDirtyModel) dirty.model = model;
    if (isDirtyDescription) dirty.description = description || null;

    upsertMutation.mutate(
      { configId, body: dirty },
      {
        onSuccess: () => {
          toast.success("Agent updated.");
          onClose();
        },
        onError: () => {
          toast.error("Failed to save changes.");
        },
      },
    );
  }

  function handleRevert() {
    deleteMutation.mutate(
      { configId },
      {
        onSuccess: () => {
          toast.success(
            isCustomAgent ? "Agent deleted." : "Reverted to default.",
          );
          onClose();
        },
        onError: () => {
          toast.error("Failed to revert.");
        },
      },
    );
  }

  const displayName =
    config.name ??
    config.config_id
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4 pr-12">
        <div className="flex items-center gap-3 mb-1">
          <div
            className="size-8 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center shrink-0"
            style={{ boxShadow: "var(--shadow-color-violet)" }}
          >
            <Bot className="size-4 text-[var(--color-text-inverse)]" />
          </div>
          <h3 className="truncate">{displayName}</h3>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] ${STATUS_CLASSES[config.customization_status]}`}
            style={{ fontWeight: 700 }}
            data-testid="customization-status-badge"
          >
            {STATUS_LABELS[config.customization_status]}
          </span>
          {config.based_on_version != null && (
            <span
              // allow-text-tertiary: secondary-metadata version pill
              className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
              style={{ fontWeight: 600 }}
              data-testid="based-on-version-chip"
            >
              v{config.based_on_version}
            </span>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 pb-4 space-y-5">
        {/* Instruction */}
        <div>
          <Label htmlFor="agent-instruction" className="flex items-center">
            Instruction
            <DirtyDot dirty={isDirtyInstruction} />
          </Label>
          <Textarea
            id="agent-instruction"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={8}
            className="mt-1.5 min-h-[160px] resize-y"
            data-testid="instruction-field"
          />
        </div>

        {/* Response style (stored as `temperature`) */}
        <div>
          {/* allow-text-tertiary: secondary-metadata slider value readout */}
          <div className="flex justify-end items-center text-[11px] text-[var(--color-text-tertiary)]">
            <DirtyDot dirty={isDirtyTemperature} />
            <span>{temperature.toFixed(2)}</span>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[12px] text-[var(--color-text-secondary)]">
              Precise
            </span>
            <Slider
              id="agent-temperature"
              aria-label="Response style: precise to creative"
              min={0}
              max={1}
              step={0.01}
              value={[temperature]}
              onValueChange={([val]) => setTemperature(val)}
              className="flex-1"
              data-testid="temperature-slider"
            />
            <span className="text-[12px] text-[var(--color-text-secondary)]">
              Creative
            </span>
          </div>
        </div>

        {/* Model */}
        <div>
          <Label htmlFor="agent-model" className="flex items-center">
            Model
            <DirtyDot dirty={isDirtyModel} />
          </Label>
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger
              id="agent-model"
              className="mt-1.5"
              data-testid="model-select"
            >
              <SelectValue placeholder="Select a model" />
            </SelectTrigger>
            <SelectContent>
              {SUPPORTED_MODELS.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Description */}
        <div>
          <Label htmlFor="agent-description" className="flex items-center">
            Description
            <DirtyDot dirty={isDirtyDescription} />
          </Label>
          <Textarea
            id="agent-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="A brief description of what this agent does"
            className="mt-1.5"
            data-testid="description-field"
          />
        </div>

        <Separator />

        {/* Disabled placeholder rows */}
        <div className="space-y-2">
          <DisabledPlaceholderRow label="Skills" />
          <DisabledPlaceholderRow label="Sandbox code execution" />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 p-4 border-t border-[var(--color-border-default)]">
        {!isDefault && (
          <Button
            variant="outline"
            size="sm"
            className="text-[var(--color-error-text)] border-[var(--color-error-text)] hover:bg-[var(--color-error-bg)]"
            onClick={handleRevert}
            disabled={!accountId || deleteMutation.isPending}
            data-testid="revert-button"
          >
            {revertLabel}
          </Button>
        )}
        {isDefault && <span />}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            disabled={upsertMutation.isPending || deleteMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!accountId || !hasAnyDirty || upsertMutation.isPending}
            data-testid="save-button"
          >
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}

export default AgentEditView;

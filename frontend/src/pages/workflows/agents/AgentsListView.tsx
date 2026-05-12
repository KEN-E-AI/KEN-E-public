import { useNavigate } from "react-router-dom";
import { Bot, Plus, Settings } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useAgentConfigsList } from "@/queries/agentConfigs";
import type { AgentConfigId } from "@/lib/api/agentConfigs";
import { toAgentConfigId } from "@/lib/api/agentConfigs";
import type {
  MergedAgentConfig,
  CustomizationStatus,
} from "@/lib/api/agentConfigs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ─── Accent palette (matches Figma FALLBACK_ACCENTS) ─────────────────────────

const FALLBACK_ACCENTS = [
  {
    accent: "var(--color-blue-500)",
    shadow: "0 4px 12px rgba(59,130,246,0.25)",
  },
  {
    accent: "var(--color-amber-500)",
    shadow: "0 4px 12px rgba(245,158,11,0.25)",
  },
  {
    accent: "var(--color-violet-500)",
    shadow: "0 4px 12px rgba(139,92,246,0.25)",
  },
  {
    accent: "var(--color-teal-500)",
    shadow: "0 4px 12px rgba(20,184,166,0.25)",
  },
];

// ─── Customization badge ──────────────────────────────────────────────────────

const STATUS_LABELS: Record<CustomizationStatus, string> = {
  default: "Default",
  customized: "Customized",
  custom_agent: "Custom Agent",
};

const STATUS_CLASSES: Record<CustomizationStatus, string> = {
  default: "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]",
  customized: "bg-[var(--color-violet-100)] text-[var(--color-violet-500)]",
  custom_agent: "bg-[var(--color-teal-100)] text-[var(--color-teal-500)]",
};

function CustomizationBadge({ status }: { status: CustomizationStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] ${STATUS_CLASSES[status]}`}
      style={{ fontWeight: 700 }}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

// ─── Agent card ───────────────────────────────────────────────────────────────

type AgentCardProps = {
  config: MergedAgentConfig;
  index: number;
  onEdit: (configId: AgentConfigId) => void;
};

function AgentCard({ config, index, onEdit }: AgentCardProps) {
  const accentStyle = FALLBACK_ACCENTS[index % FALLBACK_ACCENTS.length];
  const displayName =
    config.name ??
    config.config_id
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      className="relative p-4 rounded-[14px] border-2 border-[var(--color-border-default)] hover:border-[var(--color-border-strong)] hover:-translate-y-0.5 transition-all cursor-pointer bg-card overflow-hidden flex flex-col"
      style={{
        transitionTimingFunction: "var(--ease-bounce)",
        transitionDuration: "var(--duration-fast)",
      }}
      onClick={() => onEdit(toAgentConfigId(config.config_id))}
      data-testid={`agent-card-${config.config_id}`}
    >
      {/* Configure gear (top-right) */}
      <button
        type="button"
        className="absolute top-3 right-3 size-7 rounded-[var(--radius-sm)] flex items-center justify-center text-[var(--color-text-secondary)] cursor-pointer transition-colors hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-violet-500)]"
        onClick={(e) => {
          e.stopPropagation();
          onEdit(toAgentConfigId(config.config_id));
        }}
        aria-label={`Configure ${displayName}`}
      >
        <Settings className="size-4" />
      </button>

      {/* Icon */}
      <div className="mb-3">
        <div
          className="size-11 rounded-xl flex items-center justify-center"
          style={{
            background: accentStyle.accent,
            boxShadow: accentStyle.shadow,
          }}
        >
          <Bot className="size-5 text-white" />
        </div>
      </div>

      {/* Name + customization badge */}
      <div
        className="flex items-center gap-1.5 flex-wrap mb-1.5 pr-8"
        style={{ minHeight: 22 }}
      >
        <span
          className="text-[13px]"
          style={{ fontWeight: 700, lineHeight: 1.25 }}
        >
          {displayName}
        </span>
        <CustomizationBadge status={config.customization_status} />
      </div>

      {/* Model */}
      {/* allow-text-tertiary: secondary-metadata model identifier under agent name */}
      <div className="flex items-center gap-1 text-[11px] text-[var(--color-text-tertiary)] mb-2.5">
        {config.model}
      </div>

      {/* Description */}
      {config.description && (
        <p className="text-[12px] text-[var(--color-text-secondary)] line-clamp-2">
          {config.description}
        </p>
      )}
    </div>
  );
}

// ─── Skeleton loading cards ───────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="p-4 rounded-[14px] border-2 border-[var(--color-border-default)] bg-card flex flex-col gap-3">
      <Skeleton className="size-11 rounded-xl" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

// ─── AgentsListView ───────────────────────────────────────────────────────────

export type AgentsListViewProps = {
  onEdit: (configId: AgentConfigId) => void;
};

export function AgentsListView({ onEdit }: AgentsListViewProps) {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;

  const {
    data: configs,
    isLoading,
    isError,
  } = useAgentConfigsList(accountId, {
    visibleInFrontend: true,
  });

  if (!accountId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
        <Bot className="size-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          Select an account to view agents.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="px-6 pb-6">
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns:
              "repeat(auto-fill, minmax(min(100%, 280px), 1fr))",
          }}
        >
          {Array.from({ length: 3 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
        <Bot className="size-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          Failed to load agents. Please try again.
        </p>
      </div>
    );
  }

  const isEmpty = !configs || configs.length === 0;

  return (
    <div className="px-6 pb-6">
      {/* Action row — always visible above the grid / empty state. */}
      <div className="flex justify-end mb-4">
        <Button
          onClick={() => navigate("/workflows/agents/new")}
          className="gap-2"
          data-testid="new-agent-button"
        >
          <Plus className="size-4" />
          New Agent
        </Button>
      </div>

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] text-center">
          <Bot className="size-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground mb-1">
            Assemble specialist agents tailored to your workflow.
          </p>
          <p className="text-xs text-muted-foreground mb-4">
            Create an agent to get started with AI-powered workflows.
          </p>
          <button
            className="px-4 py-2 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] text-white text-sm cursor-pointer hover:opacity-90 transition-opacity"
            style={{ fontWeight: 600 }}
            onClick={() => navigate("/workflows/agents/new")}
          >
            Create an agent
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {configs.map((config, idx) => (
            <AgentCard
              key={config.config_id}
              config={config}
              index={idx}
              onEdit={onEdit}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default AgentsListView;

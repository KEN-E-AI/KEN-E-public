import { useMemo, useState } from "react";
import { AlertCircle, Search } from "lucide-react";
import type { AccountToolEntry } from "@/lib/api/tools";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

// ─── AgentToolPicker (AH-PRD-06 §B2) ─────────────────────────────────────────
//
// Presentational. The parent owns the ``useAccountTools`` query so the same
// inventory can drive Create + Edit forms (and so this component is trivially
// testable with a static ``tools`` prop).

const BUILT_IN_GROUP_KEY = "__builtin__";

type Group = {
  /** Stable key — ``mcp_server`` for integration tools, sentinel for built-ins. */
  key: string;
  /** User-visible label — humanized integration platform or "Built-in". */
  label: string;
  source: "global_default" | "integration";
  tools: AccountToolEntry[];
};

export type AgentToolPickerProps = {
  /** The agent's currently-selected tool IDs (controlled). */
  value: string[];
  onChange: (next: string[]) => void;
  /** Inventory from ``useAccountTools``. */
  tools: AccountToolEntry[] | undefined;
  isLoading: boolean;
  isError: boolean;
  /** Optional id used to associate the section heading with an external label. */
  id?: string;
};

export function AgentToolPicker({
  value,
  onChange,
  tools,
  isLoading,
  isError,
  id = "agent-tool-picker",
}: AgentToolPickerProps) {
  const [search, setSearch] = useState("");

  const selectedSet = useMemo(() => new Set(value), [value]);

  // Group every tool by (source, mcp_server). Built-ins coalesce into one
  // synthetic group; integration tools split by their mcp_server. Group
  // labels humanise the integration platform — that's what users connected
  // on the Account Settings page, so it matches their mental model.
  const allGroups = useMemo<Group[]>(() => groupTools(tools ?? []), [tools]);

  const filteredGroups = useMemo<Group[]>(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allGroups;
    return allGroups
      .map((g) => ({
        ...g,
        tools: g.tools.filter(
          (t) =>
            t.name.toLowerCase().includes(q) ||
            t.description.toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.tools.length > 0);
  }, [allGroups, search]);

  const totalAvailable = useMemo(() => (tools ?? []).length, [tools]);
  const totalSelected = useMemo(
    () => (tools ?? []).filter((t) => selectedSet.has(t.tool_id)).length,
    [tools, selectedSet],
  );

  function toggle(toolId: string) {
    if (selectedSet.has(toolId)) {
      onChange(value.filter((v) => v !== toolId));
    } else {
      onChange([...value, toolId]);
    }
  }

  function toggleGroup(group: Group, select: boolean) {
    const groupIds = new Set(group.tools.map((t) => t.tool_id));
    if (select) {
      // Append any not-yet-selected tools from this group, preserving the
      // existing selection order so the payload is stable across saves.
      const additions = group.tools
        .filter((t) => !selectedSet.has(t.tool_id))
        .map((t) => t.tool_id);
      if (additions.length === 0) return;
      onChange([...value, ...additions]);
    } else {
      onChange(value.filter((v) => !groupIds.has(v)));
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="tool-picker-loading">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="flex items-center gap-2 p-3 rounded-[var(--radius-md)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]"
        role="alert"
        data-testid="tool-picker-error"
      >
        <AlertCircle className="size-4 shrink-0" />
        <span className="text-sm">Failed to load tools.</span>
      </div>
    );
  }

  return (
    <div className="space-y-2" aria-labelledby={`${id}-label`}>
      <div className="flex items-center justify-between">
        {/* Rendered as h2 so the picker's Accordion triggers (which Radix
            renders as <h3>) form a valid heading hierarchy under any page
            with an <h1> (e.g. AgentCreatePage). Without this, axe flags
            "Heading levels should only increase by one." */}
        <h2 id={`${id}-label`} className="text-sm font-medium m-0">
          Tools
        </h2>
        <span
          className="text-xs text-[var(--color-text-secondary)]"
          data-testid="tool-picker-summary"
        >
          {totalSelected} of {totalAvailable} selected
        </span>
      </div>

      <div className="relative">
        {/* allow-text-tertiary: decorative leading-icon in a search input (accessible name on the <Input aria-label> below) */}
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-tertiary)] pointer-events-none" />
        <Input
          aria-label="Search tools"
          placeholder="Search tools..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
          data-testid="tool-picker-search"
        />
      </div>

      {totalAvailable === 0 ? (
        <div
          className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] text-sm text-[var(--color-text-secondary)]"
          data-testid="tool-picker-empty-inventory"
        >
          No tools available. Connect an integration on{" "}
          <a
            href="/settings/account"
            className="underline text-[var(--color-violet-500)]"
          >
            Account Settings
          </a>{" "}
          to unlock more.
        </div>
      ) : filteredGroups.length === 0 ? (
        <div
          className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] text-sm text-[var(--color-text-secondary)]"
          data-testid="tool-picker-no-results"
        >
          No tools match your search.
        </div>
      ) : (
        <Accordion
          type="multiple"
          defaultValue={allGroups.map((g) => g.key)}
          className="w-full"
        >
          {filteredGroups.map((group) => {
            const selectedInGroup = group.tools.filter((t) =>
              selectedSet.has(t.tool_id),
            ).length;
            const allInGroupSelected =
              group.tools.length > 0 && selectedInGroup === group.tools.length;
            return (
              <AccordionItem
                key={group.key}
                value={group.key}
                data-testid={`tool-picker-group-${group.key}`}
              >
                <AccordionTrigger className="text-left">
                  <span className="flex-1">{group.label}</span>
                  <span
                    className="text-xs text-[var(--color-text-secondary)] ml-2 font-normal"
                    data-testid={`tool-picker-group-count-${group.key}`}
                  >
                    {selectedInGroup} / {group.tools.length}
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-xs text-[var(--color-violet-500)] hover:text-[var(--color-violet-700)] -ml-2"
                      onClick={() => toggleGroup(group, !allInGroupSelected)}
                      data-testid={`tool-picker-group-select-all-${group.key}`}
                    >
                      {allInGroupSelected ? "Deselect all" : "Select all"}
                    </Button>
                    <div className="space-y-2">
                      {group.tools.map((tool) => {
                        const checked = selectedSet.has(tool.tool_id);
                        return (
                          <label
                            key={tool.tool_id}
                            className="flex items-start gap-3 p-2 rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                            data-testid={`tool-picker-tool-${tool.tool_id}`}
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={() => toggle(tool.tool_id)}
                              aria-label={tool.name}
                              data-testid={`tool-picker-checkbox-${tool.tool_id}`}
                            />
                            <div className="min-w-0">
                              <div className="text-sm text-[var(--color-text-primary)]">
                                {tool.name}
                              </div>
                              {tool.description && (
                                <div className="text-xs text-[var(--color-text-secondary)] mt-0.5">
                                  {tool.description}
                                </div>
                              )}
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      )}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function groupTools(tools: AccountToolEntry[]): Group[] {
  // Two-pass grouping: collect into a map keyed by ``mcp_server`` (or the
  // built-in sentinel), then emit groups in a stable order — built-ins first,
  // then integrations alphabetised by their display label. Stable order keeps
  // the picker visually consistent regardless of the response's order.
  const byKey = new Map<string, Group>();
  for (const tool of tools) {
    if (tool.source === "global_default") {
      const existing = byKey.get(BUILT_IN_GROUP_KEY);
      if (existing) {
        existing.tools.push(tool);
      } else {
        byKey.set(BUILT_IN_GROUP_KEY, {
          key: BUILT_IN_GROUP_KEY,
          label: "Built-in",
          source: "global_default",
          tools: [tool],
        });
      }
      continue;
    }
    const key = tool.mcp_server ?? "unknown";
    const existing = byKey.get(key);
    if (existing) {
      existing.tools.push(tool);
    } else {
      byKey.set(key, {
        key,
        label: humanizePlatform(tool.integration_platform ?? key),
        source: "integration",
        tools: [tool],
      });
    }
  }
  const builtIn = byKey.get(BUILT_IN_GROUP_KEY);
  const integrations = [...byKey.values()]
    .filter((g) => g.key !== BUILT_IN_GROUP_KEY)
    .sort((a, b) => a.label.localeCompare(b.label));
  return builtIn ? [builtIn, ...integrations] : integrations;
}

function humanizePlatform(slug: string): string {
  return slug
    .split(/[_-]/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default AgentToolPicker;

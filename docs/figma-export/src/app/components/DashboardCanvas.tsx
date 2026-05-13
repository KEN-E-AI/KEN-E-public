import { useCallback, useMemo, useRef, useState, useEffect } from 'react';
import { FileText, Image as ImageIcon, Table as TableIcon, Code2, Unplug, Plus, X, Clock, BarChart3, Copy, Settings2 } from 'lucide-react';
import type { AutomationTask, OutputFile, OutputFileType } from '../data/automationDetailsData';
import { FILE_TYPE_LABELS } from '../data/automationDetailsData';
import { ArtifactRenderer } from './dashboard/ArtifactRenderer';
import { toArtifactPayload } from './dashboard/artifactTypes';
import { TileSettingsPopover } from './dashboard/TileSettingsPopover';

// ─── Types ───

export type ArtifactStatus = 'fresh' | 'stale' | 'disconnected' | 'pending';

export interface DashboardArtifact {
  key: string;              // `${nodeId}:${fileType}`
  nodeId: string;           // task_id
  fileType: OutputFileType;
  label: string;            // last known task title
  latestFile: OutputFile | null;
  updatedAt: Date | null;
  status: ArtifactStatus;
}

export type ViewType = 'bar' | 'line' | 'area' | 'point' | 'arc' | 'table';

export interface Placement {
  id: string;
  nodeId: string;
  fileType: OutputFileType;
  viewOverride?: ViewType;
  color?: string;
  showDataLabels?: boolean;
  x: number;
  y: number;
  w: number;
  h: number;
}

export function artifactKey(nodeId: string, fileType: OutputFileType): string {
  return `${nodeId}:${fileType}`;
}

// ─── Derive artifacts from tasks ───
// Terminal tasks (no-one depends on them) with output_config.enabled produce one artifact
// per expected_file_type.
export function useDashboardArtifacts(
  tasks: AutomationTask[],
  placements: Placement[],
  lastRunAt: Date | null
): Record<string, DashboardArtifact> {
  return useMemo(() => {
    const incoming = new Set<string>();
    tasks.forEach((t) => t.depends_on.forEach((d) => incoming.add(d)));
    const tasksById = new Map(tasks.map((t) => [t.task_id, t]));

    const result: Record<string, DashboardArtifact> = {};

    for (const t of tasks) {
      const isTerminal = !incoming.has(t.task_id);
      if (!isTerminal || !t.output_config?.enabled) continue;

      const latestRun = t.run_outputs[0] ?? null;

      for (const ft of t.output_config.expected_file_types) {
        const file = latestRun?.outputs.find((o) => o.file_type === ft) ?? null;
        const key = artifactKey(t.task_id, ft);
        result[key] = {
          key,
          nodeId: t.task_id,
          fileType: ft,
          label: t.title,
          latestFile: file,
          updatedAt: file?.created_at ?? latestRun?.run_timestamp ?? null,
          status: file ? 'fresh' : 'pending',
        };
      }
    }

    // Placements whose (task, fileType) pair is no longer produced → disconnected
    for (const p of placements) {
      const key = artifactKey(p.nodeId, p.fileType);
      if (result[key]) continue;
      const task = tasksById.get(p.nodeId);
      const stillProduces =
        task?.output_config?.enabled && task.output_config.expected_file_types.includes(p.fileType);
      if (!stillProduces) {
        result[key] = {
          key,
          nodeId: p.nodeId,
          fileType: p.fileType,
          label: task?.title ?? 'Removed task',
          latestFile: null,
          updatedAt: null,
          status: 'disconnected',
        };
      }
    }

    if (lastRunAt) {
      for (const a of Object.values(result)) {
        if (a.status === 'fresh' && a.updatedAt && a.updatedAt.getTime() < lastRunAt.getTime() - 1000) {
          a.status = 'stale';
        }
      }
    }

    return result;
  }, [tasks, placements, lastRunAt]);
}

// ─── Canvas ───

interface DashboardCanvasProps {
  tasks: AutomationTask[];
  placements: Placement[];
  onPlacementsChange: (next: Placement[]) => void;
  lastRunAt: Date | null;
}

const TILE_MIN_W = 200;
const TILE_MIN_H = 140;
const GRID = 8;

function snap(n: number) { return Math.round(n / GRID) * GRID; }

export function DashboardCanvas({ tasks, placements, onPlacementsChange, lastRunAt }: DashboardCanvasProps) {
  const artifacts = useDashboardArtifacts(tasks, placements, lastRunAt);
  const placedKeys = useMemo(
    () => new Set(placements.map((p) => artifactKey(p.nodeId, p.fileType))),
    [placements]
  );

  const available = useMemo(
    () => Object.values(artifacts).filter((a) => a.status !== 'disconnected' && !placedKeys.has(a.key)),
    [artifacts, placedKeys]
  );

  const canvasRef = useRef<HTMLDivElement | null>(null);

  const addPlacement = useCallback(
    (nodeId: string, fileType: OutputFileType) => {
      const id = `pl-${nodeId}-${fileType}-${Date.now()}`;
      const existing = placements.length;
      const pos = { x: 16 + (existing % 3) * 280, y: 16 + Math.floor(existing / 3) * 220 };
      onPlacementsChange([
        ...placements,
        { id, nodeId, fileType, x: pos.x, y: pos.y, w: 260, h: 200 },
      ]);
    },
    [placements, onPlacementsChange]
  );

  const updatePlacement = useCallback(
    (id: string, patch: Partial<Placement>) => {
      onPlacementsChange(placements.map((p) => (p.id === id ? { ...p, ...patch } : p)));
    },
    [placements, onPlacementsChange]
  );

  const removePlacement = useCallback(
    (id: string) => {
      onPlacementsChange(placements.filter((p) => p.id !== id));
    },
    [placements, onPlacementsChange]
  );

  const duplicatePlacement = useCallback(
    (id: string) => {
      const src = placements.find((p) => p.id === id);
      if (!src) return;
      const copy: Placement = {
        ...src,
        id: `pl-${src.nodeId}-${src.fileType}-${Date.now()}`,
        x: src.x + 24,
        y: src.y + 24,
      };
      onPlacementsChange([...placements, copy]);
    },
    [placements, onPlacementsChange]
  );

  return (
    <div className="flex flex-col h-full min-h-0 border-t border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]">
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-[var(--color-border-default)] bg-card">
        <span className="text-xs text-[var(--color-text-secondary)]">Dashboard canvas</span>
        <span className="text-[0.625rem] text-[var(--color-text-tertiary)]">
          {placements.length} placed · {available.length} unplaced
        </span>
      </div>

      <div
        ref={canvasRef}
        className="relative flex-1 overflow-auto"
        style={{
          backgroundImage:
            'radial-gradient(circle, var(--color-border-default) 1px, transparent 1px)',
          backgroundSize: '16px 16px',
        }}
      >
        {placements.length === 0 && available.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-xs text-[var(--color-text-tertiary)]">
              Terminal-task artifacts will appear here as they become available
            </p>
          </div>
        )}

        {available.map((a, i) => {
          const col = i % 3;
          const row = Math.floor(i / 3);
          return (
            <GhostPlaceholder
              key={`ghost-${a.key}`}
              artifact={a}
              x={16 + col * 280}
              y={16 + (Math.ceil(placements.length / 3) + row) * 220}
              onAdd={() => addPlacement(a.nodeId, a.fileType)}
            />
          );
        })}

        {placements.map((p) => (
          <ArtifactTile
            key={p.id}
            placement={p}
            artifact={artifacts[artifactKey(p.nodeId, p.fileType)]}
            onChange={(patch) => updatePlacement(p.id, patch)}
            onRemove={() => removePlacement(p.id)}
            onDuplicate={() => duplicatePlacement(p.id)}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Tile ───

interface TileProps {
  placement: Placement;
  artifact: DashboardArtifact | undefined;
  onChange: (patch: Partial<Placement>) => void;
  onRemove: () => void;
  onDuplicate: () => void;
}

function ArtifactTile({ placement, artifact, onChange, onRemove, onDuplicate }: TileProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [dragState, setDragState] = useState<
    | { mode: 'move'; startX: number; startY: number; origX: number; origY: number }
    | { mode: 'resize'; startX: number; startY: number; origW: number; origH: number }
    | null
  >(null);

  useEffect(() => {
    if (!dragState) return;
    const onMove = (e: MouseEvent) => {
      if (dragState.mode === 'move') {
        onChange({
          x: Math.max(0, snap(dragState.origX + (e.clientX - dragState.startX))),
          y: Math.max(0, snap(dragState.origY + (e.clientY - dragState.startY))),
        });
      } else {
        onChange({
          w: Math.max(TILE_MIN_W, snap(dragState.origW + (e.clientX - dragState.startX))),
          h: Math.max(TILE_MIN_H, snap(dragState.origH + (e.clientY - dragState.startY))),
        });
      }
    };
    const onUp = () => setDragState(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [dragState, onChange]);

  const startMove = (e: React.MouseEvent) => {
    e.preventDefault();
    setDragState({
      mode: 'move',
      startX: e.clientX,
      startY: e.clientY,
      origX: placement.x,
      origY: placement.y,
    });
  };

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragState({
      mode: 'resize',
      startX: e.clientX,
      startY: e.clientY,
      origW: placement.w,
      origH: placement.h,
    });
  };

  const disconnected = artifact?.status === 'disconnected';
  const stale = artifact?.status === 'stale';
  const pending = !artifact || artifact.status === 'pending';

  return (
    <div
      className={`group absolute rounded-[var(--radius-md)] border bg-card shadow-sm flex flex-col overflow-hidden ${
        disconnected
          ? 'border-dashed border-[var(--color-error-text)]/40 opacity-75'
          : stale
          ? 'border-[var(--color-warning)]/40'
          : 'border-[var(--color-border-default)]'
      }`}
      style={{ left: placement.x, top: placement.y, width: placement.w, height: placement.h }}
    >
      <div
        onMouseDown={startMove}
        className={`absolute inset-x-0 top-0 z-10 flex items-center gap-2 px-2.5 py-1.5 border-b border-[var(--color-border-default)] bg-[var(--color-bg-secondary)]/95 backdrop-blur-sm cursor-move select-none transition-opacity duration-150 ${
          settingsOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
        }`}
      >
        <TileIcon fileType={placement.fileType} disconnected={disconnected} />
        <span className="flex-1 min-w-0 truncate text-xs">
          {artifact?.label ?? 'Unknown'}
          <span className="ml-1.5 text-[0.625rem] text-[var(--color-text-tertiary)]">
            {FILE_TYPE_LABELS[placement.fileType]}
          </span>
        </span>
        {disconnected && (
          <span className="flex items-center gap-1 text-[0.625rem] text-[var(--color-error-text)]">
            <Unplug className="size-2.5" /> disconnected
          </span>
        )}
        {stale && (
          <span className="flex items-center gap-1 text-[0.625rem] text-[var(--color-warning)]">
            <Clock className="size-2.5" /> stale
          </span>
        )}
        {(placement.fileType === 'visualization' ||
          placement.fileType === 'json' ||
          placement.fileType === 'csv') && (
          <div className="relative" onMouseDown={(e) => e.stopPropagation()}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSettingsOpen((o) => !o);
              }}
              className="p-0.5 rounded hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)]"
              title="Visualization settings"
            >
              <Settings2 className="size-3" />
            </button>
            {settingsOpen && (
              <TileSettingsPopover
                config={placement}
                onChange={(patch) => onChange(patch)}
                onClose={() => setSettingsOpen(false)}
              />
            )}
          </div>
        )}
        <button
          onClick={onDuplicate}
          className="p-0.5 rounded hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)]"
          aria-label="Duplicate tile"
          title="Duplicate"
        >
          <Copy className="size-3" />
        </button>
        <button
          onClick={onRemove}
          className="p-0.5 rounded hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)]"
          aria-label="Remove tile"
        >
          <X className="size-3" />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-2.5 text-xs">
        {pending ? (
          <div className="h-full flex items-center justify-center text-[var(--color-text-tertiary)]">
            Waiting for first run
          </div>
        ) : disconnected ? (
          <div className="h-full flex flex-col items-center justify-center gap-1 text-center text-[var(--color-text-tertiary)]">
            <Unplug className="size-4" />
            <span>No longer produced by workflow</span>
            <span className="text-[0.625rem]">Showing last known output</span>
          </div>
        ) : (
          <ArtifactPreview
            artifact={artifact!}
            viewOverride={placement.viewOverride}
            color={placement.color}
            showDataLabels={placement.showDataLabels}
            width={placement.w}
            height={placement.h - 32}
          />
        )}
      </div>

      <div
        onMouseDown={startResize}
        className="absolute bottom-0 right-0 size-3 cursor-nwse-resize"
        style={{
          background: 'linear-gradient(135deg, transparent 50%, var(--color-border-strong) 50%)',
        }}
      />
    </div>
  );
}

function GhostPlaceholder({
  artifact,
  x,
  y,
  onAdd,
}: {
  artifact: DashboardArtifact;
  x: number;
  y: number;
  onAdd: () => void;
}) {
  return (
    <button
      onClick={onAdd}
      className="absolute rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-default)] bg-card/50 hover:border-[var(--color-violet-400)] hover:bg-[var(--color-violet-100)]/30 transition-colors flex flex-col items-center justify-center gap-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-violet-500)] p-3"
      style={{ left: x, top: y, width: 260, height: 200 }}
    >
      <Plus className="size-4" />
      <div className="flex items-center gap-1.5">
        <TileIcon fileType={artifact.fileType} disconnected={false} />
        <span className="text-xs truncate max-w-[11.25rem]">{artifact.label}</span>
      </div>
      <span className="text-[0.625rem]">
        {FILE_TYPE_LABELS[artifact.fileType]} · click to add
      </span>
    </button>
  );
}

function TileIcon({ fileType, disconnected }: { fileType: OutputFileType; disconnected: boolean }) {
  const cls = `size-3 ${disconnected ? 'text-[var(--color-text-tertiary)]' : 'text-[var(--color-violet-500)]'}`;
  if (fileType === 'visualization') return <BarChart3 className={cls} />;
  if (fileType === 'image') return <ImageIcon className={cls} />;
  if (fileType === 'csv') return <TableIcon className={cls} />;
  if (fileType === 'json' || fileType === 'html') return <Code2 className={cls} />;
  return <FileText className={cls} />;
}

function ArtifactPreview({
  artifact,
  viewOverride,
  color,
  showDataLabels,
  width,
  height,
}: {
  artifact: DashboardArtifact;
  viewOverride: ViewType | undefined;
  color?: string;
  showDataLabels?: boolean;
  width: number;
  height: number;
}) {
  if (!artifact.latestFile) {
    return (
      <div className="h-full flex items-center justify-center text-[var(--color-text-tertiary)]">
        No output yet
      </div>
    );
  }
  const payload = toArtifactPayload(artifact.latestFile, artifact.label);
  return (
    <ArtifactRenderer
      artifact={payload}
      viewOverride={viewOverride}
      color={color}
      showDataLabels={showDataLabels}
      width={width}
      height={height}
    />
  );
}

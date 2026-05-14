import { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeProps,
  type Connection,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import Dagre from '@dagrejs/dagre';
import { Bot, User, Trash2, Plus, Paperclip, Unlink } from 'lucide-react';
import type { AutomationTask } from '../data/automationDetailsData';
import { statusStyles, type ActivityStatus } from '../data/calendarData';

// ─── Dagre auto-layout (left-to-right) ───

const NODE_WIDTH = 220;
const NODE_HEIGHT = 100;

function layoutGraph(tasks: AutomationTask[]) {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 100 });

  tasks.forEach((t) => {
    g.setNode(t.task_id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  tasks.forEach((t) => {
    t.depends_on.forEach((dep) => {
      if (tasks.some((x) => x.task_id === dep)) {
        g.setEdge(dep, t.task_id);
      }
    });
  });

  Dagre.layout(g);

  const nodes: Node[] = tasks.map((t) => {
    const pos = g.node(t.task_id);
    return {
      id: t.task_id,
      type: 'automationTask',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: t,
      draggable: false,
    };
  });

  const edges: Edge[] = tasks.flatMap((t) =>
    t.depends_on
      .filter((dep) => tasks.some((x) => x.task_id === dep))
      .map((dep) => ({
        id: `${dep}->${t.task_id}`,
        source: dep,
        target: t.task_id,
        type: 'deletableEdge',
        animated: true,
        style: { stroke: 'var(--color-violet-400)', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--color-violet-400)' },
        data: {},
      }))
  );

  return { nodes, edges };
}

// ─── Topological sort ───

function topoSort(tasks: AutomationTask[]): string[][] {
  const taskMap = new Map(tasks.map((t) => [t.task_id, t]));
  const inDegree = new Map<string, number>();
  tasks.forEach((t) => inDegree.set(t.task_id, 0));
  tasks.forEach((t) => {
    t.depends_on.forEach((dep) => {
      if (inDegree.has(dep)) {
        inDegree.set(t.task_id, (inDegree.get(t.task_id) ?? 0) + 1);
      }
    });
  });

  const layers: string[][] = [];
  const remaining = new Set(tasks.map((t) => t.task_id));

  while (remaining.size > 0) {
    const layer = [...remaining].filter((id) => {
      const task = taskMap.get(id)!;
      return task.depends_on.filter((d) => remaining.has(d)).length === 0 ||
        inDegree.get(id) === 0;
    });
    if (layer.length === 0) break; // cycle protection
    // Only take those with 0 current in-degree
    const ready = layer.filter((id) => {
      const task = taskMap.get(id)!;
      return task.depends_on.every((d) => !remaining.has(d));
    });
    if (ready.length === 0) break;
    layers.push(ready);
    ready.forEach((id) => remaining.delete(id));
  }
  return layers;
}

// ─── Custom Deletable Edge ───

function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  data,
}: EdgeProps) {
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const runState = (data as any)?._runState as string | undefined;
  const edgeStyle = runState === 'complete'
    ? { ...style, stroke: 'var(--color-success)', strokeWidth: 3 }
    : runState === 'running'
      ? { ...style, stroke: 'var(--color-warning)', strokeWidth: 3 }
      : style;

  return (
    <>
      <BaseEdge path={path} style={edgeStyle} markerEnd={markerEnd} />
      {!(data as any)?._isRunning && (
        <foreignObject
          x={labelX - 10}
          y={labelY - 10}
          width={20}
          height={20}
          className="overflow-visible"
        >
          <button
            className="w-5 h-5 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity hover:bg-[var(--color-error-bg)] hover:border-[var(--color-error-text)] group"
            onClick={(e) => {
              e.stopPropagation();
              const event = new CustomEvent('delete-edge', { detail: { edgeId: id } });
              window.dispatchEvent(event);
            }}
            title="Remove dependency"
          >
            <Trash2 className="size-2.5 text-[var(--color-text-tertiary)] group-hover:text-[var(--color-error-text)]" />
          </button>
        </foreignObject>
      )}
    </>
  );
}

// ─── Custom Node ───

function AutomationTaskNode({ data, selected }: NodeProps) {
  const task = data as unknown as AutomationTask & { _runState?: string; _isRunning?: boolean };
  const sStyle = statusStyles[task.status as ActivityStatus] ?? statusStyles['Draft'];
  const isAgent = task.assignee_type === 'agent';
  const runState = task._runState;

  let borderClass = selected
    ? 'border-[var(--color-violet-500)] shadow-lg'
    : 'border-[var(--color-border-default)]';

  let runGlow = '';
  if (runState === 'running') {
    borderClass = 'border-[var(--color-warning)] shadow-lg';
    runGlow = 'animate-pulse';
  } else if (runState === 'complete') {
    borderClass = 'border-[var(--color-success)]';
  }

  return (
    <div
      className={`group/node relative rounded-[var(--radius-md)] border-2 bg-card p-3 transition-all ${borderClass} ${runGlow}`}
      style={{ width: NODE_WIDTH }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-[var(--color-violet-400)] !w-2.5 !h-2.5 !border-2 !border-[var(--color-bg-elevated)]"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-[var(--color-violet-400)] !w-2.5 !h-2.5 !border-2 !border-[var(--color-bg-elevated)]"
      />

      {/* Delete button */}
      {!task._isRunning && (
        <button
          className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] flex items-center justify-center opacity-0 group-hover/node:opacity-100 hover:opacity-100 transition-opacity hover:bg-[var(--color-error-bg)] hover:border-[var(--color-error-text)] group z-10"
          onClick={(e) => {
            e.stopPropagation();
            const event = new CustomEvent('delete-task', { detail: { taskId: task.task_id } });
            window.dispatchEvent(event);
          }}
          title="Delete task"
        >
          <Trash2 className="size-2.5 text-[var(--color-text-tertiary)] group-hover:text-[var(--color-error-text)]" />
        </button>
      )}

      {/* Detach button */}
      {!task._isRunning && (
        <button
          className="absolute -top-2 -left-2 w-5 h-5 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] flex items-center justify-center opacity-0 group-hover/node:opacity-100 hover:opacity-100 transition-opacity hover:bg-[var(--color-violet-100)] hover:border-[var(--color-violet-500)] group z-10"
          onClick={(e) => {
            e.stopPropagation();
            const event = new CustomEvent('detach-task', { detail: { taskId: task.task_id } });
            window.dispatchEvent(event);
          }}
          title="Detach from project"
        >
          <Unlink className="size-2.5 text-[var(--color-text-tertiary)] group-hover:text-[var(--color-violet-600)]" />
        </button>
      )}

      {/* Run state indicator */}
      {runState === 'running' && (
        <div className="absolute -top-1 -left-1 w-3 h-3 rounded-full bg-[var(--color-warning)] animate-ping" />
      )}
      {runState === 'complete' && (
        <div className="absolute -top-1 -left-1 w-3 h-3 rounded-full bg-[var(--color-success)]" />
      )}

      <p className="text-xs truncate mb-1.5" title={task.title}>
        {task.title}
      </p>

      <div className="flex items-center gap-1.5 mb-1.5">
        <span
          className="text-[0.5625rem] px-1.5 py-0.5 rounded"
          style={{ background: sStyle.bg, color: sStyle.text, border: `1px solid ${sStyle.border}` }}
        >
          {runState === 'complete' ? 'Complete' : runState === 'running' ? 'Running...' : task.status}
        </span>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-[0.625rem] text-[var(--color-text-tertiary)]">
          {isAgent ? <Bot className="size-3" /> : <User className="size-3" />}
          <span className="truncate max-w-[6.25rem]">{task.assignee_name ?? 'Unassigned'}</span>
        </div>
        <div className="flex items-center gap-1">
          {task.output_config?.enabled && (
            <div className="relative" title={(task.run_outputs ?? []).length > 0 ? `${(task.run_outputs ?? [])[0]?.outputs.length ?? 0} output file(s)` : 'Produces output files'}>
              <Paperclip className="size-3 text-[var(--color-text-tertiary)]" />
              {(task.run_outputs ?? []).length > 0 && (task.run_outputs ?? [])[0]?.outputs.length > 0 && (
                <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[var(--color-violet-500)]" />
              )}
            </div>
          )}
          {task.estimated_effort && (
            <span className="text-[0.5625rem] text-[var(--color-text-tertiary)]">{task.estimated_effort}</span>
          )}
        </div>
      </div>
    </div>
  );
}

const nodeTypes = { automationTask: AutomationTaskNode };
const edgeTypes = { deletableEdge: DeletableEdge };

// ─── Main Graph Component ───

interface AutomationGraphProps {
  tasks: AutomationTask[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string | null) => void;
  onAddTask: () => void;
  onDeleteTask: (taskId: string) => void;
  onDetachTask?: (taskId: string) => void;
  onConnect: (sourceId: string, targetId: string) => void;
  onDeleteEdge: (sourceId: string, targetId: string) => void;
  runState: Record<string, 'pending' | 'running' | 'complete'>;
  isRunning: boolean;
}

function AutomationGraphInner({
  tasks,
  selectedTaskId,
  onSelectTask,
  onAddTask,
  onDeleteTask,
  onDetachTask,
  onConnect: onConnectProp,
  onDeleteEdge,
  runState,
  isRunning,
}: AutomationGraphProps) {
  const { nodes, edges } = useMemo(() => layoutGraph(tasks), [tasks]);
  const reactFlowInstance = useReactFlow();

  // Inject run state into node/edge data
  const nodesWithState = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        selected: n.id === selectedTaskId,
        data: { ...n.data, _runState: runState[n.id] ?? 'pending', _isRunning: isRunning },
      })),
    [nodes, selectedTaskId, runState, isRunning]
  );

  const edgesWithState = useMemo(
    () =>
      edges.map((e) => {
        const sourceState = runState[e.source];
        const targetState = runState[e.target];
        let edgeRunState = 'pending';
        if (sourceState === 'complete' && targetState === 'complete') edgeRunState = 'complete';
        else if (sourceState === 'complete' && targetState === 'running') edgeRunState = 'running';
        return {
          ...e,
          data: { ...e.data, _runState: edgeRunState, _isRunning: isRunning },
        };
      }),
    [edges, runState, isRunning]
  );

  // Fit view when tasks change
  useEffect(() => {
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.3 });
    }, 50);
  }, [tasks, reactFlowInstance]);

  // Listen for custom delete events
  useEffect(() => {
    const handleDeleteEdge = (e: Event) => {
      const edgeId = (e as CustomEvent).detail.edgeId as string;
      const [source, target] = edgeId.split('->');
      if (source && target) onDeleteEdge(source, target);
    };
    const handleDeleteTask = (e: Event) => {
      const taskId = (e as CustomEvent).detail.taskId as string;
      onDeleteTask(taskId);
    };
    const handleDetachTask = (e: Event) => {
      const taskId = (e as CustomEvent).detail.taskId as string;
      onDetachTask?.(taskId);
    };
    window.addEventListener('delete-edge', handleDeleteEdge);
    window.addEventListener('delete-task', handleDeleteTask);
    window.addEventListener('detach-task', handleDetachTask);
    return () => {
      window.removeEventListener('delete-edge', handleDeleteEdge);
      window.removeEventListener('delete-task', handleDeleteTask);
      window.removeEventListener('detach-task', handleDetachTask);
    };
  }, [onDeleteEdge, onDeleteTask, onDetachTask]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectTask(node.id === selectedTaskId ? null : node.id);
    },
    [onSelectTask, selectedTaskId]
  );

  const onPaneClick = useCallback(() => {
    onSelectTask(null);
  }, [onSelectTask]);

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target && connection.source !== connection.target) {
        onConnectProp(connection.source, connection.target);
      }
    },
    [onConnectProp]
  );

  const isValidConnection = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return false;
      if (connection.source === connection.target) return false;
      // Prevent duplicate edges
      const target = tasks.find((t) => t.task_id === connection.target);
      if (target?.depends_on.includes(connection.source)) return false;
      // Prevent reverse edges (would create cycle)
      const source = tasks.find((t) => t.task_id === connection.source);
      if (source?.depends_on.includes(connection.target)) return false;
      return true;
    },
    [tasks]
  );

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodesWithState}
        edges={edgesWithState}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onConnect={handleConnect}
        isValidConnection={isValidConnection}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={false}
        nodesConnectable={!isRunning}
        panOnDrag
        zoomOnScroll
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        connectionLineStyle={{ stroke: 'var(--color-violet-400)', strokeWidth: 2 }}
        defaultEdgeOptions={{
          type: 'deletableEdge',
          animated: true,
          style: { stroke: 'var(--color-violet-400)', strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--color-violet-400)' },
        }}
      >
        <Background color="var(--color-border-subtle)" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>

      {/* Add Task button */}
      {!isRunning && (
        <button
          onClick={onAddTask}
          className="absolute bottom-4 right-4 flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] text-white text-xs hover:bg-[var(--color-violet-600)] transition-colors shadow-lg z-10"
          style={{ boxShadow: 'var(--shadow-color-violet)' }}
        >
          <Plus className="size-3.5" />
          Add Task
        </button>
      )}

      {/* Connection hint */}
      {!isRunning && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 text-[0.625rem] text-[var(--color-text-tertiary)] bg-[var(--color-bg-elevated)]/80 backdrop-blur-sm px-3 py-1 rounded-full border border-[var(--color-border-subtle)] z-10">
          Drag between handles to connect • Hover edges to delete • Hover node to detach
        </div>
      )}
    </div>
  );
}

export function AutomationGraph(props: AutomationGraphProps) {
  return (
    <ReactFlowProvider>
      <AutomationGraphInner {...props} />
    </ReactFlowProvider>
  );
}

export { topoSort };
// ─── Standalone (orphan) tasks ───
// Mock layer for option 3: tasks can live outside any project plan.
// Backed by a module-level mutable list + a tiny pub/sub so React components
// can subscribe with `useSyncExternalStore`. When we move to a real backend,
// this file is the only consumer boundary that changes.

import { useSyncExternalStore } from 'react';
import type { CalendarActivity, ActivityStatus } from './calendarData';

// ─── Seed data ───

const nowIso = new Date(2026, 3, 21, 9, 0); // 2026-04-21 — aligns with the app's "today"

function seed(): CalendarActivity[] {
  return [
    {
      activity_id: 'orphan-1',
      name: 'Update pricing page hero copy',
      campaign_id: 'camp-3',
      channel: 'Website',
      platform: 'Webflow',
      cost: 0,
      launch_date: new Date(2026, 3, 23, 14, 0),
      launch_time_utc: '14:00',
      category: 'task',
      task_type: 'Demand Gen',
      tags: ['website', 'copy'],
      owner: 'sarah.chen@example.com',
      status: 'Draft',
      created_date: nowIso,
      created_by: 'sarah.chen@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'sarah.chen@example.com',
      plan_id: null,
    },
    {
      activity_id: 'orphan-2',
      name: 'Review Q2 brand asset audit',
      campaign_id: 'camp-1',
      channel: null,
      platform: null,
      cost: 0,
      launch_date: new Date(2026, 3, 28, 10, 0),
      launch_time_utc: '10:00',
      category: 'task',
      task_type: 'Brand',
      tags: ['brand', 'audit'],
      owner: 'priya.patel@example.com',
      status: 'Awaiting Approval',
      created_date: nowIso,
      created_by: 'priya.patel@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'priya.patel@example.com',
      plan_id: null,
    },
    {
      activity_id: 'orphan-3',
      name: 'Draft newsletter for May launch',
      campaign_id: 'camp-2',
      channel: 'Email',
      platform: 'Mailchimp',
      cost: 120,
      launch_date: new Date(2026, 4, 5, 15, 30),
      launch_time_utc: '15:30',
      category: 'task',
      task_type: 'Demand Gen',
      tags: ['email', 'newsletter'],
      owner: 'marco.rossi@example.com',
      status: 'Draft',
      created_date: nowIso,
      created_by: 'marco.rossi@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'marco.rossi@example.com',
      plan_id: null,
    },
    {
      activity_id: 'orphan-4',
      name: 'Follow up on partnership intro',
      campaign_id: 'camp-1',
      channel: null,
      platform: null,
      cost: 0,
      launch_date: nowIso,
      launch_time_utc: null,
      category: 'task',
      task_type: null,
      tags: [],
      owner: 'sarah.chen@example.com',
      status: 'Draft',
      created_date: nowIso,
      created_by: 'sarah.chen@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'sarah.chen@example.com',
      plan_id: null,
      unscheduled: true,
    },
    {
      activity_id: 'orphan-5',
      name: 'Archive old campaign assets',
      campaign_id: 'camp-1',
      channel: null,
      platform: null,
      cost: 0,
      launch_date: nowIso,
      launch_time_utc: null,
      category: 'task',
      task_type: null,
      tags: [],
      owner: 'marco.rossi@example.com',
      status: 'Draft',
      created_date: nowIso,
      created_by: 'marco.rossi@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'marco.rossi@example.com',
      plan_id: null,
      unscheduled: true,
    },
    {
      activity_id: 'orphan-6',
      name: 'Weekly Monday status email',
      campaign_id: 'camp-1',
      channel: 'Email',
      platform: null,
      cost: 0,
      launch_date: new Date(2026, 3, 27, 9, 0), // first occurrence: Mon Apr 27 2026
      launch_time_utc: '09:00',
      category: 'task',
      task_type: 'Brand',
      tags: ['recurring', 'status'],
      owner: 'sarah.chen@example.com',
      status: 'Draft',
      created_date: nowIso,
      created_by: 'sarah.chen@example.com',
      last_updated_at: nowIso,
      last_updated_by: 'sarah.chen@example.com',
      plan_id: null,
      schedule: {
        enabled: true,
        frequency: 'weekly',
        days_of_week: [1], // Monday
        day_of_month: null,
        time_utc: '09:00',
        cron_expression: null,
        run_date: null,
        next_run: null,
        last_run: null,
      },
    },
  ];
}

let tasks: CalendarActivity[] = seed();

// ─── Pub/sub ───

const listeners = new Set<() => void>();
function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
function emit() {
  for (const cb of listeners) cb();
}
function getSnapshot(): readonly CalendarActivity[] {
  return tasks;
}

// ─── Mutations ───

export function listOrphans(): readonly CalendarActivity[] {
  return tasks;
}

export function getOrphan(taskId: string): CalendarActivity | undefined {
  return tasks.find(t => t.activity_id === taskId);
}

export type CreateOrphanInput = Omit<
  CalendarActivity,
  'activity_id' | 'created_date' | 'created_by' | 'last_updated_at' | 'last_updated_by' | 'plan_id'
> & {
  activity_id?: string;
  created_by?: string;
};

export function createOrphan(input: CreateOrphanInput): CalendarActivity {
  const now = new Date();
  const creator = input.created_by ?? 'sarah.chen@example.com';
  const task: CalendarActivity = {
    ...input,
    activity_id: input.activity_id ?? `orphan-${now.getTime()}`,
    created_date: now,
    created_by: creator,
    last_updated_at: now,
    last_updated_by: creator,
    plan_id: null,
  };
  tasks = [...tasks, task];
  emit();
  return task;
}

export function updateOrphan(
  taskId: string,
  patch: Partial<CalendarActivity>,
): CalendarActivity | null {
  let updated: CalendarActivity | null = null;
  tasks = tasks.map(t => {
    if (t.activity_id !== taskId) return t;
    updated = {
      ...t,
      ...patch,
      activity_id: t.activity_id,
      last_updated_at: new Date(),
      last_updated_by: patch.last_updated_by ?? t.last_updated_by,
      plan_id: null,
    };
    return updated;
  });
  if (updated) emit();
  return updated;
}

export function deleteOrphan(taskId: string): boolean {
  const before = tasks.length;
  tasks = tasks.filter(t => t.activity_id !== taskId);
  if (tasks.length !== before) {
    emit();
    return true;
  }
  return false;
}

// ─── Attach / detach / promote (stubs for later steps) ───

export type AttachResult =
  | { ok: true; task: CalendarActivity }
  | { ok: false; reason: 'not-found' };

/**
 * Move an orphan task into a project. Removes it from the orphan list and
 * returns the task shaped for insertion into the plan. The caller is
 * responsible for appending it to the target plan's `tasks[]`.
 */
export function attachToPlan(taskId: string, planId: string): AttachResult {
  const task = tasks.find(t => t.activity_id === taskId);
  if (!task) return { ok: false, reason: 'not-found' };
  tasks = tasks.filter(t => t.activity_id !== taskId);
  emit();
  return { ok: true, task: { ...task, plan_id: planId } };
}

/**
 * Move a task from a plan back to the orphan list. The caller provides the
 * task (already removed from the plan's `tasks[]`) and this function restores
 * it as an orphan with `plan_id: null` and `depends_on` cleared semantics.
 */
export function detachFromPlan(task: CalendarActivity): CalendarActivity {
  const orphan: CalendarActivity = { ...task, plan_id: null };
  tasks = [...tasks, orphan];
  emit();
  return orphan;
}

/**
 * Remove a batch of orphans so they can be bundled into a new project plan by
 * the caller. Returns the removed tasks with `plan_id` stamped.
 */
export function takeOrphansForNewPlan(taskIds: string[], planId: string): CalendarActivity[] {
  const removed: CalendarActivity[] = [];
  tasks = tasks.filter(t => {
    if (taskIds.includes(t.activity_id)) {
      removed.push({ ...t, plan_id: planId });
      return false;
    }
    return true;
  });
  if (removed.length > 0) emit();
  return removed;
}

// ─── React hook ───

export function useStandaloneTasks(): readonly CalendarActivity[] {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import { goalKey } from '../data/goalsData';

/* ---- Types ---- */

export interface ForecastGoals {
  /** key = goalKey(stageId, month, year), value = target number */
  [key: string]: number;
}

interface GoalsContextValue {
  /** Current goal values (includes both saved and dirty) */
  goals: Map<string, number | null>;
  /** Set a single goal value */
  setGoal: (stageId: string, month: number, year: number, value: number | null) => void;
  /** Bulk-set forecast values as goals (from Simulations) */
  setForecastAsGoals: (forecasts: { stageId: string; month: number; year: number; value: number }[]) => void;
  /** Save all dirty goals (simulated async) */
  saveGoals: () => Promise<void>;
  /** Whether there are unsaved changes */
  isDirty: boolean;
  /** Whether a save is in progress */
  isSaving: boolean;
  /** Set of dirty keys (for cell highlighting) */
  dirtyKeys: Set<string>;
  /** Whether forecast-as-goals has been set in this session */
  targetsSaved: boolean;
  setTargetsSaved: (v: boolean) => void;
}

const GoalsContext = createContext<GoalsContextValue | null>(null);

export function GoalsProvider({ children }: { children: ReactNode }) {
  // Saved goals (persisted state)
  const [savedGoals, setSavedGoals] = useState<Map<string, number | null>>(new Map());
  // Working goals (includes unsaved edits)
  const [goals, setGoals] = useState<Map<string, number | null>>(new Map());
  // Track which keys are dirty
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set());
  const [isSaving, setIsSaving] = useState(false);
  const [targetsSaved, setTargetsSaved] = useState(false);

  const isDirty = dirtyKeys.size > 0;

  const setGoal = useCallback((stageId: string, month: number, year: number, value: number | null) => {
    const key = goalKey(stageId, month, year);
    setGoals(prev => {
      const next = new Map(prev);
      next.set(key, value);
      return next;
    });
    setDirtyKeys(prev => {
      const next = new Set(prev);
      // Check if the value matches the saved value
      const savedVal = savedGoals.get(key) ?? null;
      if (value === savedVal) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, [savedGoals]);

  const setForecastAsGoals = useCallback((forecasts: { stageId: string; month: number; year: number; value: number }[]) => {
    setGoals(prev => {
      const next = new Map(prev);
      forecasts.forEach(f => {
        next.set(goalKey(f.stageId, f.month, f.year), f.value);
      });
      return next;
    });
    setDirtyKeys(prev => {
      const next = new Set(prev);
      forecasts.forEach(f => {
        next.add(goalKey(f.stageId, f.month, f.year));
      });
      return next;
    });
    setTargetsSaved(true);
  }, []);

  const saveGoals = useCallback(async () => {
    setIsSaving(true);
    // Simulate async save
    await new Promise(resolve => setTimeout(resolve, 800));
    setSavedGoals(new Map(goals));
    setDirtyKeys(new Set());
    setIsSaving(false);
  }, [goals]);

  const value = useMemo<GoalsContextValue>(() => ({
    goals,
    setGoal,
    setForecastAsGoals,
    saveGoals,
    isDirty,
    isSaving,
    dirtyKeys,
    targetsSaved,
    setTargetsSaved,
  }), [goals, setGoal, setForecastAsGoals, saveGoals, isDirty, isSaving, dirtyKeys, targetsSaved, setTargetsSaved]);

  return (
    <GoalsContext.Provider value={value}>
      {children}
    </GoalsContext.Provider>
  );
}

export function useGoals(): GoalsContextValue {
  const ctx = useContext(GoalsContext);
  if (!ctx) throw new Error('useGoals must be used within GoalsProvider');
  return ctx;
}

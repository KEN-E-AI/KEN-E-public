/**
 * ActivitiesContext — Shared activity state across CalendarPage and SimulationsSection.
 *
 * This context owns the canonical list of CalendarActivity items, allowing
 * both the Campaign Calendar and Performance Simulations pages to read and
 * mutate the same dataset.
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { calendarActivities as initialActivities, type CalendarActivity } from '../data/calendarData';

interface ActivitiesContextValue {
  activities: CalendarActivity[];
  setActivities: React.Dispatch<React.SetStateAction<CalendarActivity[]>>;
  addActivity: (activity: CalendarActivity) => void;
  addActivities: (activities: CalendarActivity[]) => void;
  updateActivity: (id: string, changes: Partial<CalendarActivity>) => void;
  deleteActivity: (id: string) => void;
  /** Replace the full activity object (used by ActivityDrawer save). */
  saveActivity: (activity: CalendarActivity) => void;
}

const ActivitiesContext = createContext<ActivitiesContextValue | null>(null);

export function ActivitiesProvider({ children }: { children: ReactNode }) {
  const [activities, setActivities] = useState<CalendarActivity[]>(initialActivities);

  const addActivity = useCallback((activity: CalendarActivity) => {
    setActivities((prev) => [...prev, activity]);
  }, []);

  const addActivities = useCallback((newActivities: CalendarActivity[]) => {
    setActivities((prev) => [...prev, ...newActivities]);
  }, []);

  const updateActivity = useCallback((id: string, changes: Partial<CalendarActivity>) => {
    setActivities((prev) =>
      prev.map((a) => (a.activity_id === id ? { ...a, ...changes } : a)),
    );
  }, []);

  const deleteActivity = useCallback((id: string) => {
    setActivities((prev) => prev.filter((a) => a.activity_id !== id));
  }, []);

  const saveActivity = useCallback((activity: CalendarActivity) => {
    setActivities((prev) => {
      const exists = prev.find((a) => a.activity_id === activity.activity_id);
      if (exists) {
        return prev.map((a) => (a.activity_id === activity.activity_id ? activity : a));
      }
      return [...prev, activity];
    });
  }, []);

  return (
    <ActivitiesContext.Provider
      value={{
        activities,
        setActivities,
        addActivity,
        addActivities,
        updateActivity,
        deleteActivity,
        saveActivity,
      }}
    >
      {children}
    </ActivitiesContext.Provider>
  );
}

export function useActivities(): ActivitiesContextValue {
  const ctx = useContext(ActivitiesContext);
  if (!ctx) throw new Error('useActivities must be used within ActivitiesProvider');
  return ctx;
}

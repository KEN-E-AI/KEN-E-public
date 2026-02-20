import { useCallback, useEffect, useRef, useState } from "react";
import { chatService } from "@/services/chatService";

const WARNING_MINUTES = 25;
const TIMEOUT_MINUTES = 30;
const ACTIVITY_DEBOUNCE_MS = 30_000;

interface UseSessionTimeoutOptions {
  sessionId: string | null;
  enabled?: boolean;
  warningMinutes?: number;
  timeoutMinutes?: number;
  onTimeout?: () => void;
}

interface UseSessionTimeoutResult {
  isWarningShown: boolean;
  isExpired: boolean;
  remainingSeconds: number;
  extendSession: () => void;
}

export function useSessionTimeout({
  sessionId,
  enabled = true,
  warningMinutes = WARNING_MINUTES,
  timeoutMinutes = TIMEOUT_MINUTES,
  onTimeout,
}: UseSessionTimeoutOptions): UseSessionTimeoutResult {
  const [isWarningShown, setIsWarningShown] = useState(false);
  const [isExpired, setIsExpired] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(timeoutMinutes * 60);

  const lastActivityRef = useRef(Date.now());
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tickIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutFiredRef = useRef(false);
  const onTimeoutRef = useRef(onTimeout);

  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  const resetTimer = useCallback(() => {
    lastActivityRef.current = Date.now();
    timeoutFiredRef.current = false;
    setIsWarningShown(false);
    setIsExpired(false);
    setRemainingSeconds(timeoutMinutes * 60);
  }, [timeoutMinutes]);

  const extendSession = useCallback(async () => {
    resetTimer();
    if (sessionId) {
      const response = await chatService.recordActivity(sessionId);
      if (response.remaining_seconds != null) {
        setRemainingSeconds(response.remaining_seconds);
      }
    }
  }, [sessionId, resetTimer]);

  // Tick every second to update remaining time
  useEffect(() => {
    if (!enabled || !sessionId) return;

    resetTimer();

    tickIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - lastActivityRef.current) / 1000;
      const remaining = Math.max(0, timeoutMinutes * 60 - elapsed);
      setRemainingSeconds(Math.round(remaining));

      if (remaining <= 0 && !timeoutFiredRef.current) {
        timeoutFiredRef.current = true;
        setIsExpired(true);
        setIsWarningShown(false);
        onTimeoutRef.current?.();
      } else if (remaining > 0 && elapsed >= warningMinutes * 60) {
        setIsWarningShown(true);
      }
    }, 1000);

    return () => {
      if (tickIntervalRef.current) {
        clearInterval(tickIntervalRef.current);
      }
    };
  }, [enabled, sessionId, warningMinutes, timeoutMinutes, resetTimer]);

  // Listen for user activity events (debounced)
  useEffect(() => {
    if (!enabled || !sessionId) return;

    const handleActivity = () => {
      lastActivityRef.current = Date.now();

      if (isWarningShown) {
        setIsWarningShown(false);
      }

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        chatService
          .recordActivity(sessionId)
          .then((response) => {
            if (response.remaining_seconds != null) {
              setRemainingSeconds(response.remaining_seconds);
            }
          })
          .catch(() => {});
      }, ACTIVITY_DEBOUNCE_MS);
    };

    // mousemove excluded to avoid constant timer resets from idle cursor movement
    const events = ["keydown", "click", "scroll"] as const;
    events.forEach((event) => window.addEventListener(event, handleActivity));

    return () => {
      events.forEach((event) =>
        window.removeEventListener(event, handleActivity),
      );
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [enabled, sessionId, isWarningShown]);

  return { isWarningShown, isExpired, remainingSeconds, extendSession };
}

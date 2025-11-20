import { Button } from "@/components/ui/button";
import type { ModeConfig } from "../types";

interface ModeSelectorProps<T extends string> {
  modes: readonly ModeConfig<T>[];
  value: T;
  onChange: (mode: T) => void;
  className?: string;
}

/**
 * Segmented control for switching between different view modes
 * Used for Account (Strengths/Weaknesses) and Competitors (Strengths/Weaknesses/Substitutes)
 */
export function ModeSelector<T extends string>({
  modes,
  value,
  onChange,
  className = "",
}: ModeSelectorProps<T>) {
  return (
    <div className={`flex ${className}`}>
      <div className="inline-flex rounded-md border border-input bg-muted p-1 gap-1">
        {modes.map((mode) => (
          <Button
            key={mode.value}
            variant={value === mode.value ? "default" : "ghost"}
            size="sm"
            onClick={() => onChange(mode.value)}
            className="px-6"
          >
            {mode.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

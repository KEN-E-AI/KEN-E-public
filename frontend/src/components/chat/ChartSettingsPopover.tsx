import { Check } from "lucide-react";

export type ViewOverride = "bar" | "line" | "area" | "point" | "arc";

export type ArtifactConfig = {
  viewOverride?: ViewOverride;
  color?: string;
  showDataLabels?: boolean;
};

export const VIEW_OPTIONS: { value: ViewOverride; label: string }[] = [
  { value: "bar", label: "Bar" },
  { value: "line", label: "Line" },
  { value: "area", label: "Area" },
  { value: "point", label: "Scatter" },
  { value: "arc", label: "Pie" },
];

export const COLOR_SWATCHES = [
  { name: "Violet", varName: "--color-violet-500", fallback: "#6366F1" },
  { name: "Blue", varName: "--color-blue-500", fallback: "#3B82F6" },
  { name: "Teal", varName: "--color-teal-500", fallback: "#2EC4B6" },
  { name: "Amber", varName: "--color-amber-500", fallback: "#F59E0B" },
  { name: "Slate", varName: "--color-slate-500", fallback: "#64748B" },
];

type Props = {
  config: ArtifactConfig;
  onChange: (patch: Partial<ArtifactConfig>) => void;
};

export function ChartSettingsPopover({ config, onChange }: Props) {
  const currentColor = config.color;
  return (
    <div className="space-y-2.5" data-testid="chart-settings-popover">
      <div>
        <p className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1">
          View as
        </p>
        {/* allow-text-tertiary: settings-popover label */}
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => onChange({ viewOverride: undefined })}
            className={`text-[0.625rem] px-1.5 py-0.5 rounded border transition-colors ${
              config.viewOverride === undefined
                ? "bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]"
                : "border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]"
            }`}
          >
            Auto
          </button>
          {VIEW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onChange({ viewOverride: opt.value })}
              className={`text-[0.625rem] px-1.5 py-0.5 rounded border transition-colors ${
                config.viewOverride === opt.value
                  ? "bg-[var(--color-violet-100)] border-[var(--color-violet-400)] text-[var(--color-violet-500)]"
                  : "border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-[0.625rem] text-[var(--color-text-tertiary)] mb-1">
          Color
        </p>
        {/* allow-text-tertiary: settings-popover label */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onChange({ color: undefined })}
            className={`size-5 rounded-full border text-[0.5rem] flex items-center justify-center ${
              !currentColor
                ? "border-[var(--color-violet-500)] text-[var(--color-violet-500)]"
                : "border-[var(--color-border-default)] text-[var(--color-text-tertiary)]" /* allow-text-tertiary: inactive auto-color swatch */
            }`}
            title="Auto"
          >
            A
          </button>
          {COLOR_SWATCHES.map((s) => {
            const active = currentColor === s.varName;
            return (
              <button
                key={s.varName}
                onClick={() => onChange({ color: s.varName })}
                className={`size-5 rounded-full border flex items-center justify-center ${
                  active
                    ? "ring-2 ring-offset-1 ring-[var(--color-border-strong)]"
                    : "border-transparent"
                }`}
                style={{ background: `var(${s.varName}, ${s.fallback})` }}
                title={s.name}
              >
                {active && <Check className="size-2.5 text-white" />}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[0.625rem] text-[var(--color-text-tertiary)]">
          Data labels
        </span>
        {/* allow-text-tertiary: settings-popover label */}
        <button
          onClick={() => onChange({ showDataLabels: !config.showDataLabels })}
          className={`w-7 h-4 rounded-full relative transition-colors ${
            config.showDataLabels
              ? "bg-[var(--color-violet-500)]"
              : "bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)]"
          }`}
        >
          <span
            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform ${
              config.showDataLabels ? "translate-x-3.5" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>
    </div>
  );
}

import { Component, useEffect, useMemo, useState } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { VegaEmbed } from "react-vega";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import type { Artifact } from "@/lib/chatApi";
import type { ViewOverride } from "./ChartSettingsPopover";

export type { ViewOverride };

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return v || fallback;
}

function useVegaTheme(color: string): Record<string, unknown> {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const observer = new MutationObserver(() => setTick((t) => t + 1));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });
    return () => observer.disconnect();
  }, []);

  return useMemo(() => {
    const category = [
      cssVar("--color-teal-500", "#2EC4B6"),
      cssVar("--color-violet-500", "#6366F1"),
      cssVar("--color-blue-500", "#3B82F6"),
      cssVar("--color-amber-500", "#F59E0B"),
      cssVar("--color-teal-400", "#6AD8CC"),
      cssVar("--color-violet-400", "#818CF8"),
      cssVar("--color-blue-400", "#60A5FA"),
      cssVar("--color-slate-400", "#94A3B8"),
    ];
    const textPrimary = cssVar("--color-text-primary", "#0F172A");
    const textSecondary = cssVar("--color-text-secondary", "#334155");
    const textTertiary = cssVar("--color-text-tertiary", "#64748B");
    const gridColor = cssVar("--color-border-subtle", "#E2E8F0");
    const font =
      "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    return {
      background: "transparent",
      font,
      padding: 8,
      title: {
        font,
        fontWeight: 600,
        fontSize: 13,
        color: textPrimary,
        anchor: "start",
        offset: 8,
      },
      axis: {
        labelFont: font,
        titleFont: font,
        labelColor: textTertiary,
        titleColor: textSecondary,
        labelFontSize: 10,
        titleFontSize: 11,
        titleFontWeight: 500,
        titlePadding: 8,
        domainColor: gridColor,
        tickColor: gridColor,
        gridColor,
        gridOpacity: 0.6,
        gridDash: [2, 3],
      },
      legend: {
        labelFont: font,
        titleFont: font,
        labelColor: textSecondary,
        titleColor: textSecondary,
        labelFontSize: 10,
        titleFontSize: 11,
        symbolStrokeWidth: 0,
      },
      view: { stroke: "transparent" },
      mark: { color: category[0], cornerRadius: 3 },
      bar: { color: category[0], cornerRadiusEnd: 4 },
      line: { color: category[0], strokeWidth: 2.5 },
      area: { color: category[0], opacity: 0.35 },
      point: { fill: category[0], filled: true, size: 80 },
      arc: {
        fill: category[0],
        innerRadius: 40,
        padAngle: 0.02,
        cornerRadius: 3,
      },
      rect: { color: category[0] },
      range: {
        category,
        ordinal: { scheme: "purples" },
        ramp: { scheme: "purples" },
        heatmap: { scheme: "purples" },
      },
    };
    // color drives the colorConfig below; tick drives re-reads of CSS vars on theme switch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, color]);
}

function applyDataLabels(
  spec: Record<string, unknown>,
): Record<string, unknown> {
  const s = spec as {
    layer?: unknown;
    mark?: unknown;
    encoding?: { y?: { field?: string; type?: string }; x?: unknown };
  };
  // arc (pie/donut) uses theta/color channels, not x/y — data labels are not applicable
  if (s.layer || !s.mark || !s.encoding || s.mark === "arc") return spec;
  const yField = s.encoding.y?.field;
  if (!yField) return spec;
  const textEncoding = {
    ...s.encoding,
    text: { field: yField, type: s.encoding.y?.type ?? "quantitative" },
  };
  const { mark, encoding, ...rest } = s as Record<string, unknown>;
  return {
    ...rest,
    layer: [
      { mark, encoding },
      {
        mark: { type: "text", dy: -6, fontSize: 10, fontWeight: 500 },
        encoding: textEncoding,
      },
    ],
  };
}

function VisualizationRenderer({
  spec,
  color,
  showDataLabels,
}: {
  spec: Record<string, unknown>;
  color?: string;
  showDataLabels?: boolean;
}) {
  const themeConfig = useVegaTheme(color ?? "");
  const sized = useMemo(() => {
    const resolvedColor = color ? cssVar(color, "#6366F1") : undefined;
    const colorConfig = resolvedColor
      ? {
          mark: { ...(themeConfig.mark as object), color: resolvedColor },
          bar: { ...(themeConfig.bar as object), color: resolvedColor },
          line: { ...(themeConfig.line as object), color: resolvedColor },
          area: { ...(themeConfig.area as object), color: resolvedColor },
          point: { ...(themeConfig.point as object), fill: resolvedColor },
          arc: { ...(themeConfig.arc as object), fill: resolvedColor },
          rect: { ...(themeConfig.rect as object), color: resolvedColor },
        }
      : {};
    // Strip spec.config: backend bans it; frontend strips it as defence-in-depth
    // so any bypass cannot override app theme or user color choice.
    const { config: _stripped, ...specWithoutConfig } = spec as Record<
      string,
      unknown
    > & { config?: unknown };
    const withLabels = showDataLabels
      ? applyDataLabels(specWithoutConfig)
      : specWithoutConfig;
    return {
      ...withLabels,
      $schema: "https://vega.github.io/schema/vega-lite/v6.json",
      width: "container",
      height: 280,
      autosize: { type: "fit", contains: "padding" },
      // colorConfig last so user color overrides win over theme defaults
      config: { ...themeConfig, ...colorConfig },
    };
  }, [spec, themeConfig, color, showDataLabels]);

  const [error, setError] = useState<string | null>(null);

  if (error) return <SpecFallback spec={spec} error={error} />;

  return (
    <div className="w-full" style={{ height: 280 }}>
      <VegaEmbed
        spec={sized as any}
        // ast: true uses vega-interpreter (pure-interpreter path) instead of
        // new Function() — prevents expression-injection via transform.calculate
        options={{ actions: false, ast: true }}
        onError={(e: unknown) => setError(String(e))}
      />
    </div>
  );
}

export function SpecFallback({
  spec,
  error,
}: {
  spec: Record<string, unknown>;
  error: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-[0.6875rem] text-[var(--color-text-secondary)]">
      <div className="flex items-center gap-1 text-[var(--color-warning)] mb-1">
        <AlertTriangle className="size-3" />
        <span>Could not render chart</span>
      </div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]" // allow-text-tertiary: collapsed spec toggle is decorative/secondary
      >
        {open ? (
          <ChevronDown className="size-3" />
        ) : (
          <ChevronRight className="size-3" />
        )}
        Show spec
      </button>
      <p className="text-[0.625rem] text-[var(--color-error-text)] mt-1">
        {error.length > 200 ? error.slice(0, 200) + "…" : error}
      </p>
      {open && (
        <pre
          data-testid="spec-json"
          className="mt-1 p-1.5 bg-[var(--color-bg-secondary)] rounded overflow-auto max-h-32 text-[0.625rem]"
        >
          {JSON.stringify(spec, null, 2)}
        </pre>
      )}
    </div>
  );
}

type ChartErrorBoundaryProps = {
  spec: Record<string, unknown>;
  children: ReactNode;
};

type ChartErrorBoundaryState = {
  error: string | null;
};

class ChartErrorBoundary extends Component<
  ChartErrorBoundaryProps,
  ChartErrorBoundaryState
> {
  constructor(props: ChartErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: unknown): ChartErrorBoundaryState {
    return { error: String(error) };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("[ChartErrorBoundary]", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return <SpecFallback spec={this.props.spec} error={this.state.error} />;
    }
    return this.props.children;
  }
}

type ChatArtifactRendererProps = {
  artifact: Artifact;
  viewOverride?: ViewOverride;
  color?: string;
  showDataLabels?: boolean;
};

export function ChatArtifactRenderer({
  artifact,
  viewOverride,
  color,
  showDataLabels,
}: ChatArtifactRendererProps) {
  if (artifact.type !== "visualization") {
    console.debug(
      "[ChatArtifactRenderer] non-visualization artifact skipped",
      artifact.type,
    );
    return null;
  }

  const effectiveSpec = viewOverride
    ? { ...artifact.spec, mark: viewOverride }
    : artifact.spec;

  return (
    <div data-testid="chat-artifact-renderer">
      {/* key resets the boundary when viewOverride changes, allowing a fresh
          render attempt instead of permanently showing the fallback. */}
      <ChartErrorBoundary key={viewOverride ?? ""} spec={effectiveSpec}>
        <VisualizationRenderer
          spec={effectiveSpec}
          color={color}
          showDataLabels={showDataLabels}
        />
      </ChartErrorBoundary>
    </div>
  );
}

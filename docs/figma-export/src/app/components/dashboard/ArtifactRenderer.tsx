import { useEffect, useMemo, useState } from 'react';
import { VegaEmbed } from 'react-vega';
import { AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import type { DashboardArtifactPayload } from './artifactTypes';

// Reads a CSS custom property from :root, returning a fallback if unavailable
// (e.g. during SSR). Called on every render of the visualization renderer so
// the Vega-Lite config reflects light/dark mode changes.
function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function useVegaTheme(deps: unknown[]): Record<string, unknown> {
  // Recompute when the deps change (width/height) or when theme changes are
  // signaled via the MutationObserver below.
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const observer = new MutationObserver(() => setTick((t) => t + 1));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    return () => observer.disconnect();
  }, []);

  return useMemo(() => {
    const category = [
      cssVar('--color-teal-500', '#2EC4B6'),
      cssVar('--color-violet-500', '#6366F1'),
      cssVar('--color-blue-500', '#3B82F6'),
      cssVar('--color-amber-500', '#F59E0B'),
      cssVar('--color-teal-400', '#6AD8CC'),
      cssVar('--color-violet-400', '#818CF8'),
      cssVar('--color-blue-400', '#60A5FA'),
      cssVar('--color-slate-400', '#94A3B8'),
    ];
    const textPrimary = cssVar('--color-text-primary', '#0F172A');
    const textSecondary = cssVar('--color-text-secondary', '#334155');
    const textTertiary = cssVar('--color-text-tertiary', '#64748B');
    const gridColor = cssVar('--color-border-subtle', '#E2E8F0');
    const font = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    return {
      background: 'transparent',
      font,
      padding: 8,
      title: {
        font,
        fontWeight: 600,
        fontSize: 13,
        color: textPrimary,
        anchor: 'start',
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
      view: { stroke: 'transparent' },
      mark: { color: category[0], cornerRadius: 3 },
      bar: { color: category[0], cornerRadiusEnd: 4 },
      line: { color: category[0], strokeWidth: 2.5 },
      area: { color: category[0], opacity: 0.35 },
      point: { fill: category[0], filled: true, size: 80 },
      arc: { fill: category[0], innerRadius: 40, padAngle: 0.02, cornerRadius: 3 },
      rect: { color: category[0] },
      range: {
        category,
        ordinal: { scheme: 'purples' },
        ramp: { scheme: 'purples' },
        heatmap: { scheme: 'purples' },
      },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);
}

export type ViewOverride = 'bar' | 'line' | 'area' | 'point' | 'arc' | 'table';

interface Props {
  artifact: DashboardArtifactPayload;
  viewOverride?: ViewOverride;
  color?: string;
  showDataLabels?: boolean;
  width: number;
  height: number;
}

export function ArtifactRenderer({ artifact, viewOverride, color, showDataLabels, width, height }: Props) {
  if (artifact.type === 'visualization') {
    if (viewOverride === 'table') {
      const derived = tableFromSpec(artifact.spec);
      if (derived) return <TableRenderer columns={derived.columns} rows={derived.rows} />;
    }
    const effectiveSpec =
      viewOverride && viewOverride !== 'table'
        ? { ...artifact.spec, mark: viewOverride }
        : artifact.spec;
    return (
      <VisualizationRenderer
        spec={effectiveSpec}
        color={color}
        showDataLabels={showDataLabels}
        width={width}
        height={height}
      />
    );
  }

  switch (artifact.type) {
    case 'text':
      return <TextRenderer content={artifact.content} />;
    case 'table':
      return <TableRenderer columns={artifact.columns} rows={artifact.rows} />;
    case 'file':
      return <FileRenderer artifact={artifact} />;
  }
}

function applyDataLabels(spec: Record<string, unknown>): Record<string, unknown> {
  const s = spec as {
    layer?: unknown;
    mark?: unknown;
    encoding?: { y?: { field?: string; type?: string }; x?: unknown };
  };
  if (s.layer || !s.mark || !s.encoding) return spec;
  const yField = s.encoding.y?.field;
  if (!yField) return spec;
  const textEncoding = {
    ...s.encoding,
    text: { field: yField, type: s.encoding.y?.type ?? 'quantitative' },
  };
  const { mark, encoding, ...rest } = s as Record<string, unknown>;
  return {
    ...rest,
    layer: [
      { mark, encoding },
      {
        mark: { type: 'text', dy: -6, fontSize: 10, fontWeight: 500 },
        encoding: textEncoding,
      },
    ],
  };
}

function tableFromSpec(spec: Record<string, unknown>): { columns: string[]; rows: Array<Record<string, unknown>> } | null {
  const data = (spec as { data?: { values?: unknown } }).data;
  const values = data?.values;
  if (!Array.isArray(values) || values.length === 0) return null;
  const columns = Array.from(
    values.reduce<Set<string>>((acc, row) => {
      if (row && typeof row === 'object') Object.keys(row).forEach((k) => acc.add(k));
      return acc;
    }, new Set())
  );
  return { columns, rows: values as Array<Record<string, unknown>> };
}

// ─── Visualization ───

function VisualizationRenderer({
  spec,
  color,
  showDataLabels,
  width,
  height,
}: {
  spec: Record<string, unknown>;
  color?: string;
  showDataLabels?: boolean;
  width: number;
  height: number;
}) {
  const themeConfig = useVegaTheme([color ?? '']);
  const sized = useMemo(
    () => {
      const specConfig = (spec as { config?: Record<string, unknown> }).config ?? {};
      const resolvedColor = color ? cssVar(color, '#6366F1') : undefined;
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
      const withLabels = showDataLabels ? applyDataLabels(spec) : spec;
      return {
        ...withLabels,
        $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
        width: Math.max(80, width - 24),
        height: Math.max(60, height - 24),
        autosize: { type: 'fit', contains: 'padding' },
        // Spec-provided config wins over the theme so individual charts can
        // still opt out per-property.
        config: { ...themeConfig, ...colorConfig, ...specConfig },
      };
    },
    [spec, width, height, themeConfig, color, showDataLabels]
  );

  const [error, setError] = useState<string | null>(null);

  if (error) return <SpecFallback spec={spec} error={error} />;

  return (
    <div className="w-full h-full flex items-center justify-center">
      <VegaEmbed
        spec={sized as any}
        options={{ actions: false }}
        onError={(e: unknown) => setError(String(e))}
      />
    </div>
  );
}

function SpecFallback({ spec, error }: { spec: Record<string, unknown>; error: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-[0.6875rem] text-[var(--color-text-secondary)]">
      <div className="flex items-center gap-1 text-[var(--color-warning)] mb-1">
        <AlertTriangle className="size-3" />
        <span>Could not render chart</span>
      </div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
      >
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        Show spec
      </button>
      <p className="text-[0.625rem] text-[var(--color-error-text)] mt-1">{error}</p>
      {open && (
        <pre className="mt-1 p-1.5 bg-[var(--color-bg-secondary)] rounded overflow-auto max-h-32 text-[0.625rem]">
          {JSON.stringify(spec, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── Text ───

function TextRenderer({ content }: { content: string }) {
  return (
    <pre className="whitespace-pre-wrap break-words text-[0.6875rem] leading-snug text-[var(--color-text-secondary)]">
      {content}
    </pre>
  );
}

// ─── Table ───

function TableRenderer({
  columns,
  rows,
}: {
  columns: string[];
  rows: Array<Record<string, unknown>>;
}) {
  return (
    <div className="w-full h-full overflow-auto">
      <table className="w-full border-collapse text-[0.6875rem]">
        <thead className="sticky top-0 bg-[var(--color-bg-secondary)]">
          <tr>
            {columns.map((c) => (
              <th
                key={c}
                className="text-left px-2 py-1 border-b border-[var(--color-border-default)] font-normal text-[var(--color-text-tertiary)]"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((r, i) => (
            <tr key={i} className="border-b border-[var(--color-border-subtle)]">
              {columns.map((c) => (
                <td key={c} className="px-2 py-1 text-[var(--color-text-secondary)] truncate max-w-[8.75rem]">
                  {String(r[c] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── File (fallback) ───

function FileRenderer({ artifact }: { artifact: Extract<DashboardArtifactPayload, { type: 'file' }> }) {
  const { file } = artifact;
  if (file.file_type === 'image' && file.preview_url) {
    return <img src={file.preview_url} alt={file.filename} className="w-full h-full object-contain" />;
  }
  return (
    <div className="flex flex-col gap-1 text-[var(--color-text-secondary)]">
      <span className="truncate">{file.filename}</span>
      <span className="text-[0.625rem] text-[var(--color-text-tertiary)]">
        {file.mime_type} · {(file.size_bytes / 1024).toFixed(1)} KB
      </span>
    </div>
  );
}

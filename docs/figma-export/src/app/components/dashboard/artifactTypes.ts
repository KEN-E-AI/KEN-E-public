import type { OutputFile } from '../../data/automationDetailsData';

// ─── Artifact union ───
// Mirrors the shape in data-visualization.md §3 but extended to the broader
// set of outputs a workflow can produce (not only charts).

export interface ArtifactMetadata {
  title: string;
  description?: string | null;
  dataSource?: string;
  createdAt?: Date | null;
}

export interface VisualizationArtifact {
  type: 'visualization';
  spec: Record<string, unknown>; // Vega-Lite JSON spec
  metadata: ArtifactMetadata & { chartTypeSuggestion?: string };
}

export interface TextArtifact {
  type: 'text';
  content: string;                // plain text or markdown
  metadata: ArtifactMetadata;
}

export interface TableArtifact {
  type: 'table';
  columns: string[];
  rows: Array<Record<string, unknown>>;
  metadata: ArtifactMetadata;
}

export interface FileArtifact {
  type: 'file';
  file: OutputFile;               // fallback for binary/unknown outputs
  metadata: ArtifactMetadata;
}

export type DashboardArtifactPayload =
  | VisualizationArtifact
  | TextArtifact
  | TableArtifact
  | FileArtifact;

// ─── Adapter: OutputFile → DashboardArtifactPayload ───
// Workflow tasks currently emit OutputFile instances. Agents calling
// create_visualization() will eventually emit VisualizationArtifacts directly.
// Until then, we derive the payload from file_type / content_preview.

export function toArtifactPayload(file: OutputFile, title: string): DashboardArtifactPayload {
  const metadata: ArtifactMetadata = {
    title,
    createdAt: file.created_at,
  };

  // Vega-Lite specs may arrive as file_type 'visualization' (task output
  // declared as such) or as 'json' whose $schema identifies it as Vega-Lite
  // (agent-produced via create_visualization()).
  if ((file.file_type === 'visualization' || file.file_type === 'json') && file.content_preview) {
    try {
      const parsed = JSON.parse(file.content_preview);
      if (file.file_type === 'visualization' || isVegaLiteSpec(parsed)) {
        return {
          type: 'visualization',
          spec: parsed,
          metadata: {
            ...metadata,
            chartTypeSuggestion: typeof parsed.mark === 'string' ? parsed.mark : undefined,
          },
        };
      }
    } catch {
      // fall through — treat as generic file
    }
  }

  if (file.file_type === 'text' && file.content_preview != null) {
    return { type: 'text', content: file.content_preview, metadata };
  }

  if (file.file_type === 'csv' && file.content_preview) {
    const parsed = parseCsv(file.content_preview);
    if (parsed) return { type: 'table', ...parsed, metadata };
  }

  return { type: 'file', file, metadata };
}

function isVegaLiteSpec(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object') return false;
  const schema = (value as Record<string, unknown>).$schema;
  return typeof schema === 'string' && schema.includes('vega-lite');
}

function parseCsv(content: string): { columns: string[]; rows: Array<Record<string, unknown>> } | null {
  const lines = content.trim().split(/\r?\n/);
  if (lines.length < 2) return null;
  const columns = lines[0].split(',').map((c) => c.trim());
  const rows = lines.slice(1).map((line) => {
    const cells = line.split(',');
    const row: Record<string, unknown> = {};
    columns.forEach((col, i) => (row[col] = cells[i]?.trim() ?? ''));
    return row;
  });
  return { columns, rows };
}

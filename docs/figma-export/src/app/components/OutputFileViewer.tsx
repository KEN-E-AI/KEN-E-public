import { useMemo } from 'react';
import {
  X,
  Download,
  Image,
  FileText,
  FileJson,
  FileSpreadsheet,
  Code,
  Film,
  Music,
  File,
} from 'lucide-react';
import { Button } from './ui/button';
import type { OutputFile, OutputFileType } from '../data/automationDetailsData';
import { FILE_TYPE_LABELS } from '../data/automationDetailsData';

const FILE_TYPE_ICONS: Record<OutputFileType, React.ComponentType<{ className?: string }>> = {
  image: Image,
  document: FileText,
  csv: FileSpreadsheet,
  json: FileJson,
  text: FileText,
  html: Code,
  video: Film,
  audio: Music,
  other: File,
};

const FILE_TYPE_COLORS: Record<OutputFileType, string> = {
  image: 'var(--color-teal-500)',
  document: 'var(--color-violet-500)',
  csv: 'var(--color-success)',
  json: 'var(--color-warning)',
  text: 'var(--color-info)',
  html: 'var(--color-error)',
  video: 'var(--color-violet-500)',
  audio: 'var(--color-teal-500)',
  other: 'var(--color-text-tertiary)',
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function parseCsvToTable(csv: string): { headers: string[]; rows: string[][] } {
  const lines = csv.trim().split('\n');
  if (lines.length === 0) return { headers: [], rows: [] };

  const parseLine = (line: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') {
        inQuotes = !inQuotes;
      } else if (c === ',' && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += c;
      }
    }
    result.push(current.trim());
    return result;
  };

  const headers = parseLine(lines[0]);
  const rows = lines.slice(1, 21).map(parseLine); // max 20 rows
  return { headers, rows };
}

function tryFormatJson(str: string): string {
  try {
    return JSON.stringify(JSON.parse(str), null, 2);
  } catch {
    return str;
  }
}

interface OutputFileViewerProps {
  file: OutputFile;
  onClose: () => void;
}

export function OutputFileViewer({ file, onClose }: OutputFileViewerProps) {
  const Icon = FILE_TYPE_ICONS[file.file_type] || File;
  const color = FILE_TYPE_COLORS[file.file_type] || 'var(--color-text-tertiary)';

  const csvData = useMemo(() => {
    if (file.file_type === 'csv' && file.content_preview) {
      return parseCsvToTable(file.content_preview);
    }
    return null;
  }, [file]);

  const formattedJson = useMemo(() => {
    if (file.file_type === 'json' && file.content_preview) {
      return tryFormatJson(file.content_preview);
    }
    return null;
  }, [file]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 bg-card rounded-[var(--radius-lg)] border border-[var(--color-border-default)] shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-default)]">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-8 h-8 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0"
              style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` }}
            >
              <Icon className="size-4" style={{ color }} />
            </div>
            <div className="min-w-0">
              <p className="text-sm truncate">{file.filename}</p>
              <div className="flex items-center gap-3 mt-0.5">
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{
                    backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
                    color,
                  }}
                >
                  {FILE_TYPE_LABELS[file.file_type]}
                </span>
                <span className="text-[10px] text-[var(--color-text-tertiary)]">
                  {formatBytes(file.size_bytes)}
                </span>
                <span className="text-[10px] text-[var(--color-text-tertiary)]">
                  {formatDate(file.created_at)}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-tertiary)]"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {/* Image */}
          {file.file_type === 'image' && file.preview_url && (
            <div className="flex items-center justify-center">
              <img
                src={file.preview_url}
                alt={file.filename}
                className="max-w-full max-h-[60vh] rounded-[var(--radius-md)] object-contain"
              />
            </div>
          )}

          {/* CSV */}
          {file.file_type === 'csv' && csvData && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr>
                    {csvData.headers.map((h, i) => (
                      <th
                        key={i}
                        className="text-left p-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border-subtle)] text-[var(--color-text-secondary)] whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {csvData.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td
                          key={ci}
                          className="p-2 border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] whitespace-nowrap"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {csvData.rows.length >= 20 && (
                <p className="text-[10px] text-[var(--color-text-tertiary)] mt-2 text-center">
                  Showing first 20 rows
                </p>
              )}
            </div>
          )}

          {/* JSON */}
          {file.file_type === 'json' && formattedJson && (
            <pre className="text-xs font-mono bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] p-4 overflow-x-auto whitespace-pre text-[var(--color-text-primary)]">
              {formattedJson}
            </pre>
          )}

          {/* Text */}
          {file.file_type === 'text' && file.content_preview && (
            <div className="bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] p-4">
              <pre className="text-xs font-mono whitespace-pre-wrap text-[var(--color-text-primary)]">
                {file.content_preview}
              </pre>
            </div>
          )}

          {/* HTML */}
          {file.file_type === 'html' && file.content_preview && (
            <pre className="text-xs font-mono bg-[var(--color-bg-secondary)] rounded-[var(--radius-md)] p-4 overflow-x-auto whitespace-pre text-[var(--color-text-primary)]">
              {file.content_preview}
            </pre>
          )}

          {/* Fallback for types without preview */}
          {!file.content_preview && !file.preview_url && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Icon className="size-12 text-[var(--color-text-tertiary)] mb-3" />
              <p className="text-sm text-[var(--color-text-secondary)]">
                Preview not available for this file type
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                {file.filename} ({formatBytes(file.size_bytes)})
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-[var(--color-border-default)]">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button size="sm" className="gap-1.5" disabled>
            <Download className="size-3.5" />
            Download
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Compact file list item (used in panels) ───

interface OutputFileItemProps {
  file: OutputFile;
  onClick: () => void;
}

export function OutputFileItem({ file, onClick }: OutputFileItemProps) {
  const Icon = FILE_TYPE_ICONS[file.file_type] || File;
  const color = FILE_TYPE_COLORS[file.file_type] || 'var(--color-text-tertiary)';

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2.5 p-2 rounded-[var(--radius-sm)] border border-[var(--color-border-subtle)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-secondary)] transition-colors text-left group"
    >
      <div
        className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0"
        style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` }}
      >
        <Icon className="size-3.5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] truncate text-[var(--color-text-primary)] group-hover:text-[var(--color-violet-500)]">
          {file.filename}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[9px] text-[var(--color-text-tertiary)]">
            {FILE_TYPE_LABELS[file.file_type]}
          </span>
          <span className="text-[9px] text-[var(--color-text-tertiary)]">
            {formatBytes(file.size_bytes)}
          </span>
        </div>
      </div>
      {file.file_type === 'image' && file.preview_url && (
        <img
          src={file.preview_url}
          alt=""
          className="w-8 h-8 rounded-[var(--radius-sm)] object-cover shrink-0"
        />
      )}
    </button>
  );
}

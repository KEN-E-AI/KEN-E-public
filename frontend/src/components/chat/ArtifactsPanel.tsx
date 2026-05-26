import { FileText, FileSpreadsheet, FileImage, FileCode, Bot } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ChatSessionId, ListArtifactsResponseItem } from "@/lib/chatApi";
import { useArtifacts } from "@/hooks/useArtifacts";

type DocType = "pdf" | "spreadsheet" | "image" | "code" | "text";

function mimeToDocType(mime: string): DocType {
  if (mime === "application/pdf") return "pdf";
  if (mime.startsWith("image/")) return "image";
  if (
    mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    mime === "application/vnd.ms-excel" ||
    mime === "text/csv"
  )
    return "spreadsheet";
  if (
    mime.startsWith("application/json") ||
    mime.startsWith("application/xml") ||
    [
      "text/javascript",
      "text/typescript",
      "text/x-python",
      "text/x-java",
      "text/html",
      "text/css",
      "text/xml",
    ].some((t) => mime.startsWith(t))
  )
    return "code";
  return "text";
}

const DOC_ICONS: Record<DocType, typeof FileText> = {
  pdf: FileText,
  spreadsheet: FileSpreadsheet,
  image: FileImage,
  code: FileCode,
  text: FileText,
};

const DOC_COLORS: Record<DocType, string> = {
  pdf: "var(--color-error)",
  spreadsheet: "var(--color-success)",
  image: "var(--color-violet-500)",
  code: "var(--color-blue-500)",
  text: "var(--color-slate-500)",
};

function formatBytes(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(0)} KB`;
  return `${bytes} B`;
}

type ArtifactRowProps = {
  item: ListArtifactsResponseItem;
};

function ArtifactRow({ item }: ArtifactRowProps) {
  const { artifact_index, signed_url } = item;
  const docType = mimeToDocType(artifact_index.mime_type);
  const Icon = DOC_ICONS[docType];
  const color = DOC_COLORS[docType];

  const keneBadge = (
    <Badge variant="default">
      <span className="flex items-center gap-1">
        <Bot className="size-3" aria-hidden="true" />
        KEN-E
      </span>
    </Badge>
  );

  return (
    <a
      href={signed_url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "flex items-center gap-3 p-2.5 rounded-[var(--radius-md)]",
        "border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)]",
        "hover:border-[var(--color-violet-300)] transition-all",
      )}
      style={{
        transitionTimingFunction: "var(--ease-default)",
        transitionDuration: "var(--duration-fast)",
      }}
      aria-label={artifact_index.filename}
    >
      <div
        className="size-8 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0"
        style={{
          backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
          color,
        }}
      >
        <Icon className="size-4" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[var(--text-body-sm)] font-medium truncate">
          {artifact_index.filename}
        </p>
        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
          {formatBytes(artifact_index.size_bytes)}
        </p>
      </div>
      {artifact_index.created_by_tool != null ? (
        <Tooltip>
          <TooltipTrigger asChild>{keneBadge}</TooltipTrigger>
          <TooltipContent>
            <p>Created by: {artifact_index.created_by_tool}</p>
          </TooltipContent>
        </Tooltip>
      ) : (
        keneBadge
      )}
    </a>
  );
}

type ArtifactsPanelProps = {
  sessionId: ChatSessionId | null;
};

export function ArtifactsPanel({ sessionId }: ArtifactsPanelProps) {
  const { data, isLoading, isError } = useArtifacts(sessionId);

  if (sessionId == null) return null;

  return (
    <TooltipProvider>
      <Card
        className="p-5"
        accentColor="var(--color-accent-slot-4)"
        data-testid="artifacts-panel"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText
              className="size-4 text-[var(--color-amber-500)]"
              aria-hidden="true"
            />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Documents
            </h3>
            {!isLoading && !isError && data && (
              <Badge variant="neutral">{data.items.length}</Badge>
            )}
          </div>
        </div>

        {isLoading && (
          <div className="space-y-2" aria-label="Loading artifacts">
            <Skeleton className="h-12 w-full rounded-[var(--radius-md)]" />
            <Skeleton className="h-12 w-full rounded-[var(--radius-md)]" />
          </div>
        )}

        {isError && (
          <p className="text-[var(--text-caption)] text-[var(--color-error-text)]">
            Failed to load documents.
          </p>
        )}

        {!isLoading && !isError && data && data.items.length === 0 && (
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
            No documents yet.
          </p>
        )}

        {!isLoading && !isError && data && data.items.length > 0 && (
          <div className="space-y-2">
            {data.items.map((item) => (
              <ArtifactRow key={item.artifact_index.artifact_id} item={item} />
            ))}
          </div>
        )}
      </Card>
    </TooltipProvider>
  );
}

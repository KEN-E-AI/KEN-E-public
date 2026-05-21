import { File, FileText, Image, Sheet } from "lucide-react";
import { cn } from "@/lib/utils";

type ArtifactBlockProps = {
  filename: string;
  mime_type?: string;
};

function resolveIcon(
  mime_type: string | undefined,
): React.ComponentType<{ className?: string }> {
  if (!mime_type) return File;
  if (mime_type.startsWith("image/")) return Image;
  if (mime_type === "application/pdf") return FileText;
  if (
    mime_type ===
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    mime_type === "text/csv" ||
    mime_type === "application/vnd.ms-excel"
  )
    return Sheet;
  return File;
}

export function ArtifactBlock({ filename, mime_type }: ArtifactBlockProps) {
  const Icon = resolveIcon(mime_type);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Artifact: ${filename} (preview coming soon)`}
      onClick={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
        }
      }}
      className={cn(
        "inline-flex items-center gap-2.5 px-3 py-2 cursor-default select-none",
        "rounded-[var(--radius-md)] border border-[var(--color-border-default)]",
        "bg-[var(--color-bg-primary)]",
        "max-w-xs",
      )}
    >
      <Icon className="size-4 shrink-0 text-[var(--color-text-secondary)]" />
      <div className="min-w-0 flex-1">
        <p className="text-sm truncate text-[var(--color-text-primary)]">
          {filename}
        </p>
        <p className="text-xs text-[var(--color-text-tertiary)]">
          Click to view (coming soon)
        </p>
      </div>
    </div>
  );
}

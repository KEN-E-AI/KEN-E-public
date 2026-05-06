import type { EmptyStateProps } from "../types";

/**
 * Consistent empty state component for knowledge graph sections
 */
export function EmptyState({ message, height }: EmptyStateProps) {
  return (
    <div
      className={`p-6 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border-default)] flex items-center justify-center ${height || ""}`}
    >
      <p className="text-[var(--color-text-tertiary)] text-center">{message}</p>
    </div>
  );
}

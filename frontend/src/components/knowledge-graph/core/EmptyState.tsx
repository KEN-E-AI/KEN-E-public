import type { EmptyStateProps } from "../types";

/**
 * Consistent empty state component for knowledge graph sections
 */
export function EmptyState({ message, height }: EmptyStateProps) {
  return (
    <div
      className={`p-6 bg-dashboard-gray-50 rounded-lg border border-dashboard-gray-200 flex items-center justify-center ${height || ""}`}
    >
      <p className="text-dashboard-gray-500 text-center">{message}</p>
    </div>
  );
}

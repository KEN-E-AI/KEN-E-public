import type React from "react";

interface BorderedSectionProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Bordered container section for nested content within cards
 * Used in Competitors page for child sections within main card
 */
export function BorderedSection({
  children,
  className = "",
}: BorderedSectionProps) {
  return (
    <div className={`rounded-lg border bg-card shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

import { cn } from "@/lib/utils";

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "animate-pulse rounded-[var(--radius-md)] bg-[var(--color-surface-muted)]",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };

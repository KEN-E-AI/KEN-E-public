import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "./utils";

const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-[var(--radius-pill)] px-3.5 py-0.5 text-[var(--text-overline)] font-bold w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none transition-all overflow-hidden",
  {
    variants: {
      variant: {
        success:
          "bg-[var(--color-success-bg)] text-[var(--color-success-text)] border-0",
        error:
          "bg-[var(--color-error-bg)] text-[var(--color-error-text)] border-0",
        warning:
          "bg-[var(--color-warning-bg)] text-[var(--color-warning-text)] border-0",
        info:
          "bg-[var(--color-info-bg)] text-[var(--color-info-text)] border-0",
        disconnected:
          "bg-[var(--color-disconnected-bg)] text-[var(--color-disconnected)] border-0",
        neutral:
          "bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] border-0",
        default:
          "bg-[var(--color-violet-100)] text-[var(--color-violet-500)] border-0",
        outline:
          "text-foreground border border-[var(--color-border-default)] bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

const Badge = React.forwardRef<
  HTMLSpanElement,
  React.ComponentProps<"span"> &
    VariantProps<typeof badgeVariants> & { asChild?: boolean }
>(({ className, variant, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "span";

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      ref={ref}
      {...props}
    />
  );
});

Badge.displayName = "Badge";

export { Badge, badgeVariants };

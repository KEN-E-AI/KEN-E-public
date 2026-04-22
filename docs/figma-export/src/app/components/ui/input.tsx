import * as React from "react";

import { cn } from "./utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "file:text-foreground placeholder:text-[var(--color-text-tertiary)] selection:bg-[var(--color-violet-500)] selection:text-[var(--color-text-inverse)]",
        "flex h-9 w-full min-w-0 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-3 text-[var(--text-body-md)] text-[var(--color-text-primary)]",
        "transition-all outline-none",
        "focus-visible:border-[var(--color-violet-500)] focus-visible:shadow-[0_0_0_3px_var(--color-violet-100)]",
        "aria-invalid:border-[var(--color-error)] aria-invalid:shadow-[0_0_0_3px_var(--color-coral-100)]",
        "disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:border-[var(--color-border-subtle)] disabled:cursor-not-allowed",
        "file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      style={{
        transitionTimingFunction: 'var(--ease-default)',
        transitionDuration: 'var(--duration-fast)',
      }}
      {...props}
    />
  );
}

export { Input };

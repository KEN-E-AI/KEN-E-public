import * as React from "react";

import { cn } from "./utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "resize-none placeholder:text-[var(--color-text-tertiary)] selection:bg-[var(--color-violet-500)] selection:text-[var(--color-text-inverse)]",
        "flex field-sizing-content min-h-16 w-full rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-3 text-[var(--text-body-md)] text-[var(--color-text-primary)]",
        "transition-all outline-none",
        "focus-visible:border-[var(--color-violet-500)] focus-visible:shadow-[0_0_0_3px_var(--color-violet-100)]",
        "aria-invalid:border-[var(--color-error)] aria-invalid:shadow-[0_0_0_3px_var(--color-coral-100)]",
        "disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:border-[var(--color-border-subtle)] disabled:cursor-not-allowed",
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

export { Textarea };

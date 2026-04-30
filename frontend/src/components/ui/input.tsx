import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        data-slot="input"
        className={cn(
          "file:text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)]",
          "flex h-9 w-full min-w-0 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-3 text-[var(--text-body-md)] text-[var(--color-text-primary)]",
          "transition-all outline-none",
          "focus-visible:border-[var(--color-violet-500)] focus-visible:shadow-[0_0_0_3px_var(--color-violet-100)]",
          "aria-invalid:border-[var(--color-error)] aria-invalid:shadow-[0_0_0_3px_var(--color-error-bg)]",
          "disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:border-[var(--color-border-subtle)] disabled:cursor-not-allowed",
          "file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
          className,
        )}
        style={{
          transitionTimingFunction: "var(--ease-default)",
          transitionDuration: "var(--duration-fast)",
        }}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };

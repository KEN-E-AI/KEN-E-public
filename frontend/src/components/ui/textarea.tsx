import * as React from "react";

import { cn } from "@/lib/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        data-slot="textarea"
        className={cn(
          "placeholder:text-[var(--color-text-tertiary)]",
          "flex min-h-[80px] w-full rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-2 text-[var(--text-body-md)] text-[var(--color-text-primary)]",
          "transition-all outline-none resize-y",
          "focus-visible:border-[var(--color-violet-500)] focus-visible:shadow-[0_0_0_3px_var(--color-violet-100)]",
          "aria-invalid:border-[var(--color-error)] aria-invalid:shadow-[0_0_0_3px_var(--color-error-bg)]",
          "disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:border-[var(--color-border-subtle)] disabled:cursor-not-allowed disabled:resize-none",
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
Textarea.displayName = "Textarea";

export { Textarea };

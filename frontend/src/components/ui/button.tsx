import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-bold text-[var(--text-body-md)] transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] border-2 border-[var(--color-violet-500)] shadow-[var(--shadow-color-violet)] hover:-translate-y-0.5 active:translate-y-0 disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:shadow-none disabled:transform-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)]",
        gradient:
          "bg-[image:var(--gradient-cta)] text-[var(--color-text-inverse)] border-0 shadow-[var(--shadow-color-violet)] hover:-translate-y-0.5 active:translate-y-0 disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:shadow-none disabled:transform-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)]",
        destructive:
          "bg-[var(--color-error)] text-[var(--color-text-inverse)] border-2 border-[var(--color-error)] shadow-[var(--shadow-color-violet)] hover:-translate-y-0.5 active:translate-y-0 disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:shadow-none disabled:transform-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-error)]",
        outline:
          "bg-transparent text-[var(--color-text-secondary)] border-2 border-[var(--color-border-default)] hover:border-[var(--color-violet-300)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5 active:translate-y-0 disabled:text-[var(--color-text-disabled)] disabled:border-[var(--color-border-subtle)] disabled:transform-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)]",
        secondary:
          "bg-[var(--color-teal-500)] text-[var(--color-text-inverse)] border-2 border-[var(--color-teal-500)] shadow-[var(--shadow-color-teal)] hover:-translate-y-0.5 active:translate-y-0 disabled:bg-[var(--color-surface-muted)] disabled:text-[var(--color-text-disabled)] disabled:shadow-none disabled:transform-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-teal-300)]",
        ghost:
          "hover:bg-[var(--color-violet-100)] hover:text-[var(--color-violet-500)] text-[var(--color-text-tertiary)] disabled:text-[var(--color-text-disabled)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)]",
        link: "text-[var(--color-violet-500)] underline-offset-4 hover:underline disabled:text-[var(--color-text-disabled)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)]",
      },
      size: {
        default: "h-9 px-4 py-2 rounded-[var(--radius-md)] has-[>svg]:px-3",
        sm: "h-8 rounded-[var(--radius-md)] gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-[var(--radius-md)] px-6 has-[>svg]:px-4",
        icon: "size-9 rounded-[var(--radius-md)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        data-slot="button"
        className={cn(buttonVariants({ variant, size, className }))}
        style={{
          transitionTimingFunction: "var(--ease-bounce)",
          transitionDuration: "var(--duration-fast)",
        }}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };

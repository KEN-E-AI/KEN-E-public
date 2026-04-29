import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-[var(--radius-lg)] border-2 p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-bg-elevated)] border-[var(--color-border-default)] text-[var(--color-text-primary)]",
        destructive:
          "bg-[var(--color-error-bg)] border-[var(--color-error)] text-[var(--color-error-text)] [&>svg]:text-[var(--color-error)]",
        success:
          "bg-[var(--color-success-bg)] border-[var(--color-success)] text-[var(--color-success-text)] [&>svg]:text-[var(--color-success)]",
        warning:
          "bg-[var(--color-warning-bg)] border-[var(--color-warning)] text-[var(--color-warning-text)] [&>svg]:text-[var(--color-warning)]",
        info: "bg-[var(--color-info-bg)] border-[var(--color-info)] text-[var(--color-info-text)] [&>svg]:text-[var(--color-info)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    data-slot="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props}
  />
));
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    data-slot="alert-title"
    className={cn(
      "mb-1 font-semibold leading-none tracking-tight text-[var(--text-body-md)]",
      className,
    )}
    {...props}
  />
));
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="alert-description"
    className={cn(
      "text-[var(--text-body-md)] [&_p]:leading-relaxed opacity-90",
      className,
    )}
    {...props}
  />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };

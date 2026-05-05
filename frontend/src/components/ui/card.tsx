import * as React from "react";

import { cn } from "@/lib/utils";

const ACCENT_COLOR_RE =
  /^(#[0-9a-fA-F]{3,8}|(rgb|hsl)a?\([^)]*\)|var\(--[\w-]+\))$/;

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { accentColor?: string }
>(({ className, accentColor, style, ...props }, ref) => {
  const safeAccentColor =
    accentColor && ACCENT_COLOR_RE.test(accentColor) ? accentColor : undefined;
  // Strip guarded style keys so callers cannot bypass the accentColor guard
  // by passing borderLeftColor / borderLeftWidth directly via the style prop.
  const {
    borderLeftColor: _blc,
    borderLeftWidth: _blw,
    ...safeStyle
  } = style ?? {};
  return (
    <div
      ref={ref}
      data-slot="card"
      className={cn(
        "bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] flex flex-col gap-6 rounded-[var(--radius-xl)] border-2 border-[var(--color-border-default)] transition-all shadow-[var(--shadow-md)] hover:shadow-[var(--shadow-lg)] hover:-translate-y-1 hover:border-[var(--color-violet-300)]",
        className,
      )}
      style={{
        borderLeftWidth: safeAccentColor ? "var(--border-accent)" : undefined,
        borderLeftColor: safeAccentColor,
        transitionTimingFunction: "var(--ease-bounce)",
        transitionDuration: "var(--duration-default)",
        ...safeStyle,
      }}
      {...props}
    />
  );
});
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="card-header"
    className={cn(
      "@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 pt-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6",
      className,
    )}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    data-slot="card-title"
    className={cn(
      "leading-none font-bold text-[var(--text-heading-md)]",
      className,
    )}
    style={{ fontFamily: "var(--font-display)" }}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    data-slot="card-description"
    className={cn(
      "text-[var(--color-text-secondary)] text-[var(--text-body-md)]",
      className,
    )}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

const CardAction = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="card-action"
    className={cn(
      "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
      className,
    )}
    {...props}
  />
));
CardAction.displayName = "CardAction";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="card-content"
    className={cn("px-6 [&:last-child]:pb-6", className)}
    {...props}
  />
));
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="card-footer"
    className={cn("flex items-center px-6 pb-6 [.border-t]:pt-6", className)}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
};

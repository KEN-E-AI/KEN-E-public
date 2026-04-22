import * as React from "react";

import { cn } from "./utils";

interface CardProps extends React.ComponentProps<"div"> {
  accentColor?: string;
}

function Card({ className, accentColor, style, ...props }: CardProps) {
  return (
    <div
      data-slot="card"
      className={cn(
        "bg-[var(--color-bg-elevated)] text-card-foreground flex flex-col gap-6 rounded-[var(--radius-xl)] border-2 border-[var(--color-border-default)] transition-all shadow-[var(--shadow-md)]",
        "hover:shadow-[var(--shadow-lg)] hover:-translate-y-1 hover:border-[var(--color-violet-300)]",
        className,
      )}
      style={{
        borderLeftWidth: accentColor ? 'var(--border-accent)' : undefined,
        borderLeftColor: accentColor,
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-default)',
        ...style,
      }}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 pt-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6",
        className,
      )}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <h4
      data-slot="card-title"
      className={cn("leading-none font-bold text-[var(--text-heading-md)]", className)}
      style={{ fontFamily: 'var(--font-display)' }}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-[var(--color-text-secondary)] text-[var(--text-body-md)]", className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
        className,
      )}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("px-6 [&:last-child]:pb-6", className)}
      {...props}
    />
  );
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center px-6 pb-6 border-t-2 border-dashed border-[var(--color-border-default)] [.border-t]:pt-6", className)}
      {...props}
    />
  );
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
};
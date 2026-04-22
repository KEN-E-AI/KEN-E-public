"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "./utils";

function Tabs({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  );
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "inline-flex w-fit items-center justify-center gap-2 flex mb-8",
        className,
      )}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-[var(--radius-pill)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-5 py-2.5 text-[var(--text-body-sm)] font-bold text-[var(--color-text-tertiary)] whitespace-nowrap transition-all",
        "hover:border-[var(--color-teal-300)] hover:text-[var(--color-teal-500)] hover:-translate-y-0.5",
        "data-[state=active]:bg-[var(--color-teal-500)] data-[state=active]:text-[var(--color-text-inverse)] data-[state=active]:border-[var(--color-teal-500)] data-[state=active]:shadow-[var(--shadow-color-teal)]",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-500)]",
        "disabled:pointer-events-none disabled:opacity-50",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      style={{
        transitionTimingFunction: 'var(--ease-bounce)',
        transitionDuration: 'var(--duration-default)',
      }}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
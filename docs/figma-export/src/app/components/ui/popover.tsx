"use client";

import * as React from "react";

import { cn } from "./utils";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface PopoverContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
  contentRef: React.RefObject<HTMLDivElement | null>;
}

const PopoverContext = React.createContext<PopoverContextValue | null>(null);

function usePopoverContext() {
  const ctx = React.useContext(PopoverContext);
  if (!ctx)
    throw new Error("Popover components must be used within <Popover>");
  return ctx;
}

// ---------------------------------------------------------------------------
// Slot utility – lightweight asChild support
// ---------------------------------------------------------------------------
function mergeRefs(
  ...refs: (React.Ref<any> | undefined)[]
): React.RefCallback<any> {
  return (node) => {
    refs.forEach((ref) => {
      if (typeof ref === "function") ref(node);
      else if (ref && typeof ref === "object")
        (ref as React.MutableRefObject<any>).current = node;
    });
  };
}

const Slot = React.forwardRef<any, { children: React.ReactNode } & Record<string, any>>(
  ({ children, ...props }, forwardedRef) => {
    if (!React.isValidElement(children)) return null;
    const childProps = (children as React.ReactElement<any>).props as Record<
      string,
      any
    >;
    const merged: Record<string, any> = { ...props };
    for (const key of Object.keys(childProps)) {
      if (key === "className" || key === "ref") continue;
      if (
        key.startsWith("on") &&
        typeof props[key] === "function" &&
        typeof childProps[key] === "function"
      ) {
        const parentHandler = props[key];
        const childHandler = childProps[key];
        merged[key] = (...args: any[]) => {
          childHandler(...args);
          parentHandler(...args);
        };
      } else if (!(key in merged)) {
        merged[key] = childProps[key];
      }
    }
    merged.className = cn(props.className, childProps.className);
    const childRef = (children as any).ref;
    merged.ref = mergeRefs(forwardedRef, childRef);
    return React.cloneElement(children as React.ReactElement<any>, merged);
  }
);

Slot.displayName = "Slot";

// ---------------------------------------------------------------------------
// Popover (Root)
// ---------------------------------------------------------------------------
interface PopoverProps {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  modal?: boolean;
}

function Popover({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: PopoverProps) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  // Close on outside click
  React.useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        triggerRef.current &&
        !triggerRef.current.contains(target) &&
        contentRef.current &&
        !contentRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open, setOpen]);

  // Close on Escape
  React.useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, setOpen]);

  const ctx = React.useMemo<PopoverContextValue>(
    () => ({ open, setOpen, triggerRef, contentRef }),
    [open, setOpen],
  );

  return (
    <PopoverContext.Provider value={ctx}>
      <div
        data-slot="popover"
        style={{ position: "relative", display: "inline-block" }}
      >
        {children}
      </div>
    </PopoverContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// PopoverTrigger
// ---------------------------------------------------------------------------
interface PopoverTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

const PopoverTrigger = React.forwardRef<
  HTMLButtonElement,
  PopoverTriggerProps
>(({ asChild, children, onClick, ...props }, ref) => {
  const { open, setOpen, triggerRef } = usePopoverContext();

  const composedRef = React.useCallback(
    (node: HTMLButtonElement | null) => {
      (
        triggerRef as React.MutableRefObject<HTMLButtonElement | null>
      ).current = node;
      if (typeof ref === "function") ref(node);
      else if (ref)
        (ref as React.MutableRefObject<HTMLButtonElement | null>).current =
          node;
    },
    [ref, triggerRef],
  );

  const sharedProps: Record<string, any> = {
    ref: composedRef,
    "data-slot": "popover-trigger",
    "data-state": open ? "open" : "closed",
    "aria-expanded": open,
    onClick: (e: React.MouseEvent) => {
      setOpen(!open);
      (onClick as any)?.(e);
    },
    ...props,
  };

  if (asChild && React.isValidElement(children)) {
    return <Slot {...sharedProps}>{children}</Slot>;
  }

  return (
    <button type="button" {...sharedProps}>
      {children}
    </button>
  );
});

PopoverTrigger.displayName = "PopoverTrigger";

// ---------------------------------------------------------------------------
// PopoverContent
// ---------------------------------------------------------------------------
interface PopoverContentProps extends React.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end";
  sideOffset?: number;
  side?: "top" | "right" | "bottom" | "left";
  alignOffset?: number;
  avoidCollisions?: boolean;
  collisionBoundary?: any;
  collisionPadding?: any;
  sticky?: string;
  hideWhenDetached?: boolean;
  onOpenAutoFocus?: (e: Event) => void;
  onCloseAutoFocus?: (e: Event) => void;
  onEscapeKeyDown?: (e: KeyboardEvent) => void;
  onPointerDownOutside?: (e: PointerEvent) => void;
  onInteractOutside?: (e: Event) => void;
  forceMount?: boolean;
}

function PopoverContent({
  className,
  children,
  align = "center",
  sideOffset = 4,
  side = "bottom",
  alignOffset: _ao,
  avoidCollisions: _ac,
  collisionBoundary: _cb,
  collisionPadding: _cp,
  sticky: _s,
  hideWhenDetached: _hwd,
  onOpenAutoFocus: _oaf,
  onCloseAutoFocus: _ocaf,
  onEscapeKeyDown: _oekd,
  onPointerDownOutside: _opdo,
  onInteractOutside: _oio,
  forceMount: _fm,
  ...props
}: PopoverContentProps) {
  const { open, contentRef } = usePopoverContext();

  if (!open) return null;

  const positionStyles: React.CSSProperties = {
    position: "absolute",
    zIndex: 50,
  };

  if (side === "bottom") {
    positionStyles.top = `calc(100% + ${sideOffset}px)`;
  } else if (side === "top") {
    positionStyles.bottom = `calc(100% + ${sideOffset}px)`;
  } else if (side === "right") {
    positionStyles.left = `calc(100% + ${sideOffset}px)`;
    positionStyles.top = 0;
  } else if (side === "left") {
    positionStyles.right = `calc(100% + ${sideOffset}px)`;
    positionStyles.top = 0;
  }

  if (side === "bottom" || side === "top") {
    if (align === "start") positionStyles.left = 0;
    else if (align === "end") positionStyles.right = 0;
    else {
      positionStyles.left = "50%";
      positionStyles.transform = "translateX(-50%)";
    }
  }

  return (
    <div
      ref={contentRef}
      data-slot="popover-content"
      data-state="open"
      data-side={side}
      style={positionStyles}
      className={cn(
        "bg-popover text-popover-foreground animate-in fade-in-0 zoom-in-95 z-50 w-72 rounded-md border p-4 shadow-md outline-hidden",
        side === "bottom" && "slide-in-from-top-2",
        side === "top" && "slide-in-from-bottom-2",
        side === "left" && "slide-in-from-right-2",
        side === "right" && "slide-in-from-left-2",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PopoverClose
// ---------------------------------------------------------------------------
interface PopoverCloseProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

function PopoverClose({
  asChild,
  children,
  onClick,
  ...props
}: PopoverCloseProps) {
  const { setOpen } = usePopoverContext();

  const closeProps: Record<string, any> = {
    "data-slot": "popover-close",
    onClick: (e: React.MouseEvent) => {
      setOpen(false);
      (onClick as any)?.(e);
    },
    ...props,
  };

  if (asChild && React.isValidElement(children)) {
    return <Slot {...closeProps}>{children}</Slot>;
  }

  return (
    <button type="button" {...closeProps}>
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// PopoverPortal – no-op (avoids sandbox SecurityError)
// ---------------------------------------------------------------------------
function PopoverPortal({
  children,
}: {
  children: React.ReactNode;
  container?: HTMLElement | null;
  forceMount?: true;
}) {
  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// PopoverAnchor (no-op — rarely used)
// ---------------------------------------------------------------------------
function PopoverAnchor({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="popover-anchor"
      className={className}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export { Popover, PopoverTrigger, PopoverContent, PopoverAnchor, PopoverClose, PopoverPortal };
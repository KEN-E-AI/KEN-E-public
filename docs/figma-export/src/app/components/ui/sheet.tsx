"use client";

import * as React from "react";
import { XIcon } from "lucide-react";

import { cn } from "./utils";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface SheetContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const SheetContext = React.createContext<SheetContextValue | null>(null);

function useSheetContext() {
  const ctx = React.useContext(SheetContext);
  if (!ctx)
    throw new Error("Sheet components must be used within <Sheet>");
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
// Sheet (Root)
// ---------------------------------------------------------------------------
interface SheetProps {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  modal?: boolean;
}

function Sheet({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: SheetProps) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  // Close on Escape
  React.useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, setOpen]);

  const ctx = React.useMemo<SheetContextValue>(
    () => ({ open, setOpen }),
    [open, setOpen],
  );

  return (
    <SheetContext.Provider value={ctx}>{children}</SheetContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// SheetTrigger
// ---------------------------------------------------------------------------
interface SheetTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

function SheetTrigger({
  asChild,
  children,
  onClick,
  ...props
}: SheetTriggerProps) {
  const { setOpen } = useSheetContext();

  const triggerProps: Record<string, any> = {
    "data-slot": "sheet-trigger",
    onClick: (e: React.MouseEvent) => {
      setOpen(true);
      (onClick as any)?.(e);
    },
    ...props,
  };

  if (asChild && React.isValidElement(children)) {
    return <Slot {...triggerProps}>{children}</Slot>;
  }

  return (
    <button type="button" {...triggerProps}>
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// SheetClose
// ---------------------------------------------------------------------------
interface SheetCloseProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

function SheetClose({
  asChild,
  children,
  onClick,
  ...props
}: SheetCloseProps) {
  const { setOpen } = useSheetContext();

  const closeProps: Record<string, any> = {
    "data-slot": "sheet-close",
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
// SheetOverlay (internal)
// ---------------------------------------------------------------------------
function SheetOverlay({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const { setOpen } = useSheetContext();

  return (
    <div
      data-slot="sheet-overlay"
      data-state="open"
      className={cn(
        "animate-in fade-in-0 fixed inset-0 z-50 bg-black/50",
        className,
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          setOpen(false);
        }
      }}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// SheetContent
// ---------------------------------------------------------------------------
interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: "top" | "right" | "bottom" | "left";
  onOpenAutoFocus?: (e: Event) => void;
  onCloseAutoFocus?: (e: Event) => void;
  onEscapeKeyDown?: (e: KeyboardEvent) => void;
  onPointerDownOutside?: (e: PointerEvent) => void;
  onInteractOutside?: (e: Event) => void;
  forceMount?: boolean;
}

function SheetContent({
  className,
  children,
  side = "right",
  onOpenAutoFocus: _oaf,
  onCloseAutoFocus: _ocaf,
  onEscapeKeyDown: _oekd,
  onPointerDownOutside: _opdo,
  onInteractOutside: _oio,
  forceMount: _fm,
  ...props
}: SheetContentProps) {
  const { open, setOpen } = useSheetContext();

  if (!open) return null;

  return (
    <>
      <SheetOverlay />
      <div
        role="dialog"
        aria-modal="true"
        data-slot="sheet-content"
        data-state="open"
        className={cn(
          "bg-background animate-in fixed z-50 flex flex-col gap-4 shadow-lg transition ease-in-out duration-500",
          side === "right" &&
            "slide-in-from-right inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm",
          side === "left" &&
            "slide-in-from-left inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm",
          side === "top" &&
            "slide-in-from-top inset-x-0 top-0 h-auto border-b",
          side === "bottom" &&
            "slide-in-from-bottom inset-x-0 bottom-0 h-auto border-t",
          className,
        )}
        {...props}
      >
        {children}
        <button
          type="button"
          className="ring-offset-background focus:ring-ring data-[state=open]:bg-secondary absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none"
          onClick={() => setOpen(false)}
        >
          <XIcon className="size-4" />
          <span className="sr-only">Close</span>
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// SheetHeader / SheetFooter
// ---------------------------------------------------------------------------
function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1.5 p-4", className)}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("mt-auto flex flex-col gap-2 p-4", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// SheetTitle
// ---------------------------------------------------------------------------
function SheetTitle({
  className,
  ...props
}: React.ComponentProps<"h2">) {
  return (
    <h2
      data-slot="sheet-title"
      className={cn("text-foreground font-semibold", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// SheetDescription
// ---------------------------------------------------------------------------
function SheetDescription({
  className,
  ...props
}: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="sheet-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
};
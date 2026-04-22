"use client";

import * as React from "react";
import { XIcon } from "lucide-react";

import { cn } from "./utils";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface DialogContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialogContext() {
  const ctx = React.useContext(DialogContext);
  if (!ctx)
    throw new Error("Dialog components must be used within <Dialog>");
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
// Dialog (Root)
// ---------------------------------------------------------------------------
interface DialogProps {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  modal?: boolean;
}

function Dialog({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: DialogProps) {
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

  const ctx = React.useMemo<DialogContextValue>(
    () => ({ open, setOpen }),
    [open, setOpen],
  );

  return (
    <DialogContext.Provider value={ctx}>{children}</DialogContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// DialogTrigger
// ---------------------------------------------------------------------------
interface DialogTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

function DialogTrigger({
  asChild,
  children,
  onClick,
  ...props
}: DialogTriggerProps) {
  const { setOpen } = useDialogContext();

  const triggerProps: Record<string, any> = {
    "data-slot": "dialog-trigger",
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
// DialogPortal – no-op (avoids sandbox SecurityError)
// ---------------------------------------------------------------------------
function DialogPortal({
  children,
}: {
  children: React.ReactNode;
  container?: HTMLElement | null;
  forceMount?: true;
}) {
  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// DialogClose
// ---------------------------------------------------------------------------
interface DialogCloseProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

function DialogClose({
  asChild,
  children,
  onClick,
  ...props
}: DialogCloseProps) {
  const { setOpen } = useDialogContext();

  const closeProps: Record<string, any> = {
    "data-slot": "dialog-close",
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
// DialogOverlay
// ---------------------------------------------------------------------------
function DialogOverlay({
  className,
  onClick,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const { setOpen } = useDialogContext();

  return (
    <div
      data-slot="dialog-overlay"
      data-state="open"
      className={cn(
        "animate-in fade-in-0 fixed inset-0 z-50 bg-black/50",
        className,
      )}
      onClick={(e) => {
        // Only close if clicking the overlay itself, not its children
        if (e.target === e.currentTarget) {
          setOpen(false);
        }
        (onClick as any)?.(e);
      }}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DialogContent
// ---------------------------------------------------------------------------
interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  onOpenAutoFocus?: (e: Event) => void;
  onCloseAutoFocus?: (e: Event) => void;
  onEscapeKeyDown?: (e: KeyboardEvent) => void;
  onPointerDownOutside?: (e: PointerEvent) => void;
  onInteractOutside?: (e: Event) => void;
  forceMount?: boolean;
}

function DialogContent({
  className,
  children,
  onOpenAutoFocus: _oaf,
  onCloseAutoFocus: _ocaf,
  onEscapeKeyDown: _oekd,
  onPointerDownOutside: _opdo,
  onInteractOutside: _oio,
  forceMount: _fm,
  ...props
}: DialogContentProps) {
  const { open, setOpen } = useDialogContext();
  const contentRef = React.useRef<HTMLDivElement>(null);

  // Focus trap: focus the content when opened
  React.useEffect(() => {
    if (open && contentRef.current) {
      contentRef.current.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <>
      <DialogOverlay />
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        data-slot="dialog-content"
        data-state="open"
        className={cn(
          "bg-background animate-in fade-in-0 zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 sm:max-w-lg",
          className,
        )}
        onClick={(e) => e.stopPropagation()}
        {...props}
      >
        {children}
        <button
          type="button"
          className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          onClick={() => setOpen(false)}
        >
          <XIcon />
          <span className="sr-only">Close</span>
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// DialogHeader / DialogFooter
// ---------------------------------------------------------------------------
function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn(
        "flex flex-col gap-2 text-center sm:text-left",
        className,
      )}
      {...props}
    />
  );
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className,
      )}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DialogTitle
// ---------------------------------------------------------------------------
function DialogTitle({
  className,
  ...props
}: React.ComponentProps<"h2">) {
  return (
    <h2
      data-slot="dialog-title"
      className={cn("text-lg leading-none font-semibold", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DialogDescription
// ---------------------------------------------------------------------------
function DialogDescription({
  className,
  ...props
}: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="dialog-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
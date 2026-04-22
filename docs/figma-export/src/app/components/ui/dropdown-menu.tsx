"use client";

import * as React from "react";
import { CheckIcon, ChevronRightIcon, CircleIcon } from "lucide-react";

import { cn } from "./utils";

// ---------------------------------------------------------------------------
// Slot utility – lightweight `asChild` support (replaces @radix-ui/react-slot)
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

/**
 * Renders the single React-element child, forwarding all `props` from the
 * parent onto it (merges className, event handlers, refs, and data-* attrs).
 */
const Slot = React.forwardRef<any, { children: React.ReactNode } & Record<string, any>>(
  ({ children, ...props }, forwardedRef) => {
    if (!React.isValidElement(children)) return null;

    const childProps = (children as React.ReactElement<any>).props as Record<
      string,
      any
    >;

    const merged: Record<string, any> = { ...props };

    // Copy child props that the parent doesn't already provide
    for (const key of Object.keys(childProps)) {
      if (key === "className" || key === "ref") continue; // handled below
      if (key.startsWith("on") && typeof props[key] === "function") {
        // Chain both event handlers — child first, parent second
        const parentHandler = props[key];
        const childHandler = childProps[key];
        merged[key] = (...args: any[]) => {
          if (typeof childHandler === "function") childHandler(...args);
          parentHandler(...args);
        };
      } else if (!(key in merged)) {
        merged[key] = childProps[key];
      }
    }

    // Merge classNames
    merged.className = cn(props.className, childProps.className);

    // Merge refs
    const childRef = (children as any).ref;
    merged.ref = mergeRefs(forwardedRef, childRef);

    return React.cloneElement(children as React.ReactElement<any>, merged);
  }
);

Slot.displayName = "Slot";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface DropdownMenuContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
  contentRef: React.RefObject<HTMLDivElement | null>;
}

const DropdownMenuContext =
  React.createContext<DropdownMenuContextValue | null>(null);

function useDropdownMenuContext() {
  const ctx = React.useContext(DropdownMenuContext);
  if (!ctx)
    throw new Error(
      "DropdownMenu components must be used within <DropdownMenu>",
    );
  return ctx;
}

// ---------------------------------------------------------------------------
// DropdownMenu (Root)
// ---------------------------------------------------------------------------
interface DropdownMenuProps {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  modal?: boolean;
  dir?: "ltr" | "rtl";
}

function DropdownMenu({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: DropdownMenuProps) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  const setOpen = React.useCallback(
    (nextOpen: boolean) => {
      if (!isControlled) setInternalOpen(nextOpen);
      onOpenChange?.(nextOpen);
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

  const ctx = React.useMemo<DropdownMenuContextValue>(
    () => ({ open, setOpen, triggerRef, contentRef }),
    [open, setOpen],
  );

  return (
    <DropdownMenuContext.Provider value={ctx}>
      <div
        data-slot="dropdown-menu"
        style={{ position: "relative", display: "inline-block" }}
      >
        {children}
      </div>
    </DropdownMenuContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuPortal – no-op pass-through (avoids sandbox SecurityError)
// ---------------------------------------------------------------------------
function DropdownMenuPortal({
  children,
}: {
  children: React.ReactNode;
  container?: HTMLElement | null;
  forceMount?: true;
}) {
  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// DropdownMenuTrigger
// ---------------------------------------------------------------------------
interface DropdownMenuTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

const DropdownMenuTrigger = React.forwardRef<
  HTMLButtonElement,
  DropdownMenuTriggerProps
>(({ asChild, children, onClick, onKeyDown, ...props }, ref) => {
  const { open, setOpen, triggerRef } = useDropdownMenuContext();

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
    "data-slot": "dropdown-menu-trigger",
    "data-state": open ? "open" : "closed",
    "aria-expanded": open,
    "aria-haspopup": "menu",
    onClick: (e: React.MouseEvent) => {
      setOpen(!open);
      (onClick as any)?.(e);
    },
    onKeyDown: (e: React.KeyboardEvent) => {
      if (
        e.key === "ArrowDown" ||
        e.key === "Enter" ||
        e.key === " "
      ) {
        e.preventDefault();
        if (!open) setOpen(true);
      }
      (onKeyDown as any)?.(e);
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

DropdownMenuTrigger.displayName = "DropdownMenuTrigger";

// ---------------------------------------------------------------------------
// DropdownMenuContent
// ---------------------------------------------------------------------------
interface DropdownMenuContentProps
  extends React.HTMLAttributes<HTMLDivElement> {
  sideOffset?: number;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  alignOffset?: number;
  avoidCollisions?: boolean;
  collisionBoundary?: any;
  collisionPadding?: any;
  sticky?: string;
  hideWhenDetached?: boolean;
  onCloseAutoFocus?: (e: Event) => void;
  loop?: boolean;
  forceMount?: boolean;
}

function DropdownMenuContent({
  className,
  children,
  sideOffset = 4,
  align = "center",
  side = "bottom",
  // Accept but ignore Radix-specific positioning props
  alignOffset: _ao,
  avoidCollisions: _ac,
  collisionBoundary: _cb,
  collisionPadding: _cp,
  sticky: _s,
  hideWhenDetached: _hwd,
  onCloseAutoFocus: _ocaf,
  loop: _loop,
  forceMount: _fm,
  ...props
}: DropdownMenuContentProps) {
  const { open, contentRef } = useDropdownMenuContext();

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
      role="menu"
      data-slot="dropdown-menu-content"
      data-state="open"
      data-side={side}
      style={positionStyles}
      className={cn(
        "bg-popover text-popover-foreground z-50 max-h-[var(--radix-dropdown-menu-content-available-height,85vh)] min-w-[8rem] overflow-x-hidden overflow-y-auto rounded-md border p-1 shadow-md",
        "animate-in fade-in-0 zoom-in-95",
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
// DropdownMenuGroup
// ---------------------------------------------------------------------------
function DropdownMenuGroup({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      role="group"
      data-slot="dropdown-menu-group"
      className={className}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuItem
// ---------------------------------------------------------------------------
interface DropdownMenuItemProps
  extends React.HTMLAttributes<HTMLDivElement> {
  inset?: boolean;
  variant?: "default" | "destructive";
  disabled?: boolean;
  asChild?: boolean;
  onSelect?: (event: Event) => void;
}

function DropdownMenuItem({
  className,
  inset,
  variant = "default",
  disabled,
  asChild,
  children,
  onClick,
  onSelect: _onSelect,
  ...props
}: DropdownMenuItemProps) {
  const { setOpen } = useDropdownMenuContext();

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled) return;
    (onClick as any)?.(e);
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!disabled) {
        (onClick as any)?.(e);
        setOpen(false);
      }
    }
    (props.onKeyDown as any)?.(e);
  };

  const itemClassName = cn(
    "focus:bg-accent focus:text-accent-foreground data-[variant=destructive]:text-destructive data-[variant=destructive]:focus:bg-destructive/10 dark:data-[variant=destructive]:focus:bg-destructive/20 data-[variant=destructive]:focus:text-destructive data-[variant=destructive]:*:[svg]:!text-destructive [&_svg:not([class*='text-'])]:text-muted-foreground relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[inset]:pl-8 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
    className,
  );

  const sharedProps: Record<string, any> = {
    role: "menuitem",
    "data-slot": "dropdown-menu-item",
    "data-inset": inset || undefined,
    "data-variant": variant,
    "data-disabled": disabled || undefined,
    tabIndex: disabled ? -1 : 0,
    className: itemClassName,
    onClick: handleClick,
    onKeyDown: handleKeyDown,
    ...props,
  };

  if (asChild && React.isValidElement(children)) {
    return <Slot {...sharedProps}>{children}</Slot>;
  }

  return <div {...sharedProps}>{children}</div>;
}

// ---------------------------------------------------------------------------
// DropdownMenuCheckboxItem
// ---------------------------------------------------------------------------
interface DropdownMenuCheckboxItemProps
  extends React.HTMLAttributes<HTMLDivElement> {
  checked?: boolean | "indeterminate";
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
}

function DropdownMenuCheckboxItem({
  className,
  children,
  checked,
  onCheckedChange,
  disabled,
  onClick,
  ...props
}: DropdownMenuCheckboxItemProps) {
  const { setOpen } = useDropdownMenuContext();

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled) return;
    onCheckedChange?.(!checked);
    (onClick as any)?.(e);
    setOpen(false);
  };

  return (
    <div
      role="menuitemcheckbox"
      aria-checked={checked === "indeterminate" ? "mixed" : !!checked}
      data-slot="dropdown-menu-checkbox-item"
      data-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : 0}
      className={cn(
        "focus:bg-accent focus:text-accent-foreground relative flex cursor-default items-center gap-2 rounded-sm py-1.5 pr-2 pl-8 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick(e as any);
        }
      }}
      {...props}
    >
      <span className="pointer-events-none absolute left-2 flex size-3.5 items-center justify-center">
        {checked === true && <CheckIcon className="size-4" />}
      </span>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuRadioGroup
// ---------------------------------------------------------------------------
interface DropdownMenuRadioContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const DropdownMenuRadioContext =
  React.createContext<DropdownMenuRadioContextValue | null>(null);

interface DropdownMenuRadioGroupProps
  extends React.HTMLAttributes<HTMLDivElement> {
  value?: string;
  onValueChange?: (value: string) => void;
}

function DropdownMenuRadioGroup({
  value = "",
  onValueChange,
  ...props
}: DropdownMenuRadioGroupProps) {
  const ctx = React.useMemo(
    () => ({ value, onValueChange: onValueChange ?? (() => {}) }),
    [value, onValueChange],
  );
  return (
    <DropdownMenuRadioContext.Provider value={ctx}>
      <div
        role="group"
        data-slot="dropdown-menu-radio-group"
        {...props}
      />
    </DropdownMenuRadioContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuRadioItem
// ---------------------------------------------------------------------------
interface DropdownMenuRadioItemProps
  extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
  disabled?: boolean;
}

function DropdownMenuRadioItem({
  className,
  children,
  value: itemValue,
  disabled,
  onClick,
  ...props
}: DropdownMenuRadioItemProps) {
  const { setOpen } = useDropdownMenuContext();
  const radioCtx = React.useContext(DropdownMenuRadioContext);
  const isChecked = radioCtx?.value === itemValue;

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled) return;
    radioCtx?.onValueChange(itemValue);
    (onClick as any)?.(e);
    setOpen(false);
  };

  return (
    <div
      role="menuitemradio"
      aria-checked={isChecked}
      data-slot="dropdown-menu-radio-item"
      data-state={isChecked ? "checked" : "unchecked"}
      data-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : 0}
      className={cn(
        "focus:bg-accent focus:text-accent-foreground relative flex cursor-default items-center gap-2 rounded-sm py-1.5 pr-2 pl-8 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick(e as any);
        }
      }}
      {...props}
    >
      <span className="pointer-events-none absolute left-2 flex size-3.5 items-center justify-center">
        {isChecked && <CircleIcon className="size-2 fill-current" />}
      </span>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuLabel
// ---------------------------------------------------------------------------
function DropdownMenuLabel({
  className,
  inset,
  ...props
}: React.ComponentProps<"div"> & { inset?: boolean }) {
  return (
    <div
      data-slot="dropdown-menu-label"
      data-inset={inset || undefined}
      className={cn(
        "px-2 py-1.5 text-sm font-medium data-[inset]:pl-8",
        className,
      )}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuSeparator
// ---------------------------------------------------------------------------
function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      role="separator"
      data-slot="dropdown-menu-separator"
      className={cn("bg-border -mx-1 my-1 h-px", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuShortcut
// ---------------------------------------------------------------------------
function DropdownMenuShortcut({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      className={cn(
        "text-muted-foreground ml-auto text-xs tracking-widest",
        className,
      )}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuSub  (minimal – sub-menus are rare in current usage)
// ---------------------------------------------------------------------------
interface DropdownMenuSubContextValue {
  subOpen: boolean;
  setSubOpen: (open: boolean) => void;
  subTriggerRef: React.RefObject<HTMLDivElement | null>;
  subContentRef: React.RefObject<HTMLDivElement | null>;
}

const DropdownMenuSubContext =
  React.createContext<DropdownMenuSubContextValue | null>(null);

function DropdownMenuSub({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
}: {
  children: React.ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const subTriggerRef = React.useRef<HTMLDivElement | null>(null);
  const subContentRef = React.useRef<HTMLDivElement | null>(null);

  const isControlled = controlledOpen !== undefined;
  const subOpen = isControlled ? controlledOpen : internalOpen;

  const setSubOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  const ctx = React.useMemo(
    () => ({ subOpen, setSubOpen, subTriggerRef, subContentRef }),
    [subOpen, setSubOpen],
  );

  return (
    <DropdownMenuSubContext.Provider value={ctx}>
      <div
        data-slot="dropdown-menu-sub"
        style={{ position: "relative" }}
      >
        {children}
      </div>
    </DropdownMenuSubContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuSubTrigger
// ---------------------------------------------------------------------------
function DropdownMenuSubTrigger({
  className,
  inset,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }) {
  const subCtx = React.useContext(DropdownMenuSubContext);

  return (
    <div
      data-slot="dropdown-menu-sub-trigger"
      data-inset={inset || undefined}
      data-state={subCtx?.subOpen ? "open" : "closed"}
      className={cn(
        "focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground flex cursor-default items-center rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[inset]:pl-8",
        className,
      )}
      tabIndex={0}
      ref={subCtx?.subTriggerRef as any}
      onClick={() => subCtx?.setSubOpen(!subCtx.subOpen)}
      onMouseEnter={() => subCtx?.setSubOpen(true)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          subCtx?.setSubOpen(true);
        }
        if (e.key === "ArrowLeft" || e.key === "Escape") {
          subCtx?.setSubOpen(false);
        }
      }}
      {...props}
    >
      {children}
      <ChevronRightIcon className="ml-auto size-4" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// DropdownMenuSubContent
// ---------------------------------------------------------------------------
function DropdownMenuSubContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const subCtx = React.useContext(DropdownMenuSubContext);

  if (!subCtx?.subOpen) return null;

  return (
    <div
      ref={subCtx.subContentRef}
      data-slot="dropdown-menu-sub-content"
      data-state="open"
      style={{
        position: "absolute",
        left: "100%",
        top: 0,
        zIndex: 50,
        marginLeft: 4,
      }}
      className={cn(
        "bg-popover text-popover-foreground z-50 min-w-[8rem] overflow-hidden rounded-md border p-1 shadow-lg",
        "animate-in fade-in-0 zoom-in-95 slide-in-from-left-2",
        className,
      )}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export {
  DropdownMenu,
  DropdownMenuPortal,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
};
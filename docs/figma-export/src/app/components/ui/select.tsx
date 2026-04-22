"use client";

import * as React from "react";
import { CheckIcon, ChevronDownIcon } from "lucide-react";
import { cn } from "./utils";

// ---- Context ----
interface SelectContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  value: string;
  onValueChange: (value: string) => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
  contentRef: React.RefObject<HTMLDivElement | null>;
  // Map of value -> display text, populated by SelectItem
  itemLabels: React.MutableRefObject<Map<string, string>>;
  placeholder?: string;
}

const SelectContext = React.createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const ctx = React.useContext(SelectContext);
  if (!ctx) throw new Error("Select components must be used within <Select>");
  return ctx;
}

// ---- Select Root ----
interface SelectProps {
  children: React.ReactNode;
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
}

function Select({
  children,
  defaultValue = "",
  value: controlledValue,
  onValueChange,
  disabled,
}: SelectProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);
  const itemLabels = React.useRef<Map<string, string>>(new Map());

  const isControlled = controlledValue !== undefined;
  const currentValue = isControlled ? controlledValue : internalValue;

  const handleValueChange = React.useCallback(
    (newValue: string) => {
      if (!isControlled) setInternalValue(newValue);
      onValueChange?.(newValue);
    },
    [isControlled, onValueChange],
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
    // Use setTimeout to avoid the click that opened the menu from closing it
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const ctx = React.useMemo<SelectContextValue>(
    () => ({
      open,
      setOpen,
      value: currentValue,
      onValueChange: handleValueChange,
      triggerRef,
      contentRef,
      itemLabels,
    }),
    [open, currentValue, handleValueChange],
  );

  return (
    <SelectContext.Provider value={ctx}>
      <div data-slot="select" data-state={open ? "open" : "closed"} style={{ position: "relative" }}>
        {children}
      </div>
    </SelectContext.Provider>
  );
}

// ---- SelectGroup ----
function SelectGroup({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return <div data-slot="select-group" className={className} {...props} />;
}

// ---- SelectValue ----
interface SelectValueProps extends React.ComponentProps<"span"> {
  placeholder?: string;
}

function SelectValue({ placeholder, className, ...props }: SelectValueProps) {
  const { value, itemLabels } = useSelectContext();
  const [label, setLabel] = React.useState("");

  // Re-derive label when value changes; small delay to let items register
  React.useEffect(() => {
    const text = itemLabels.current.get(value);
    if (text) {
      setLabel(text);
    } else {
      // Items may not have mounted yet; try again shortly
      const timer = setTimeout(() => {
        setLabel(itemLabels.current.get(value) || "");
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [value, itemLabels]);

  const showPlaceholder = !value && placeholder;

  return (
    <span
      data-slot="select-value"
      data-placeholder={showPlaceholder ? "" : undefined}
      className={cn("line-clamp-1 flex items-center gap-2", className)}
      {...props}
    >
      {showPlaceholder ? placeholder : label || value}
    </span>
  );
}

// ---- SelectTrigger ----
interface SelectTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: "sm" | "default";
}

const SelectTrigger = React.forwardRef<HTMLButtonElement, SelectTriggerProps>(
  ({ className, size = "default", children, ...props }, ref) => {
    const { open, setOpen, triggerRef } = useSelectContext();

    const composedRef = React.useCallback(
      (node: HTMLButtonElement | null) => {
        (triggerRef as React.MutableRefObject<HTMLButtonElement | null>).current = node;
        if (typeof ref === "function") ref(node);
        else if (ref) (ref as React.MutableRefObject<HTMLButtonElement | null>).current = node;
      },
      [ref, triggerRef],
    );

    return (
      <button
        type="button"
        role="combobox"
        aria-expanded={open}
        data-slot="select-trigger"
        data-size={size}
        data-state={open ? "open" : "closed"}
        className={cn(
          "border-input data-[placeholder]:text-muted-foreground [&_svg:not([class*='text-'])]:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 dark:hover:bg-input/50 flex w-full items-center justify-between gap-2 rounded-md border bg-transparent px-3 py-2 text-sm whitespace-nowrap transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 data-[size=default]:h-9 data-[size=sm]:h-8 *:data-[slot=select-value]:line-clamp-1 *:data-[slot=select-value]:flex *:data-[slot=select-value]:items-center *:data-[slot=select-value]:gap-2 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
          className,
        )}
        ref={composedRef}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (!open) setOpen(true);
          }
          if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        {...props}
      >
        {children}
        <ChevronDownIcon className="size-4 opacity-50" />
      </button>
    );
  },
);

SelectTrigger.displayName = "SelectTrigger";

// ---- SelectContent ----
interface SelectContentProps extends React.HTMLAttributes<HTMLDivElement> {
  position?: "popper" | "item-aligned";
}

function SelectContent({
  className,
  children,
  position = "popper",
  ...props
}: SelectContentProps) {
  const { open, contentRef } = useSelectContext();

  if (!open) {
    // Render items hidden so they can register their labels
    return <div style={{ display: 'none' }}>{children}</div>;
  }

  return (
    <div
      ref={contentRef}
      data-slot="select-content"
      data-state="open"
      data-side="bottom"
      className={cn(
        "bg-popover text-popover-foreground absolute left-0 top-full z-50 mt-1 max-h-96 min-w-[8rem] w-full overflow-x-hidden overflow-y-auto rounded-md border shadow-md",
        "animate-in fade-in-0 zoom-in-95",
        className,
      )}
      {...props}
    >
      <div className="p-1 w-full">{children}</div>
    </div>
  );
}

// ---- SelectLabel ----
function SelectLabel({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="select-label"
      className={cn("text-muted-foreground px-2 py-1.5 text-xs", className)}
      {...props}
    />
  );
}

// ---- SelectItem ----
interface SelectItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
  disabled?: boolean;
}

function SelectItem({
  className,
  children,
  value: itemValue,
  disabled,
  ...props
}: SelectItemProps) {
  const { value, onValueChange, setOpen, triggerRef, itemLabels } = useSelectContext();
  const isSelected = value === itemValue;
  const textRef = React.useRef<HTMLSpanElement>(null);

  // Register this item's label text
  React.useEffect(() => {
    const text = textRef.current?.textContent || "";
    itemLabels.current.set(itemValue, text);
  }, [itemValue, children, itemLabels]);

  return (
    <div
      role="option"
      aria-selected={isSelected}
      data-slot="select-item"
      data-disabled={disabled || undefined}
      data-state={isSelected ? "checked" : "unchecked"}
      className={cn(
        "hover:bg-accent hover:text-accent-foreground [&_svg:not([class*='text-'])]:text-muted-foreground relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 pr-8 pl-2 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        isSelected && "bg-accent text-accent-foreground",
        className,
      )}
      onClick={() => {
        if (disabled) return;
        onValueChange(itemValue);
        setOpen(false);
        // Return focus to trigger
        setTimeout(() => triggerRef.current?.focus(), 0);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (!disabled) {
            onValueChange(itemValue);
            setOpen(false);
            setTimeout(() => triggerRef.current?.focus(), 0);
          }
        }
      }}
      tabIndex={disabled ? -1 : 0}
      {...props}
    >
      <span className="absolute right-2 flex size-3.5 items-center justify-center">
        {isSelected && <CheckIcon className="size-4" />}
      </span>
      <span ref={textRef}>{children}</span>
    </div>
  );
}

// ---- SelectSeparator ----
function SelectSeparator({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="select-separator"
      className={cn("bg-border pointer-events-none -mx-1 my-1 h-px", className)}
      {...props}
    />
  );
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
};
import * as React from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { INDUSTRY_OPTIONS } from "@/data/organizationTypes";

interface IndustrySelectProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

/**
 * Industry selector with search functionality - simplified version
 * Uses basic input and scroll area instead of Command component
 */
export const IndustrySelectSearchable = React.forwardRef<
  HTMLButtonElement,
  IndustrySelectProps
>(
  (
    { value, onValueChange, placeholder = "Select industry", className },
    ref,
  ) => {
    const [open, setOpen] = React.useState(false);
    const [search, setSearch] = React.useState("");
    const [highlightedIndex, setHighlightedIndex] = React.useState(0);
    const inputRef = React.useRef<HTMLInputElement>(null);
    const scrollAreaRef = React.useRef<HTMLDivElement>(null);

    const filteredOptions = React.useMemo(() => {
      if (!search) return INDUSTRY_OPTIONS;

      const searchLower = search.toLowerCase();
      return INDUSTRY_OPTIONS.filter(
        (opt) =>
          opt.label.toLowerCase().includes(searchLower) ||
          opt.definition.toLowerCase().includes(searchLower),
      );
    }, [search]);

    const selectedOption = INDUSTRY_OPTIONS.find((opt) => opt.value === value);

    // Reset highlighted index when search changes
    React.useEffect(() => {
      setHighlightedIndex(0);
    }, [search]);

    // Focus input when popover opens
    React.useEffect(() => {
      if (open && inputRef.current) {
        inputRef.current.focus();
      }
    }, [open]);

    const handleSelect = (optionValue: string) => {
      onValueChange(optionValue);
      setOpen(false);
      setSearch("");
      setHighlightedIndex(0);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (!open) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          e.stopPropagation();
          setHighlightedIndex((prev) =>
            prev < filteredOptions.length - 1 ? prev + 1 : prev,
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          e.stopPropagation();
          setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : prev));
          break;
        case "Enter":
          e.preventDefault();
          if (filteredOptions[highlightedIndex]) {
            handleSelect(filteredOptions[highlightedIndex].value);
          }
          break;
        case "Escape":
          e.preventDefault();
          setOpen(false);
          setSearch("");
          setHighlightedIndex(0);
          break;
      }
    };

    // Scroll highlighted item into view
    React.useEffect(() => {
      if (!open || !scrollAreaRef.current) return;

      const highlightedElement = scrollAreaRef.current.querySelector(
        `[data-index="${highlightedIndex}"]`,
      );

      if (highlightedElement && highlightedElement.scrollIntoView) {
        highlightedElement.scrollIntoView({
          block: "nearest",
          behavior: "smooth",
        });
      }
    }, [highlightedIndex, open]);

    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            ref={ref}
            variant="outline"
            role="combobox"
            aria-expanded={open}
            aria-haspopup="listbox"
            className={cn("w-full justify-between", className)}
          >
            <span className={cn(!selectedOption && "text-muted-foreground")}>
              {selectedOption?.label || placeholder}
            </span>
            <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="p-0 overflow-hidden"
          align="start"
          style={{ width: "var(--radix-popover-trigger-width)" }}
        >
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <Input
              ref={inputRef}
              placeholder="Search industries..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              className="h-11 border-0 focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </div>
          <div
            className="max-h-[18.75rem] overflow-y-auto overflow-x-hidden"
            ref={scrollAreaRef}
            style={{ overscrollBehavior: "contain" }}
          >
            {filteredOptions.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No industry found.
              </div>
            ) : (
              <div className="p-1" role="listbox">
                {filteredOptions.map((option, index) => (
                  <div
                    key={option.value}
                    data-index={index}
                    className={cn(
                      "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors",
                      highlightedIndex === index &&
                        "bg-accent text-accent-foreground",
                      value === option.value && "font-medium",
                    )}
                    onClick={() => handleSelect(option.value)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    role="option"
                    aria-selected={value === option.value}
                  >
                    <div className="flex flex-col items-start flex-1 py-1">
                      <span className="font-medium">{option.label}</span>
                      <span className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {option.definition}
                      </span>
                    </div>
                    <Check
                      className={cn(
                        "ml-2 h-4 w-4",
                        value === option.value ? "opacity-100" : "opacity-0",
                      )}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  },
);

IndustrySelectSearchable.displayName = "IndustrySelectSearchable";

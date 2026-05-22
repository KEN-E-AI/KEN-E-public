import * as React from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  templateService,
  type IndustryTemplate,
} from "@/services/templateService";

interface IndustrySelectProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

interface IndustryOption {
  value: string;
  label: string;
  description: string;
}

/**
 * Industry selector with search functionality - fetches data from API
 * This version uses the industry templates from Firestore
 */
export const IndustrySelectDropdownAPI = React.forwardRef<
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
    const [industries, setIndustries] = React.useState<IndustryOption[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const inputRef = React.useRef<HTMLInputElement>(null);
    const dropdownRef = React.useRef<HTMLDivElement>(null);
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Fetch industries when component mounts
    React.useEffect(() => {
      const fetchIndustries = async () => {
        setLoading(true);
        setError(null);
        try {
          const templates = await templateService.getAllTemplates();
          const options: IndustryOption[] = templates.map((template) => ({
            // `industry` is the canonical field; the legacy fallbacks to
            // `recommendedSettings.industry` / `name` reference fields that
            // IndustryTemplate doesn't expose. Cast preserves the runtime
            // fallback behavior in case the API ever returns either.
            value:
              template.industry ||
              (template as { recommendedSettings?: { industry?: string } })
                .recommendedSettings?.industry ||
              template.id,
            label:
              template.industry ||
              (template as { name?: string }).name ||
              template.id,
            description: template.description || "",
          }));
          // Sort alphabetically by label
          options.sort((a, b) => a.label.localeCompare(b.label));
          setIndustries(options);
        } catch (err) {
          console.error("Failed to fetch industries:", err);
          setError("Failed to load industries");
          // Fallback to empty list
          setIndustries([]);
        } finally {
          setLoading(false);
        }
      };

      fetchIndustries();
    }, []);

    const filteredOptions = React.useMemo(() => {
      if (!search) return industries;

      const searchLower = search.toLowerCase();
      return industries.filter(
        (opt) =>
          opt.label.toLowerCase().includes(searchLower) ||
          opt.description.toLowerCase().includes(searchLower),
      );
    }, [search, industries]);

    const selectedOption = industries.find((opt) => opt.value === value);

    // Reset highlighted index when search changes
    React.useEffect(() => {
      setHighlightedIndex(0);
    }, [search]);

    // Focus input when dropdown opens
    React.useEffect(() => {
      if (open && inputRef.current) {
        // Small delay to ensure DOM is ready
        setTimeout(() => {
          inputRef.current?.focus();
        }, 50);
      }
    }, [open]);

    // Close on outside click
    React.useEffect(() => {
      if (!open) return;

      const handleClickOutside = (e: MouseEvent) => {
        if (
          containerRef.current &&
          !containerRef.current.contains(e.target as Node)
        ) {
          setOpen(false);
          setSearch("");
          setHighlightedIndex(0);
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
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
      if (!open || !dropdownRef.current) return;

      const highlightedElement = dropdownRef.current.querySelector(
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
      <div className="relative" ref={containerRef}>
        <Button
          ref={ref}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          className={cn("w-full justify-between", className)}
          onClick={() => setOpen(!open)}
          disabled={loading}
        >
          {loading ? (
            <span className="text-muted-foreground">Loading industries...</span>
          ) : (
            <span className={cn(!selectedOption && "text-muted-foreground")}>
              {selectedOption?.label || placeholder}
            </span>
          )}
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>

        {open && !loading && (
          <div
            ref={dropdownRef}
            className="absolute z-50 w-full mt-1 rounded-md border bg-popover text-popover-foreground shadow-md"
            onKeyDown={handleKeyDown}
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
              className="max-h-[18.75rem] overflow-y-auto"
              style={{
                overscrollBehavior: "contain",
                WebkitOverflowScrolling: "touch",
              }}
            >
              {error ? (
                <div className="py-6 text-center text-sm text-destructive">
                  {error}
                </div>
              ) : filteredOptions.length === 0 ? (
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
                        "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground",
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
                        {option.description && (
                          <span className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                            {option.description}
                          </span>
                        )}
                      </div>
                      <Check
                        className={cn(
                          "ml-2 h-4 w-4 flex-shrink-0",
                          value === option.value ? "opacity-100" : "opacity-0",
                        )}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  },
);

IndustrySelectDropdownAPI.displayName = "IndustrySelectDropdownAPI";

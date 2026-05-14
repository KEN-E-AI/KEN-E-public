import { Lock } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function DisabledPlaceholderRow({ label }: { label: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="flex items-center gap-2 p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] opacity-50 cursor-not-allowed select-none"
            aria-disabled="true"
            data-testid={`disabled-row-${label.toLowerCase().replace(/\s+/g, "-")}`}
          >
            {/* allow-text-tertiary: dim icon on disabled placeholder row */}
            <Lock className="size-4 text-[var(--color-text-tertiary)] shrink-0" />
            <span className="text-sm text-[var(--color-text-secondary)]">
              {label}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent>Available in Feature 2.6</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

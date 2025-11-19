import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import type React from "react";

interface SectionHeaderProps {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  tooltip?: string;
  actions?: React.ReactNode;
}

/**
 * Reusable section header with icon, title, tooltip, and actions
 * Used for headers within bordered sections or subsections
 */
export function SectionHeader({
  title,
  icon: Icon,
  tooltip,
  actions,
}: SectionHeaderProps) {
  return (
    <div className="flex justify-between items-center mb-6">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-5 w-5" />}
        <h3 className="text-lg font-semibold">{title}</h3>
        {tooltip && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 text-dashboard-gray-400" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>{tooltip}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      {actions}
    </div>
  );
}

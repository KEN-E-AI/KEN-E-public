import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import type { KnowledgeGraphCardProps } from "../types";

/**
 * Reusable card wrapper for knowledge graph sections
 * Provides consistent styling, header structure, and optional tooltip
 */
export function KnowledgeGraphCard({
  title,
  icon: Icon,
  tooltip,
  actions,
  children,
  height,
  className = "",
}: KnowledgeGraphCardProps) {
  return (
    <Card className={`${height || ""} ${className}`}>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="flex items-center gap-2">
            {Icon && <Icon className="h-5 w-5" />}
            {title}
            {tooltip && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>{tooltip}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </CardTitle>
          {actions}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Plus, Pencil, Trash2, Info, Loader2 } from "lucide-react";
import type { SideSheetNestedListProps, NestedListItem } from "../types";

/**
 * Reusable component for displaying nested lists in side sheets
 * Used for Value Propositions, Tactics, Opportunities, Risks, etc.
 *
 * @template T - Type of nested items (must extend NestedListItem)
 */
export function SideSheetNestedList<T extends NestedListItem>({
  title,
  tooltip,
  items,
  isLoading = false,
  onAdd,
  onEdit,
  onDelete,
  hasEditAccess = false,
  isEditingParent = false,
}: SideSheetNestedListProps<T>) {
  return (
    <div className="mt-6 pt-6 border-t">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <p className="font-semibold">{title}</p>
          {tooltip && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-dashboard-gray-400" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  <p>{tooltip}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
        {!isEditingParent && hasEditAccess && onAdd && (
          <Button size="sm" variant="outline" onClick={onAdd}>
            <Plus className="h-4 w-4 mr-1" />
            Add
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-dashboard-gray-500 italic">
          No {title.toLowerCase()} yet
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.node_id}
              className="p-3 rounded-md border border-dashboard-gray-200
                         bg-dashboard-gray-50 hover:bg-dashboard-gray-100
                         transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="font-medium text-sm">{item.display_name}</p>
                  <p className="text-xs text-dashboard-gray-600 mt-1">
                    {item.description}
                  </p>
                </div>
                {!isEditingParent && hasEditAccess && (onEdit || onDelete) && (
                  <div className="flex gap-1 ml-2">
                    {onEdit && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onEdit(item)}
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                    )}
                    {onDelete && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onDelete(item)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

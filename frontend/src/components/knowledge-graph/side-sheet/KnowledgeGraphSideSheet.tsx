import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2 } from "lucide-react";
import type React from "react";

interface KnowledgeGraphSideSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  isEditing: boolean;
  onEdit?: () => void;
  onSave?: () => void;
  onCancel?: () => void;
  onDelete?: () => void;
  hasEditAccess?: boolean;
  isSaving?: boolean;
  preventClose?: boolean;
  modal?: boolean;
}

/**
 * Reusable side sheet for viewing/editing knowledge graph items
 * Provides consistent edit/view mode switching and action buttons
 */
export function KnowledgeGraphSideSheet({
  open,
  onOpenChange,
  title,
  icon: Icon,
  children,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  onDelete,
  hasEditAccess = false,
  isSaving = false,
  preventClose = false,
  modal = false,
}: KnowledgeGraphSideSheetProps) {
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && preventClose) {
      return;
    }
    onOpenChange(newOpen);
  };

  return (
    <Sheet open={open} modal={modal} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        className="w-[400px] flex flex-col"
        onInteractOutside={(e) => {
          // Prevent closing when clicking on React Flow canvas
          e.preventDefault();
        }}
      >
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {Icon && <Icon className="h-5 w-5" />}
            {title}
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 mt-6 overflow-y-auto">{children}</div>

        {hasEditAccess && (
          <div className="flex gap-2 pt-4 border-t">
            {isEditing ? (
              <>
                <Button
                  onClick={onCancel}
                  variant="outline"
                  className="flex-1"
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button onClick={onSave} className="flex-1" disabled={isSaving}>
                  Save Changes
                </Button>
              </>
            ) : (
              <>
                <Button onClick={onEdit} variant="outline" className="flex-1">
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button
                  onClick={onDelete}
                  variant="destructive"
                  className="flex-1"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { AgentsListView } from "./agents/AgentsListView";
import { AgentEditView } from "./agents/AgentEditView";
import type { AgentConfigId } from "@/lib/api/agentConfigs";
import { toAgentConfigId } from "@/lib/api/agentConfigs";

export function AgentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const editParam = searchParams.get("edit");
  const [editingId, setEditingId] = useState<AgentConfigId | null>(
    editParam ? toAgentConfigId(editParam) : null,
  );

  return (
    <>
      <AgentsListView onEdit={setEditingId} />

      <Sheet
        open={editingId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingId(null);
            setSearchParams({});
          }
        }}
      >
        <SheetContent className="sm:max-w-md p-0 gap-0">
          <VisuallyHidden>
            <SheetTitle>Configure Agent</SheetTitle>
          </VisuallyHidden>
          {editingId !== null && (
            <AgentEditView
              configId={editingId}
              onClose={() => setEditingId(null)}
            />
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

export default AgentsPage;

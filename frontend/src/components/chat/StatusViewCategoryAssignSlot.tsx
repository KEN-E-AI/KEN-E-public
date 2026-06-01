// CH-PRD-03 §2 in-scope: "CH-PRD-03 ships a placeholder mount point if CH-PRD-04 hasn't
// shipped (behind a flag); CH-PRD-04 replaces the placeholder."
//
// CH-PRD-04 hand-off contract: import StatusViewCategoryAssignSlot and drop it into the
// "Session Category" row inside SessionStatusView.tsx.  No local state needed — the inner
// CategoriesDropdown owns the assign mutation via useChatCategories().assign.
//
// When chat_categories_enabled is off this component returns null, so the surrounding
// CH-PRD-04 card is responsible for deciding whether to hide the containing row or render
// its own empty state.

import type { FlagKey } from "@/lib/featureFlags/types";
import type { ChatCategoryId, ChatSessionId } from "@/lib/chatApi";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { CategoriesDropdown } from "./CategoriesDropdown";

type StatusViewCategoryAssignSlotProps = {
  sessionId: ChatSessionId;
  currentCategoryId: ChatCategoryId | null;
};

export function StatusViewCategoryAssignSlot({
  sessionId,
  currentCategoryId,
}: StatusViewCategoryAssignSlotProps) {
  const { enabled, isLoading } = useFeatureFlag(
    "chat_categories_enabled" as FlagKey,
  );

  if (isLoading || !enabled) {
    return null;
  }

  return (
    <div data-testid="status-view-category-assign-slot">
      <CategoriesDropdown
        variant="assign"
        sessionId={sessionId}
        currentCategoryId={currentCategoryId}
      />
    </div>
  );
}

import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { ChatSessionId, TodoListView } from "@/lib/chatApi";
import { useTodoLists } from "@/hooks/useTodoLists";

type TodoListItemProps = {
  list: TodoListView;
};

function TodoListItem({ list }: TodoListItemProps) {
  const [isExpanded, setIsExpanded] = useState(list.is_current);
  const completedCount = list.items.filter((i) => i.completed).length;

  return (
    <div
      className={cn(
        "rounded-[var(--radius-md)] border-2 transition-all overflow-hidden",
        list.is_current
          ? "border-[var(--color-violet-300)] bg-[var(--color-bg-primary)]"
          : "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]",
      )}
    >
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full flex items-center gap-2 p-3 hover:bg-[var(--color-accent)] transition-all text-left"
        style={{
          transitionTimingFunction: "var(--ease-default)",
          transitionDuration: "var(--duration-fast)",
        }}
        aria-expanded={isExpanded}
      >
        {isExpanded ? (
          <ChevronDown
            className="size-4 text-[var(--color-text-tertiary)] shrink-0"
            aria-hidden="true"
          />
        ) : (
          <ChevronRight
            className="size-4 text-[var(--color-text-tertiary)] shrink-0"
            aria-hidden="true"
          />
        )}
        <span className="text-[var(--text-body-sm)] font-medium flex-1 min-w-0 truncate">
          {list.title}
        </span>
        {list.is_current && <Badge variant="info">Active</Badge>}
        <span
          className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] shrink-0"
          aria-label={`${completedCount} of ${list.items.length} completed`}
        >
          {completedCount}/{list.items.length}
        </span>
      </button>

      {isExpanded && list.items.length > 0 && (
        <div className="px-3 pb-3 space-y-2 border-t-2 border-dashed border-[var(--color-border-default)] pt-3">
          {list.items.map((item) => (
            <div key={item.item_id} className="flex items-start gap-2.5">
              <Checkbox
                checked={item.completed}
                disabled
                className="mt-0.5"
                aria-label={item.text}
              />
              <span
                className={cn(
                  "text-[var(--text-body-sm)]",
                  item.completed &&
                    "line-through text-[var(--color-text-tertiary)]",
                )}
              >
                {item.text}
              </span>
            </div>
          ))}
        </div>
      )}

      {isExpanded && list.items.length === 0 && (
        <div className="px-3 pb-3 border-t-2 border-dashed border-[var(--color-border-default)] pt-3">
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
            No items yet
          </p>
        </div>
      )}
    </div>
  );
}

type TodoListsPanelProps = {
  sessionId: ChatSessionId | null;
};

export function TodoListsPanel({ sessionId }: TodoListsPanelProps) {
  // Hook called unconditionally per Rules of Hooks; `enabled: sessionId != null`
  // inside useTodoLists prevents any network request when sessionId is null.
  const { data, isLoading, isError } = useTodoLists(sessionId);

  if (sessionId == null) return null;

  return (
    <Card
      className="p-5"
      accentColor="var(--color-accent-slot-5)"
      data-testid="todo-lists-panel"
    >
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2
          className="size-4 text-[var(--color-violet-500)]"
          aria-hidden="true"
        />
        <h3
          className="text-[var(--text-heading-sm)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          To Do Lists
        </h3>
      </div>

      <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mb-4">
        Tracks long tasks to ensure details are preserved during compaction.
      </p>

      {isLoading && (
        <div className="space-y-2" aria-label="Loading todo lists">
          <Skeleton className="h-10 w-full rounded-[var(--radius-md)]" />
          <Skeleton className="h-10 w-full rounded-[var(--radius-md)]" />
        </div>
      )}

      {isError && (
        <p className="text-[var(--text-caption)] text-[var(--color-error-text)]">
          Failed to load todo lists.
        </p>
      )}

      {!isLoading && !isError && data && data.todo_lists.length === 0 && (
        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
          No todo lists yet.
        </p>
      )}

      {!isLoading && !isError && data && data.todo_lists.length > 0 && (
        <div className="space-y-3">
          {data.todo_lists.map((list) => (
            <TodoListItem key={list.list_id} list={list} />
          ))}
        </div>
      )}
    </Card>
  );
}

// Flag-gating (chat_categories_enabled) is the mount-site's responsibility;
// this component renders regardless. When list.data is undefined (flag off →
// query disabled), it gracefully shows an empty list.
import { useRef, useState, useMemo } from "react";
import { ChevronDown, Plus, Trash2, X, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useChatCategories } from "@/hooks/useChatCategories";
import type {
  ChatCategory,
  ChatCategoryId,
  ChatSessionId,
} from "@/lib/chatApi";
import { CategoryExistsError } from "@/lib/chatApi";

type CategoriesDropdownProps =
  | {
      variant: "filter";
      value: ChatCategoryId | null;
      onChange: (v: ChatCategoryId | null) => void;
    }
  | {
      variant: "assign";
      sessionId: ChatSessionId;
      currentCategoryId: ChatCategoryId | null;
    };

export function CategoriesDropdown(props: CategoriesDropdownProps) {
  const { list, create, remove, assign } = useChatCategories();

  // ── Inline create form state ────────────────────────────────────────────────
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const createInputRef = useRef<HTMLInputElement>(null);

  // ── Delete confirm state ────────────────────────────────────────────────────
  const [categoryToDelete, setCategoryToDelete] = useState<ChatCategory | null>(
    null,
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // ── Sorted categories ───────────────────────────────────────────────────────
  const categories = useMemo(
    () =>
      [...(list.data ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
      ),
    [list.data],
  );

  // ── Helpers ─────────────────────────────────────────────────────────────────
  const selectedId =
    props.variant === "filter" ? props.value : props.currentCategoryId;

  const triggerLabel =
    props.variant === "filter"
      ? (list.data?.find((c) => c.category_id === selectedId)?.name ??
        "All sessions")
      : (list.data?.find((c) => c.category_id === selectedId)?.name ??
        "Uncategorized");

  function handleSelect(categoryId: ChatCategoryId | null) {
    if (props.variant === "filter") {
      props.onChange(categoryId);
    } else {
      assign.mutate({ sessionId: props.sessionId, categoryId });
    }
  }

  async function handleCreateSubmit() {
    const trimmed = createName.trim();
    if (!trimmed) return;
    setCreateError(null);
    try {
      const newCat = await create.mutateAsync(trimmed);
      setCreateName("");
      setShowCreateForm(false);
      if (props.variant === "assign") {
        assign.mutate({
          sessionId: props.sessionId,
          categoryId: newCat.category_id,
        });
      }
    } catch (err) {
      if (err instanceof CategoryExistsError) {
        setCreateError(`"${err.attemptedName}" already exists`);
      } else {
        console.error(
          "CategoriesDropdown.create: unexpected error creating category",
          err,
        );
        setCreateError("Failed to create category. Please try again.");
      }
    }
  }

  function openCreateForm() {
    setShowCreateForm(true);
    setCreateError(null);
    setCreateName("");
    // Focus input on next tick (after the DOM updates)
    requestAnimationFrame(() => createInputRef.current?.focus());
  }

  function handleContentKeyDown(e: React.KeyboardEvent) {
    if (e.key === "+") {
      e.preventDefault();
      if (!showCreateForm) {
        openCreateForm();
      } else {
        createInputRef.current?.focus();
      }
    }
  }

  async function handleConfirmDelete() {
    if (!categoryToDelete) return;
    setDeleteError(null);
    try {
      await remove.mutateAsync(categoryToDelete.category_id);
      setCategoryToDelete(null);
    } catch (err) {
      console.error(
        "CategoriesDropdown.delete: unexpected error deleting category",
        err,
      );
      setDeleteError("Failed to delete. Please try again.");
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between font-normal"
            data-testid={`categories-dropdown-${props.variant}-trigger`}
          >
            <span className="truncate">{triggerLabel}</span>
            <ChevronDown className="ml-2 size-4 shrink-0" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          className="w-64"
          align="start"
          onKeyDown={handleContentKeyDown}
        >
          {/* "All sessions" sentinel — filter variant only */}
          {props.variant === "filter" && (
            <DropdownMenuItem
              onSelect={() => handleSelect(null)}
              className="flex items-center gap-2"
            >
              <span
                className={cn(
                  "size-4 shrink-0",
                  selectedId === null ? "opacity-100" : "opacity-0",
                )}
              >
                <Check className="size-4" />
              </span>
              All sessions
            </DropdownMenuItem>
          )}

          {/* "Uncategorized" option */}
          <DropdownMenuItem
            onSelect={() => handleSelect(null)}
            className="flex items-center gap-2"
          >
            <span
              className={cn(
                "size-4 shrink-0",
                selectedId === null && props.variant === "assign"
                  ? "opacity-100"
                  : "opacity-0",
              )}
            >
              <Check className="size-4" />
            </span>
            Uncategorized
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          {/* Loading state */}
          {list.isPending && (
            <DropdownMenuItem disabled className="text-sm">
              Loading…
            </DropdownMenuItem>
          )}

          {/* Error state — distinguished from empty so the user knows the list failed to load */}
          {!list.isPending && list.isError && (
            <div
              className="px-2 py-1.5 text-sm text-[var(--color-error)]"
              role="alert"
            >
              Couldn&apos;t load categories. Try again later.
            </div>
          )}

          {/* Empty state message when no categories */}
          {!list.isPending && !list.isError && categories.length === 0 && (
            <div className="px-2 py-1.5 text-sm text-[var(--color-text-secondary)]">
              No categories yet
            </div>
          )}

          {/* Category rows */}
          {categories.map((cat) => (
            <DropdownMenuItem
              key={cat.category_id}
              onSelect={() => handleSelect(cat.category_id)}
              className="flex items-center gap-2 pr-1"
            >
              <span
                className={cn(
                  "size-4 shrink-0",
                  selectedId === cat.category_id ? "opacity-100" : "opacity-0",
                )}
              >
                <Check className="size-4" />
              </span>
              <span className="flex-1 truncate">{cat.name}</span>
              {/* Trash button — stops propagation so row selection doesn't also fire */}
              <button
                type="button"
                aria-label={`Delete category ${cat.name}`}
                className="ml-auto shrink-0 rounded p-1 opacity-60 hover:bg-[var(--color-error-bg)] hover:text-[var(--color-error)] hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-error)]"
                onClick={(e) => {
                  e.stopPropagation();
                  setCategoryToDelete(cat);
                }}
              >
                <Trash2 className="size-3.5" />
              </button>
            </DropdownMenuItem>
          ))}

          {categories.length > 0 && <DropdownMenuSeparator />}

          {/* Inline create form — lives OUTSIDE DropdownMenuItem to keep focus without closing the menu */}
          <div className="px-2 pb-2 pt-1">
            {!showCreateForm ? (
              <button
                type="button"
                className="flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-sm hover:bg-[var(--color-bg-subtle)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-violet-500)]"
                onClick={openCreateForm}
              >
                <Plus className="size-4 shrink-0" />
                New category
              </button>
            ) : (
              <div className="space-y-1.5">
                <div className="flex gap-1.5">
                  <Input
                    ref={createInputRef}
                    value={createName}
                    onChange={(e) => {
                      setCreateName(e.target.value);
                      setCreateError(null);
                    }}
                    placeholder="Category name…"
                    className="h-8 flex-1 text-sm"
                    aria-label="New category name"
                    aria-invalid={createError !== null}
                    aria-describedby={
                      createError !== null
                        ? "categories-dropdown-create-error"
                        : undefined
                    }
                    maxLength={64}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void handleCreateSubmit();
                      }
                      if (e.key === "Escape") {
                        setShowCreateForm(false);
                        setCreateName("");
                        setCreateError(null);
                      }
                    }}
                  />
                  <Button
                    size="sm"
                    className="h-8 px-2"
                    onClick={() => void handleCreateSubmit()}
                    disabled={!createName.trim() || create.isPending}
                  >
                    Add
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2"
                    aria-label="Cancel new category"
                    onClick={() => {
                      setShowCreateForm(false);
                      setCreateName("");
                      setCreateError(null);
                    }}
                  >
                    <X className="size-4" />
                  </Button>
                </div>
                {createError && (
                  <p
                    id="categories-dropdown-create-error"
                    className="text-xs text-[var(--color-error)]"
                    role="alert"
                  >
                    {createError}
                  </p>
                )}
              </div>
            )}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Delete confirm dialog — outside the DropdownMenu so it survives DropdownMenu unmount */}
      <AlertDialog
        open={categoryToDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCategoryToDelete(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &apos;{categoryToDelete?.name}&apos;?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Sessions will return to Uncategorized.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && (
            <p className="text-xs text-[var(--color-error)]" role="alert">
              {deleteError}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setCategoryToDelete(null);
                setDeleteError(null);
              }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-[var(--color-error)] text-white hover:bg-[var(--color-error)]/90"
              onClick={() => void handleConfirmDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { ScrollChevronButton } from "../item-card/ScrollChevronButton";
import { useScrollPosition } from "../hooks/useScrollPosition";
import type { ScrollableItemProps, KnowledgeGraphItem } from "../types";

/**
 * Reusable horizontal scrollable list with chevron buttons
 * Used for Categories, Competitors, Strengths, Weaknesses, etc.
 *
 * @template T - Type of items in the list (must extend KnowledgeGraphItem)
 */
export function HorizontalScrollList<T extends KnowledgeGraphItem>({
  items,
  selectedId,
  onItemClick,
  isLoading = false,
  emptyMessage = "No items found.",
  emptyMessageWithAction,
  onAdd,
  hasEditAccess = false,
  renderItem,
}: ScrollableItemProps<T>) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const {
    canScrollLeft,
    canScrollRight,
    scrollLeft,
    scrollRight,
    checkScrollPosition,
  } = useScrollPosition(scrollContainerRef, [items]);

  if (isLoading) {
    return (
      <div className="text-center py-8 text-dashboard-gray-500">Loading...</div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-dashboard-gray-500">
        {emptyMessage}
        {hasEditAccess &&
          emptyMessageWithAction &&
          ` ${emptyMessageWithAction}`}
      </div>
    );
  }

  return (
    <div className="relative">
      <ScrollChevronButton
        direction="left"
        onClick={scrollLeft}
        visible={canScrollLeft}
      />

      <div
        ref={scrollContainerRef}
        className="flex gap-3 overflow-x-auto px-2 py-2"
        onScroll={checkScrollPosition}
      >
        {items.map((item) => (
          <div key={item.node_id} onClick={() => onItemClick(item)}>
            {renderItem(item, selectedId === item.node_id)}
          </div>
        ))}
      </div>

      <ScrollChevronButton
        direction="right"
        onClick={scrollRight}
        visible={canScrollRight}
      />
    </div>
  );
}

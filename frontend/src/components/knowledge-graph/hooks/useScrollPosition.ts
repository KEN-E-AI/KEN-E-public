import { useState, useEffect, useCallback, type RefObject } from "react";
import { SCROLL_AMOUNT } from "../constants/layout";

/**
 * Hook to manage horizontal scroll position and chevron button visibility
 *
 * @param containerRef - Reference to the scrollable container element
 * @param deps - Dependencies to trigger scroll position recalculation
 * @returns Scroll state and control functions
 */
export function useScrollPosition(
  containerRef: RefObject<HTMLDivElement>,
  deps: any[] = [],
) {
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScrollPosition = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    setCanScrollLeft(container.scrollLeft > 0);
    setCanScrollRight(
      container.scrollLeft < container.scrollWidth - container.clientWidth - 1,
    );
  }, [containerRef]);

  const scrollLeft = useCallback(() => {
    containerRef.current?.scrollBy({
      left: -SCROLL_AMOUNT,
      behavior: "smooth",
    });
  }, [containerRef]);

  const scrollRight = useCallback(() => {
    containerRef.current?.scrollBy({ left: SCROLL_AMOUNT, behavior: "smooth" });
  }, [containerRef]);

  useEffect(() => {
    checkScrollPosition();
    const handleResize = () => checkScrollPosition();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [checkScrollPosition, ...deps]);

  return {
    canScrollLeft,
    canScrollRight,
    scrollLeft,
    scrollRight,
    checkScrollPosition,
  };
}

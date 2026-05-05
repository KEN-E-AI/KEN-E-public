import { ChevronLeft, ChevronRight } from "lucide-react";

interface ScrollChevronButtonProps {
  direction: "left" | "right";
  onClick: () => void;
  visible: boolean;
}

/**
 * Chevron button for horizontal scrolling
 * Appears as an overlay on the left or right side of scrollable containers
 */
export function ScrollChevronButton({
  direction,
  onClick,
  visible,
}: ScrollChevronButtonProps) {
  if (!visible) return null;

  const Icon = direction === "left" ? ChevronLeft : ChevronRight;
  const positionClass = direction === "left" ? "left-0" : "right-0";

  return (
    <button
      className={`absolute ${positionClass} top-0 bottom-0 z-20 bg-[var(--color-border-strong)] bg-opacity-75 px-3 flex items-center justify-center hover:bg-opacity-90 transition-opacity`}
      onClick={onClick}
      aria-label={`Scroll ${direction}`}
    >
      <Icon className="h-6 w-6 text-white" />
    </button>
  );
}

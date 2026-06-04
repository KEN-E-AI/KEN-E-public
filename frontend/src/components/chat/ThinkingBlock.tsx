import { useState, useEffect, useRef } from "react";
import { ChevronDown, Brain, Square } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

type ThinkingBlockProps = {
  isThinking: boolean;
  thoughts: string[];
  durationSeconds?: number;
  onStop?: () => void;
};

export function ThinkingBlock({
  isThinking,
  thoughts,
  durationSeconds,
  onStop,
}: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);

  // Promote to the full bordered "card" treatment only while actively thinking.
  // Once reasoning ends, the block demotes to an inline metadata line.
  const isPromoted = isThinking;

  // Auto-expand when thinking starts, auto-collapse when it ends
  useEffect(() => {
    if (isThinking) {
      setIsOpen(true);
    } else {
      // Brief delay before collapsing so user can see final thought
      const timer = setTimeout(() => setIsOpen(false), 600);
      return () => clearTimeout(timer);
    }
  }, [isThinking]);

  // Auto-scroll to bottom of thoughts as they stream in
  useEffect(() => {
    if (contentRef.current && isOpen) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [thoughts, isOpen]);

  const summaryText = isThinking ? "Reasoning..." : `${durationSeconds ?? 0}s`;

  return (
    <div className="relative rounded-[var(--radius-lg)] overflow-hidden">
      {/* Animated gradient border while thinking */}
      {isPromoted && (
        <motion.div
          className="absolute inset-0 rounded-[var(--radius-lg)]"
          style={{
            padding: "2px",
            background:
              "linear-gradient(90deg, var(--color-violet-400), var(--color-teal-400), var(--color-violet-400))",
            backgroundSize: "200% 100%",
          }}
          animate={{
            backgroundPosition: ["0% 0%", "200% 0%"],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "linear",
          }}
        >
          <div className="w-full h-full rounded-[calc(var(--radius-lg)-2px)] bg-[var(--color-bg-elevated)]" />
        </motion.div>
      )}

      <div
        className={cn(
          "relative",
          isPromoted &&
            "rounded-[var(--radius-lg)] bg-[var(--color-bg-elevated)] m-[2px]",
        )}
      >
        {/* Trigger / Summary Bar */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsOpen((prev) => !prev)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setIsOpen((prev) => !prev);
            }
          }}
          className={cn(
            "w-full flex items-center text-left group transition-colors hover:bg-[var(--color-accent)] cursor-pointer",
            isPromoted
              ? "gap-2 px-4 py-3 rounded-[var(--radius-lg)]"
              : "gap-1.5 px-1 py-0.5 rounded-[var(--radius-md)]",
          )}
        >
          <Brain
            className={cn(
              "shrink-0 transition-colors",
              isPromoted ? "size-4" : "size-3",
              isThinking
                ? "text-[var(--color-violet-500)]"
                : "text-[var(--color-text-tertiary)]",
            )}
          />
          <span
            className={cn(
              isPromoted ? "flex-1 text-[var(--text-body-sm)]" : "text-[11px]",
              isThinking
                ? "text-[var(--color-violet-500)] italic"
                : "text-[var(--color-text-tertiary)]",
            )}
          >
            {summaryText}
          </span>

          {/* Pulsing dots while thinking */}
          {isThinking && (
            <span className="flex gap-1 mr-2">
              <span
                className="size-1.5 rounded-full bg-[var(--color-violet-400)] animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <span
                className="size-1.5 rounded-full bg-[var(--color-violet-400)] animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <span
                className="size-1.5 rounded-full bg-[var(--color-violet-400)] animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </span>
          )}

          {/* Stop button while thinking */}
          {isThinking && onStop && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onStop();
              }}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-md)]",
                "bg-[var(--color-bg-primary)] border border-[var(--color-border-default)]",
                "text-[var(--text-caption)] text-[var(--color-text-secondary)]",
                "hover:bg-[#F97066]/10 hover:border-[#F97066]/40 hover:text-[#F97066]",
                "transition-colors duration-150 shrink-0",
              )}
              aria-label="Stop generating"
              title="Stop generating"
            >
              <Square className="size-3 fill-current" />
              <span>Stop</span>
            </button>
          )}

          <ChevronDown
            className={cn(
              "shrink-0 text-[var(--color-text-tertiary)] transition-transform duration-200",
              isPromoted ? "size-4" : "size-3",
              isOpen && "rotate-180",
            )}
          />
        </div>

        {/* Collapsible Content */}
        <AnimatePresence initial={false}>
          {isOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="overflow-hidden"
            >
              <div
                ref={contentRef}
                className={cn(
                  "max-h-40 overflow-y-auto",
                  isPromoted ? "px-4 pb-3" : "px-1 pb-1 pt-1",
                )}
              >
                <div
                  className={cn(
                    "space-y-2",
                    isPromoted &&
                      "border-t border-[var(--color-border-default)] pt-3",
                  )}
                >
                  {thoughts.map((thought, index) => (
                    <motion.p
                      key={index}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.05 }}
                      className="text-[11px] text-[var(--color-text-tertiary)] leading-relaxed"
                    >
                      {thought}
                    </motion.p>
                  ))}
                  {isThinking && thoughts.length === 0 && (
                    <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] italic">
                      Analyzing your request...
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

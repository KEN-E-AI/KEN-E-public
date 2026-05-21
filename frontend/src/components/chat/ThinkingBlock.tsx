import { useState, useEffect, useRef } from "react";
import { ChevronDown, Brain, Square } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface ThinkingBlockProps {
  isThinking: boolean;
  thoughts: string[];
  durationSeconds?: number;
  onStop?: () => void;
}

export function ThinkingBlock({
  isThinking,
  thoughts,
  durationSeconds,
  onStop,
}: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);

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

  const summaryText = isThinking
    ? "Reasoning..."
    : `Thought for ${durationSeconds ?? 0} second${(durationSeconds ?? 0) !== 1 ? "s" : ""}`;

  return (
    <div className="relative rounded-[var(--radius-lg)] overflow-hidden">
      {/* Animated gradient border while thinking */}
      {isThinking && (
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
          "relative rounded-[var(--radius-lg)] bg-[var(--color-bg-elevated)]",
          !isThinking && "border-2 border-[var(--color-border-default)]",
          isThinking && "m-[2px]",
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
          className="w-full flex items-center gap-2 px-4 py-3 text-left group transition-colors hover:bg-[var(--color-accent)] rounded-[var(--radius-lg)] cursor-pointer"
        >
          <Brain
            className={cn(
              "size-4 shrink-0 transition-colors",
              isThinking
                ? "text-[var(--color-violet-500)]"
                : "text-[var(--color-text-tertiary)]",
            )}
          />
          <span
            className={cn(
              "flex-1 text-[var(--text-body-sm)]",
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
              title="Stop generating"
            >
              <Square className="size-3 fill-current" />
              <span>Stop</span>
            </button>
          )}

          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform duration-200",
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
                className="px-4 pb-3 max-h-40 overflow-y-auto"
              >
                <div className="border-t border-[var(--color-border-default)] pt-3 space-y-2">
                  {thoughts.map((thought, index) => (
                    <motion.p
                      key={index}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.05 }}
                      className="text-[var(--text-caption)] text-[var(--color-text-secondary)] leading-relaxed"
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

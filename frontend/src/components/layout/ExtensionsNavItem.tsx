import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useExtensions } from "@/contexts/ExtensionsContext";
import { cn } from "@/lib/utils";

const HOVER_CLOSE_DELAY_MS = 150;

interface ExtensionsNavItemProps {
  item: { name: string; href: string; icon: LucideIcon };
  isActive: boolean;
}

export function ExtensionsNavItem({ item, isActive }: ExtensionsNavItemProps) {
  const { getActiveExtensionDefinitions } = useExtensions();
  const [hovered, setHovered] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeExtensions = getActiveExtensionDefinitions();

  const handleEnter = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setHovered(true);
  };

  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setHovered(false);
      timeoutRef.current = null;
    }, HOVER_CLOSE_DELAY_MS);
  };

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            to={item.href}
            className={cn(
              "flex items-center gap-2 p-2 lg:px-4 lg:py-2 rounded-[var(--radius-pill)] transition-all text-[var(--text-body-sm)] font-bold",
              isActive
                ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                : "text-[var(--color-text-tertiary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5",
            )}
            style={{
              transitionTimingFunction: "var(--ease-bounce)",
              transitionDuration: "var(--duration-fast)",
            }}
          >
            <item.icon className="size-4" />
            <span className="hidden lg:inline">{item.name}</span>
          </Link>
        </TooltipTrigger>
        <TooltipContent className="lg:hidden">{item.name}</TooltipContent>
      </Tooltip>

      {hovered && (
        <div
          role="menu"
          aria-label="Active extensions"
          className="absolute top-full left-0 mt-1 min-w-[200px] bg-[var(--color-bg-elevated)] border-2 border-[var(--color-border-default)] rounded-[var(--radius-md)] shadow-lg py-1 z-50"
        >
          {activeExtensions.map((p) => (
            <Link
              key={p.id}
              to={`/extensions/${p.slug}`}
              role="menuitem"
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] transition-colors"
              onClick={() => setHovered(false)}
            >
              <div
                className={`size-6 rounded-[var(--radius-sm)] flex items-center justify-center ${p.rotation}`}
                style={{ backgroundColor: p.color }}
              >
                <p.icon className="size-3 text-[var(--color-text-inverse)]" />
              </div>
              <span>{p.name}</span>
            </Link>
          ))}
          {activeExtensions.length > 0 && (
            <div className="border-t border-[var(--color-border-default)] my-1" />
          )}
          <Link
            to="/extensions"
            role="menuitem"
            className="flex items-center gap-2.5 px-3 py-2 text-xs text-muted-foreground hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] transition-colors"
            onClick={() => setHovered(false)}
          >
            Browse all extensions
          </Link>
        </div>
      )}
    </div>
  );
}

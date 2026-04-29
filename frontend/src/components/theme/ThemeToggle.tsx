import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { mode, toggle } = useTheme();

  return (
    <button
      aria-label="Toggle theme"
      onClick={toggle}
      className="size-9 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] flex items-center justify-center rotate-[8deg] transition-all hover:rotate-0 hover:scale-110"
      style={{
        transitionTimingFunction: "var(--ease-bounce)",
        transitionDuration: "var(--duration-fast)",
      }}
    >
      <Moon className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0 text-[var(--color-slate-500)]" />
      <Sun className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100 text-[var(--color-amber-400)]" />
      <span className="sr-only">Toggle theme</span>
    </button>
  );
}

import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-[var(--color-bg-elevated)] group-[.toaster]:text-[var(--color-text-primary)] group-[.toaster]:border-2 group-[.toaster]:border-[var(--color-border-default)] group-[.toaster]:shadow-[var(--shadow-lg)] group-[.toaster]:rounded-[var(--radius-lg)]",
          description: "group-[.toast]:text-[var(--color-text-tertiary)]",
          actionButton:
            "group-[.toast]:bg-[var(--color-violet-500)] group-[.toast]:text-[var(--color-text-inverse)]",
          cancelButton:
            "group-[.toast]:bg-[var(--color-surface-muted)] group-[.toast]:text-[var(--color-text-tertiary)]",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };

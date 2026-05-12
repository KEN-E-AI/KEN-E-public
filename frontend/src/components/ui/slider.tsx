import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

type SliderProps = React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
  thumbContent?: React.ReactNode;
};

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  SliderProps
>(
  (
    {
      className,
      "aria-label": ariaLabel,
      "aria-labelledby": ariaLabelledBy,
      thumbContent,
      ...props
    },
    ref,
  ) => (
    <SliderPrimitive.Root
      ref={ref}
      data-slot="slider"
      className={cn(
        "relative flex w-full touch-none select-none items-center",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
        <SliderPrimitive.Range className="absolute h-full bg-[var(--color-violet-500)]" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        className={cn(
          "block rounded-full border-2 border-[var(--color-violet-500)] bg-[var(--color-bg-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-violet-300)] disabled:pointer-events-none disabled:opacity-50",
          thumbContent !== undefined
            ? "flex items-center justify-center size-7 text-[10px] font-bold text-[var(--color-violet-500)] tabular-nums"
            : "size-5",
        )}
      >
        {thumbContent}
      </SliderPrimitive.Thumb>
    </SliderPrimitive.Root>
  ),
);
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };

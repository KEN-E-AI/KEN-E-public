import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Logo } from "./Logo";

const SIZE_CLASS_BY_PROP = {
  sm: "size-15",
  md: "size-18",
  lg: "size-24",
  xl: "size-32",
  "2xl": "size-48",
} as const;

const TEXT_CLASS_BY_PROP = {
  sm: "text-lg",
  md: "text-xl",
  lg: "text-3xl",
  xl: "text-5xl",
  "2xl": "text-7xl",
} as const;

function getSvgWrapper(container: HTMLElement): HTMLElement {
  const svg = container.querySelector("svg");
  if (!svg) throw new Error("Logo SVG not found in rendered output");
  return svg.parentElement as HTMLElement;
}

describe("Logo", () => {
  describe("size prop", () => {
    (Object.keys(SIZE_CLASS_BY_PROP) as Array<keyof typeof SIZE_CLASS_BY_PROP>).forEach(
      (size) => {
        test(`size="${size}" applies the ${SIZE_CLASS_BY_PROP[size]} class to the SVG wrapper`, () => {
          const { container } = render(<Logo size={size} />);
          expect(getSvgWrapper(container)).toHaveClass(
            SIZE_CLASS_BY_PROP[size],
          );
        });
      },
    );

    test('default size is "md"', () => {
      const { container } = render(<Logo />);
      expect(getSvgWrapper(container)).toHaveClass(SIZE_CLASS_BY_PROP.md);
    });
  });

  describe("variant prop", () => {
    test('variant="full" renders the KEN-E wordmark', () => {
      render(<Logo variant="full" />);
      expect(
        screen.getByRole("heading", { name: /KEN-E/ }),
      ).toBeInTheDocument();
    });

    test('default variant is "full"', () => {
      render(<Logo />);
      expect(
        screen.getByRole("heading", { name: /KEN-E/ }),
      ).toBeInTheDocument();
    });

    test('variant="icon" hides the KEN-E wordmark', () => {
      render(<Logo variant="icon" />);
      expect(
        screen.queryByRole("heading", { name: /KEN-E/ }),
      ).not.toBeInTheDocument();
    });
  });

  describe("size prop drives wordmark text class", () => {
    (Object.keys(TEXT_CLASS_BY_PROP) as Array<keyof typeof TEXT_CLASS_BY_PROP>).forEach(
      (size) => {
        test(`size="${size}" applies ${TEXT_CLASS_BY_PROP[size]} to the wordmark`, () => {
          render(<Logo size={size} variant="full" />);
          expect(screen.getByRole("heading", { name: /KEN-E/ })).toHaveClass(
            TEXT_CLASS_BY_PROP[size],
          );
        });
      },
    );
  });
});

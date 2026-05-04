import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

describe("keyboard navigation", () => {
  describe("Button", () => {
    it("is reachable via Tab and activatable via Enter", async () => {
      const user = userEvent.setup();
      let clicked = false;
      render(<Button onClick={() => { clicked = true; }}>Save</Button>);

      await user.tab();
      expect(screen.getByRole("button", { name: "Save" })).toHaveFocus();

      await user.keyboard("{Enter}");
      expect(clicked).toBe(true);
    });

    it("is activatable via Space", async () => {
      const user = userEvent.setup();
      let clicked = false;
      render(<Button onClick={() => { clicked = true; }}>Save</Button>);

      await user.tab();
      await user.keyboard(" ");
      expect(clicked).toBe(true);
    });

    it("disabled button is not reachable via Tab", async () => {
      const user = userEvent.setup();
      render(
        <>
          <Button disabled>Unavailable</Button>
          <Button>After</Button>
        </>,
      );

      await user.tab();
      // The disabled button is skipped; the "After" button should receive focus
      expect(screen.getByRole("button", { name: "After" })).toHaveFocus();
      expect(screen.getByRole("button", { name: "Unavailable" })).not.toHaveFocus();
    });
  });

  describe("ThemeToggle", () => {
    it("is reachable via Tab and toggles theme via Enter", async () => {
      const user = userEvent.setup();
      render(
        <ThemeProvider>
          <ThemeToggle />
        </ThemeProvider>,
      );

      await user.tab();
      const btn = screen.getByRole("button", { name: "Toggle theme" });
      expect(btn).toHaveFocus();

      await user.keyboard("{Enter}");
      expect(document.documentElement.classList.contains("dark")).toBe(true);
    });
  });
});

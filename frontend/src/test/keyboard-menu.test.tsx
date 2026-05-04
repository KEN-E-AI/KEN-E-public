import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

describe("keyboard: arrow key navigation in composite widgets", () => {
  describe("Tabs", () => {
    it("Right arrow moves focus to the next tab trigger", async () => {
      const user = userEvent.setup();
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
          <TabsContent value="tab3">Content 3</TabsContent>
        </Tabs>,
      );

      // Tab into the tablist — first (selected) trigger receives focus
      await user.tab();
      expect(screen.getByRole("tab", { name: "Tab 1" })).toHaveFocus();

      await user.keyboard("{ArrowRight}");
      expect(screen.getByRole("tab", { name: "Tab 2" })).toHaveFocus();
    });

    it("Left arrow moves focus to the previous tab trigger", async () => {
      const user = userEvent.setup();
      render(
        <Tabs defaultValue="tab2">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
          <TabsContent value="tab3">Content 3</TabsContent>
        </Tabs>,
      );

      // Tab into the tablist — selected trigger (Tab 2) receives focus
      await user.tab();
      expect(screen.getByRole("tab", { name: "Tab 2" })).toHaveFocus();

      await user.keyboard("{ArrowLeft}");
      expect(screen.getByRole("tab", { name: "Tab 1" })).toHaveFocus();
    });

    it("Home jumps to the first tab; End jumps to the last", async () => {
      const user = userEvent.setup();
      render(
        <Tabs defaultValue="tab2">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
          <TabsContent value="tab3">Content 3</TabsContent>
        </Tabs>,
      );

      await user.tab();
      expect(screen.getByRole("tab", { name: "Tab 2" })).toHaveFocus();

      await user.keyboard("{End}");
      expect(screen.getByRole("tab", { name: "Tab 3" })).toHaveFocus();

      await user.keyboard("{Home}");
      expect(screen.getByRole("tab", { name: "Tab 1" })).toHaveFocus();
    });
  });

  describe("DropdownMenu", () => {
    it("Down arrow focuses the first item after opening", async () => {
      const user = userEvent.setup();
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item A</DropdownMenuItem>
            <DropdownMenuItem>Item B</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>,
      );

      await user.click(screen.getByRole("button", { name: "Open" }));
      expect(screen.getByRole("menu")).toBeInTheDocument();

      await user.keyboard("{ArrowDown}");
      expect(screen.getByRole("menuitem", { name: "Item A" })).toHaveFocus();
    });

    it("Down then Up arrows navigate between items", async () => {
      const user = userEvent.setup();
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item A</DropdownMenuItem>
            <DropdownMenuItem>Item B</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>,
      );

      await user.click(screen.getByRole("button", { name: "Open" }));

      await user.keyboard("{ArrowDown}");
      expect(screen.getByRole("menuitem", { name: "Item A" })).toHaveFocus();

      await user.keyboard("{ArrowDown}");
      expect(screen.getByRole("menuitem", { name: "Item B" })).toHaveFocus();

      await user.keyboard("{ArrowUp}");
      expect(screen.getByRole("menuitem", { name: "Item A" })).toHaveFocus();
    });

    it("Home jumps to the first item; End jumps to the last", async () => {
      const user = userEvent.setup();
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item A</DropdownMenuItem>
            <DropdownMenuItem>Item B</DropdownMenuItem>
            <DropdownMenuItem>Item C</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>,
      );

      await user.click(screen.getByRole("button", { name: "Open" }));
      await user.keyboard("{ArrowDown}");

      await user.keyboard("{End}");
      expect(screen.getByRole("menuitem", { name: "Item C" })).toHaveFocus();

      await user.keyboard("{Home}");
      expect(screen.getByRole("menuitem", { name: "Item A" })).toHaveFocus();
    });

    it("Trigger is keyboard-activatable (Enter opens the menu and focuses the first item)", async () => {
      const user = userEvent.setup();
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item A</DropdownMenuItem>
            <DropdownMenuItem>Item B</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>,
      );

      // Tab to the trigger — keyboard-only invocation, no mouse.
      await user.tab();
      expect(screen.getByRole("button", { name: "Open" })).toHaveFocus();

      await user.keyboard("{Enter}");
      expect(screen.getByRole("menu")).toBeInTheDocument();
      expect(screen.getByRole("menuitem", { name: "Item A" })).toHaveFocus();
    });
  });

  describe("Select (Listbox)", () => {
    it("Trigger is keyboard-activatable (Enter opens the listbox)", async () => {
      const user = userEvent.setup();
      render(
        <Select>
          <SelectTrigger aria-label="Pick a fruit">
            <SelectValue placeholder="Pick one" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="apple">Apple</SelectItem>
            <SelectItem value="banana">Banana</SelectItem>
            <SelectItem value="cherry">Cherry</SelectItem>
          </SelectContent>
        </Select>,
      );

      const trigger = screen.getByRole("combobox", { name: "Pick a fruit" });
      await user.tab();
      expect(trigger).toHaveFocus();

      await user.keyboard("{Enter}");
      expect(await screen.findByRole("listbox")).toBeInTheDocument();
    });
  });
});

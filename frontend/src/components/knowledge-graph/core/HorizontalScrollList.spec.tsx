import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HorizontalScrollList } from "./HorizontalScrollList";

describe("HorizontalScrollList", () => {
  const mockItems = [
    { id: "1", name: "Item 1" },
    { id: "2", name: "Item 2" },
    { id: "3", name: "Item 3" },
  ];

  const mockRenderItem = (item: (typeof mockItems)[0], isSelected: boolean) => (
    <div
      data-testid={`item-${item.id}`}
      className={isSelected ? "selected" : ""}
    >
      {item.name}
    </div>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render list of items", () => {
    render(
      <HorizontalScrollList
        items={mockItems}
        selectedId="1"
        onItemClick={vi.fn()}
        renderItem={mockRenderItem}
      />,
    );

    expect(screen.getByTestId("item-1")).toBeInTheDocument();
    expect(screen.getByTestId("item-2")).toBeInTheDocument();
    expect(screen.getByTestId("item-3")).toBeInTheDocument();
  });

  it("should highlight selected item", () => {
    render(
      <HorizontalScrollList
        items={mockItems}
        selectedId="2"
        onItemClick={vi.fn()}
        renderItem={mockRenderItem}
      />,
    );

    const selectedItem = screen.getByTestId("item-2");
    expect(selectedItem.className).toContain("selected");
  });

  it("should call onItemClick when item is clicked", () => {
    const handleClick = vi.fn();

    render(
      <HorizontalScrollList
        items={mockItems}
        selectedId="1"
        onItemClick={handleClick}
        renderItem={mockRenderItem}
      />,
    );

    fireEvent.click(screen.getByTestId("item-2"));

    expect(handleClick).toHaveBeenCalledWith("2");
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("should render custom item components via renderItem", () => {
    const customRenderItem = (
      item: (typeof mockItems)[0],
      isSelected: boolean,
    ) => (
      <div data-testid={`custom-${item.id}`} className="custom">
        Custom: {item.name}
      </div>
    );

    render(
      <HorizontalScrollList
        items={mockItems}
        selectedId="1"
        onItemClick={vi.fn()}
        renderItem={customRenderItem}
      />,
    );

    const customItem = screen.getByTestId("custom-1");
    expect(customItem).toBeInTheDocument();
    expect(customItem.textContent).toContain("Custom: Item 1");
    expect(customItem.className).toContain("custom");
  });

  it("should render empty list without errors", () => {
    const { container } = render(
      <HorizontalScrollList
        items={[]}
        selectedId={null}
        onItemClick={vi.fn()}
        renderItem={mockRenderItem}
      />,
    );

    expect(container.querySelector('[data-testid^="item-"]')).toBeNull();
  });

  it("should handle null selectedId", () => {
    render(
      <HorizontalScrollList
        items={mockItems}
        selectedId={null}
        onItemClick={vi.fn()}
        renderItem={mockRenderItem}
      />,
    );

    mockItems.forEach((item) => {
      const element = screen.getByTestId(`item-${item.id}`);
      expect(element.className).not.toContain("selected");
    });
  });
});

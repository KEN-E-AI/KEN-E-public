import { describe, test, expect } from "vitest";
import {
  calculateCenteredStartX,
  calculateChildNodeX,
  calculateChildNodeY,
} from "./layoutCalculations";
import { DIAGRAM_LAYOUT } from "../constants/layout";

describe("layoutCalculations", () => {
  describe("calculateCenteredStartX", () => {
    test("calculates correct start X for single node", () => {
      const result = calculateCenteredStartX(1);
      const expectedTotalWidth =
        DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH - DIAGRAM_LAYOUT.HORIZONTAL_GAP;
      const expected = DIAGRAM_LAYOUT.PARENT_NODE_X - expectedTotalWidth / 2;

      expect(result).toBe(expected);
    });

    test("calculates correct start X for three nodes", () => {
      const result = calculateCenteredStartX(3);
      const expectedTotalWidth =
        3 * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH - DIAGRAM_LAYOUT.HORIZONTAL_GAP;
      const expected = DIAGRAM_LAYOUT.PARENT_NODE_X - expectedTotalWidth / 2;

      expect(result).toBe(expected);
    });

    test("handles zero nodes", () => {
      const result = calculateCenteredStartX(0);
      const expected =
        DIAGRAM_LAYOUT.PARENT_NODE_X + DIAGRAM_LAYOUT.HORIZONTAL_GAP / 2;

      expect(result).toBe(expected);
    });

    test("handles large number of nodes", () => {
      const result = calculateCenteredStartX(10);
      const expectedTotalWidth =
        10 * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH - DIAGRAM_LAYOUT.HORIZONTAL_GAP;
      const expected = DIAGRAM_LAYOUT.PARENT_NODE_X - expectedTotalWidth / 2;

      expect(result).toBe(expected);
    });
  });

  describe("calculateChildNodeX", () => {
    test("calculates correct X for first node", () => {
      const result = calculateChildNodeX(0, 3);
      const startX = calculateCenteredStartX(3);

      expect(result).toBe(startX);
    });

    test("calculates correct X for second node", () => {
      const result = calculateChildNodeX(1, 3);
      const startX = calculateCenteredStartX(3);
      const expected = startX + DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;

      expect(result).toBe(expected);
    });

    test("calculates correct X for third node", () => {
      const result = calculateChildNodeX(2, 3);
      const startX = calculateCenteredStartX(3);
      const expected = startX + 2 * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;

      expect(result).toBe(expected);
    });

    test("spaces nodes evenly", () => {
      const node0 = calculateChildNodeX(0, 3);
      const node1 = calculateChildNodeX(1, 3);
      const node2 = calculateChildNodeX(2, 3);

      expect(node1 - node0).toBe(DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH);
      expect(node2 - node1).toBe(DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH);
    });

    test("handles single node", () => {
      const result = calculateChildNodeX(0, 1);
      const startX = calculateCenteredStartX(1);

      expect(result).toBe(startX);
    });

    test("handles edge case of index equal to nodeCount", () => {
      const result = calculateChildNodeX(3, 3);
      const startX = calculateCenteredStartX(3);
      const expected = startX + 3 * DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH;

      expect(result).toBe(expected);
    });
  });

  describe("calculateChildNodeY", () => {
    test("calculates correct Y position", () => {
      const result = calculateChildNodeY();
      const expected =
        DIAGRAM_LAYOUT.PARENT_NODE_Y + DIAGRAM_LAYOUT.VERTICAL_SPACING;

      expect(result).toBe(expected);
    });

    test("returns same value on multiple calls", () => {
      const result1 = calculateChildNodeY();
      const result2 = calculateChildNodeY();

      expect(result1).toBe(result2);
    });

    test("returns positive value", () => {
      const result = calculateChildNodeY();

      expect(result).toBeGreaterThan(0);
    });
  });

  describe("integration tests", () => {
    test("centers nodes symmetrically around parent", () => {
      const nodeCount = 4;
      const nodes = Array.from({ length: nodeCount }, (_, i) =>
        calculateChildNodeX(i, nodeCount),
      );

      // Calculate center of all nodes
      const minX = Math.min(...nodes);
      const maxX = Math.max(...nodes);
      const centerOfNodes = (minX + maxX) / 2;

      // Should be close to parent X (within half a node width)
      expect(
        Math.abs(centerOfNodes - DIAGRAM_LAYOUT.PARENT_NODE_X),
      ).toBeLessThan(DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH / 2);
    });

    test("maintains consistent spacing for different node counts", () => {
      const spacings = [2, 3, 5, 7].map((count) => {
        const node0 = calculateChildNodeX(0, count);
        const node1 = calculateChildNodeX(1, count);
        return node1 - node0;
      });

      // All spacings should be equal to NODE_TOTAL_WIDTH
      spacings.forEach((spacing) => {
        expect(spacing).toBe(DIAGRAM_LAYOUT.NODE_TOTAL_WIDTH);
      });
    });
  });
});

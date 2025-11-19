/**
 * Unit tests for SubstituteProductService
 *
 * Tests the unique link/unlink functionality for substitute products.
 * Basic CRUD operations are covered by integration tests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { substituteProductService } from "./substituteProductService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

// Mock the api module
vi.mock("@/lib/api");

describe("SubstituteProductService", () => {
  const mockAccountId = "acc_test123" as AccountId;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("linkProduct", () => {
    it("should call POST endpoint with product_node_id", async () => {
      const substituteProductId = "subprod_test456";
      const productNodeId = "prod_test789";

      vi.mocked(api.post).mockResolvedValue({ data: {} });

      await substituteProductService.linkProduct(
        mockAccountId,
        substituteProductId,
        productNodeId,
      );

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${mockAccountId}/substitute-products/${substituteProductId}/link-product`,
        { product_node_id: productNodeId },
      );
      expect(api.post).toHaveBeenCalledTimes(1);
    });

    it("should handle API errors gracefully", async () => {
      const substituteProductId = "subprod_test456";
      const productNodeId = "prod_test789";

      vi.mocked(api.post).mockRejectedValue(new Error("Product not found"));

      await expect(
        substituteProductService.linkProduct(
          mockAccountId,
          substituteProductId,
          productNodeId,
        ),
      ).rejects.toThrow("Product not found");
    });
  });

  describe("unlinkProduct", () => {
    it("should call DELETE endpoint with correct path", async () => {
      const substituteProductId = "subprod_test456";
      const productNodeId = "prod_test789";

      vi.mocked(api.delete).mockResolvedValue({ data: {} });

      await substituteProductService.unlinkProduct(
        mockAccountId,
        substituteProductId,
        productNodeId,
      );

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${mockAccountId}/substitute-products/${substituteProductId}/unlink-product/${productNodeId}`,
      );
      expect(api.delete).toHaveBeenCalledTimes(1);
    });

    it("should handle unlinking non-existent relationship", async () => {
      const substituteProductId = "subprod_test456";
      const productNodeId = "prod_test789";

      vi.mocked(api.delete).mockRejectedValue(
        new Error("Relationship not found"),
      );

      await expect(
        substituteProductService.unlinkProduct(
          mockAccountId,
          substituteProductId,
          productNodeId,
        ),
      ).rejects.toThrow("Relationship not found");
    });
  });

  describe("list", () => {
    it("should include both competitor_node_id and product_node_id filters", async () => {
      const competitorId = "comp_test123";
      const productNodeId = "prod_test456";
      const mockResponse = {
        data: {
          products: [],
          total_count: 0,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      await substituteProductService.list(
        mockAccountId,
        competitorId,
        productNodeId,
      );

      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${mockAccountId}/substitute-products`,
        {
          params: {
            skip: 0,
            limit: 1000,
            competitor_node_id: competitorId,
            product_node_id: productNodeId,
          },
        },
      );
    });

    it("should handle optional filter parameters", async () => {
      const mockResponse = {
        data: {
          products: [],
          total_count: 0,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      await substituteProductService.list(mockAccountId);

      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${mockAccountId}/substitute-products`,
        {
          params: {
            skip: 0,
            limit: 1000,
          },
        },
      );
    });
  });
});

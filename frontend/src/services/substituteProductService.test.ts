import { describe, it, expect, vi, beforeEach } from "vitest";
import { substituteProductService } from "./substituteProductService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("SubstituteProductService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;
  const COMPETITOR_NODE_ID = "competitor_node_123";
  const SUBSTITUTE_NODE_ID = "substitute_node_789";
  const PRODUCT_NODE_ID = "product_node_456";

  const MOCK_SUBSTITUTE = {
    node_id: SUBSTITUTE_NODE_ID,
    account_id: ACCOUNT_ID,
    product_name: "Competitor Product X",
    description: "Alternative product offered by competitor",
    references: ["https://example.com/product"],
    product_detail_page: "https://competitor.com/product-x",
    competitor_node_id: COMPETITOR_NODE_ID,
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
    created_by: "user_123",
    last_modified_by: "user_123",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("list", () => {
    it("should fetch substitutes with default pagination", async () => {
      const MOCK_RESPONSE = {
        products: [MOCK_SUBSTITUTE],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await substituteProductService.list(ACCOUNT_ID);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        { params: { skip: 0, limit: 1000 } },
      );
    });

    it("should fetch substitutes filtered by competitor", async () => {
      const MOCK_RESPONSE = {
        products: [MOCK_SUBSTITUTE],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await substituteProductService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 0,
            limit: 1000,
          },
        },
      );
    });

    it("should fetch substitutes filtered by product", async () => {
      const MOCK_RESPONSE = {
        products: [MOCK_SUBSTITUTE],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await substituteProductService.list(
        ACCOUNT_ID,
        undefined,
        PRODUCT_NODE_ID,
      );

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        {
          params: {
            product_node_id: PRODUCT_NODE_ID,
            skip: 0,
            limit: 1000,
          },
        },
      );
    });

    it("should fetch substitutes with custom pagination", async () => {
      const MOCK_RESPONSE = {
        products: [MOCK_SUBSTITUTE],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await substituteProductService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
        undefined,
        20,
        50,
      );

      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 20,
            limit: 50,
          },
        },
      );
    });

    it("should return empty list when no substitutes exist", async () => {
      const EMPTY_RESPONSE = {
        products: [],
        total_count: 0,
      };

      vi.mocked(api.get).mockResolvedValue({ data: EMPTY_RESPONSE });

      const result = await substituteProductService.list(ACCOUNT_ID);

      expect(result.products).toEqual([]);
      expect(result.total_count).toBe(0);
    });
  });

  describe("create", () => {
    it("should create a new substitute product linked to competitor", async () => {
      const CREATE_DATA = {
        product_name: "Alternative Solution",
        description: "Competitor's alternative offering",
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_SUBSTITUTE });

      const result = await substituteProductService.create(
        ACCOUNT_ID,
        CREATE_DATA,
      );

      expect(result).toEqual(MOCK_SUBSTITUTE);
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        CREATE_DATA,
      );
    });

    it("should create a substitute with product detail page", async () => {
      const CREATE_DATA = {
        product_name: "Premium Alternative",
        description: "High-end substitute product",
        references: ["https://example.com/ref"],
        product_detail_page: "https://competitor.com/premium",
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_SUBSTITUTE });

      await substituteProductService.create(ACCOUNT_ID, CREATE_DATA);

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products`,
        CREATE_DATA,
      );
    });
  });

  describe("update", () => {
    it("should update substitute product_name", async () => {
      const UPDATE_DATA = { product_name: "Updated Product Name" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_SUBSTITUTE });

      await substituteProductService.update(
        ACCOUNT_ID,
        SUBSTITUTE_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products/${SUBSTITUTE_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update multiple fields", async () => {
      const UPDATE_DATA = {
        product_name: "New Product Name",
        description: "New description",
        product_detail_page: "https://new-url.com",
        references: ["https://new.com"],
      };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_SUBSTITUTE });

      await substituteProductService.update(
        ACCOUNT_ID,
        SUBSTITUTE_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products/${SUBSTITUTE_NODE_ID}`,
        UPDATE_DATA,
      );
    });
  });

  describe("delete", () => {
    it("should delete a substitute product by node_id", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      await substituteProductService.delete(ACCOUNT_ID, SUBSTITUTE_NODE_ID);

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products/${SUBSTITUTE_NODE_ID}`,
      );
    });
  });

  describe("linkProduct", () => {
    it("should link our product to competitor substitute product", async () => {
      vi.mocked(api.post).mockResolvedValue({
        data: {
          message: "Product linked to substitute product successfully",
          product_node_id: PRODUCT_NODE_ID,
          substitute_product_node_id: SUBSTITUTE_NODE_ID,
        },
      });

      await substituteProductService.linkProduct(
        ACCOUNT_ID,
        SUBSTITUTE_NODE_ID,
        PRODUCT_NODE_ID,
      );

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products/${SUBSTITUTE_NODE_ID}/link-product`,
        { product_node_id: PRODUCT_NODE_ID },
      );
    });
  });

  describe("unlinkProduct", () => {
    it("should unlink our product from competitor substitute product", async () => {
      vi.mocked(api.delete).mockResolvedValue({
        data: {
          message: "Product unlinked from substitute product successfully",
        },
      });

      await substituteProductService.unlinkProduct(
        ACCOUNT_ID,
        SUBSTITUTE_NODE_ID,
        PRODUCT_NODE_ID,
      );

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/substitute-products/${SUBSTITUTE_NODE_ID}/unlink-product/${PRODUCT_NODE_ID}`,
      );
    });
  });
});

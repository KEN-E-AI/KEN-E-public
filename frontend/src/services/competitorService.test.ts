import { describe, it, expect, vi, beforeEach } from "vitest";
import { competitorService } from "./competitorService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("CompetitorService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;
  const COMPETITOR_NODE_ID = "competitor_node_123";

  const MOCK_COMPETITOR = {
    node_id: COMPETITOR_NODE_ID,
    account_id: ACCOUNT_ID,
    display_name: "Test Competitor",
    description: "A test competitor company",
    references: ["https://example.com/competitor"],
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
    created_by: "user_123",
    last_modified_by: "user_123",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("list", () => {
    it("should fetch competitors with default pagination", async () => {
      const MOCK_RESPONSE = {
        competitors: [MOCK_COMPETITOR],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorService.list(ACCOUNT_ID);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors`,
        { params: { skip: 0, limit: 1000 } },
      );
    });

    it("should fetch competitors with custom pagination", async () => {
      const MOCK_RESPONSE = {
        competitors: [MOCK_COMPETITOR],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorService.list(ACCOUNT_ID, 10, 50);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors`,
        { params: { skip: 10, limit: 50 } },
      );
    });

    it("should return empty list when no competitors exist", async () => {
      const EMPTY_RESPONSE = {
        competitors: [],
        total_count: 0,
      };

      vi.mocked(api.get).mockResolvedValue({ data: EMPTY_RESPONSE });

      const result = await competitorService.list(ACCOUNT_ID);

      expect(result.competitors).toEqual([]);
      expect(result.total_count).toBe(0);
    });
  });

  describe("get", () => {
    it("should fetch a single competitor by node_id", async () => {
      vi.mocked(api.get).mockResolvedValue({ data: MOCK_COMPETITOR });

      const result = await competitorService.get(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toEqual(MOCK_COMPETITOR);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors/${COMPETITOR_NODE_ID}`,
      );
    });

    it("should include all competitor fields", async () => {
      vi.mocked(api.get).mockResolvedValue({ data: MOCK_COMPETITOR });

      const result = await competitorService.get(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toHaveProperty("node_id");
      expect(result).toHaveProperty("display_name");
      expect(result).toHaveProperty("description");
      expect(result).toHaveProperty("references");
      expect(result).toHaveProperty("created_time");
    });
  });

  describe("create", () => {
    it("should create a new competitor with required fields", async () => {
      const CREATE_DATA = {
        display_name: "New Competitor",
        description: "A new competitor",
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_COMPETITOR });

      const result = await competitorService.create(ACCOUNT_ID, CREATE_DATA);

      expect(result).toEqual(MOCK_COMPETITOR);
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors`,
        CREATE_DATA,
      );
    });

    it("should create a competitor with references", async () => {
      const CREATE_DATA = {
        display_name: "Competitor with Refs",
        description: "Competitor with references",
        references: ["https://example.com/ref1", "https://example.com/ref2"],
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_COMPETITOR });

      const result = await competitorService.create(ACCOUNT_ID, CREATE_DATA);

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors`,
        CREATE_DATA,
      );
    });
  });

  describe("update", () => {
    it("should update competitor display_name", async () => {
      const UPDATE_DATA = { display_name: "Updated Name" };
      const UPDATED_COMPETITOR = {
        ...MOCK_COMPETITOR,
        display_name: "Updated Name",
      };

      vi.mocked(api.patch).mockResolvedValue({ data: UPDATED_COMPETITOR });

      const result = await competitorService.update(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
        UPDATE_DATA,
      );

      expect(result.display_name).toBe("Updated Name");
      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors/${COMPETITOR_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update competitor description", async () => {
      const UPDATE_DATA = { description: "Updated description" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_COMPETITOR });

      await competitorService.update(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors/${COMPETITOR_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update multiple fields at once", async () => {
      const UPDATE_DATA = {
        display_name: "New Name",
        description: "New description",
        references: ["https://new-ref.com"],
      };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_COMPETITOR });

      await competitorService.update(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors/${COMPETITOR_NODE_ID}`,
        UPDATE_DATA,
      );
    });
  });

  describe("delete", () => {
    it("should delete a competitor by node_id", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      await competitorService.delete(ACCOUNT_ID, COMPETITOR_NODE_ID);

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitors/${COMPETITOR_NODE_ID}`,
      );
    });

    it("should not return data on successful deletion", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      const result = await competitorService.delete(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toBeUndefined();
    });
  });
});

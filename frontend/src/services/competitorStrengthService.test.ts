import { describe, it, expect, vi, beforeEach } from "vitest";
import { competitorStrengthService } from "./competitorStrengthService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("CompetitorStrengthService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;
  const COMPETITOR_NODE_ID = "competitor_node_123";
  const STRENGTH_NODE_ID = "strength_node_789";

  const MOCK_STRENGTH = {
    node_id: STRENGTH_NODE_ID,
    account_id: ACCOUNT_ID,
    display_name: "Strong Brand",
    description: "Well-established brand recognition",
    references: ["https://example.com/brand-report"],
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
    it("should fetch strengths with default pagination", async () => {
      const MOCK_RESPONSE = {
        strengths: [MOCK_STRENGTH],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorStrengthService.list(ACCOUNT_ID);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths`,
        { params: { competitor_node_id: undefined, skip: 0, limit: 1000 } },
      );
    });

    it("should fetch strengths filtered by competitor", async () => {
      const MOCK_RESPONSE = {
        strengths: [MOCK_STRENGTH],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorStrengthService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 0,
            limit: 1000,
          },
        },
      );
    });

    it("should return empty list when no strengths exist", async () => {
      const EMPTY_RESPONSE = {
        strengths: [],
        total_count: 0,
      };

      vi.mocked(api.get).mockResolvedValue({ data: EMPTY_RESPONSE });

      const result = await competitorStrengthService.list(ACCOUNT_ID);

      expect(result.strengths).toEqual([]);
      expect(result.total_count).toBe(0);
    });
  });

  describe("create", () => {
    it("should create a new strength linked to competitor", async () => {
      const CREATE_DATA = {
        display_name: "Market Leadership",
        description: "Leader in the market segment",
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_STRENGTH });

      const result = await competitorStrengthService.create(
        ACCOUNT_ID,
        CREATE_DATA,
      );

      expect(result).toEqual(MOCK_STRENGTH);
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths`,
        CREATE_DATA,
      );
    });

    it("should create a strength with references", async () => {
      const CREATE_DATA = {
        display_name: "Innovation",
        description: "Strong R&D capabilities",
        references: ["https://example.com/innovation-report"],
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_STRENGTH });

      await competitorStrengthService.create(ACCOUNT_ID, CREATE_DATA);

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths`,
        CREATE_DATA,
      );
    });
  });

  describe("update", () => {
    it("should update strength display_name", async () => {
      const UPDATE_DATA = { display_name: "Updated Strength" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_STRENGTH });

      await competitorStrengthService.update(
        ACCOUNT_ID,
        STRENGTH_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths/${STRENGTH_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update multiple fields", async () => {
      const UPDATE_DATA = {
        display_name: "New Name",
        description: "New description",
        references: ["https://new.com"],
      };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_STRENGTH });

      await competitorStrengthService.update(
        ACCOUNT_ID,
        STRENGTH_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths/${STRENGTH_NODE_ID}`,
        UPDATE_DATA,
      );
    });
  });

  describe("delete", () => {
    it("should delete a strength by node_id", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      await competitorStrengthService.delete(ACCOUNT_ID, STRENGTH_NODE_ID);

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-strengths/${STRENGTH_NODE_ID}`,
      );
    });
  });
});

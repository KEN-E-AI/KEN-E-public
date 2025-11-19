import { describe, it, expect, vi, beforeEach } from "vitest";
import { competitorTacticService } from "./competitorTacticService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("CompetitorTacticService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;
  const COMPETITOR_NODE_ID = "competitor_node_123";
  const TACTIC_NODE_ID = "tactic_node_456";

  const MOCK_TACTIC = {
    node_id: TACTIC_NODE_ID,
    account_id: ACCOUNT_ID,
    display_name: "Social Media Campaign",
    description: "Active social media marketing strategy",
    references: ["https://example.com/campaign"],
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
    it("should fetch tactics with default pagination", async () => {
      const MOCK_RESPONSE = {
        tactics: [MOCK_TACTIC],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorTacticService.list(ACCOUNT_ID);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics`,
        { params: { competitor_node_id: undefined, skip: 0, limit: 1000 } },
      );
    });

    it("should fetch tactics filtered by competitor", async () => {
      const MOCK_RESPONSE = {
        tactics: [MOCK_TACTIC],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorTacticService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 0,
            limit: 1000,
          },
        },
      );
    });

    it("should fetch tactics with custom pagination", async () => {
      const MOCK_RESPONSE = {
        tactics: [MOCK_TACTIC],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorTacticService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
        20,
        100,
      );

      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 20,
            limit: 100,
          },
        },
      );
    });

    it("should return empty list when no tactics exist", async () => {
      const EMPTY_RESPONSE = {
        tactics: [],
        total_count: 0,
      };

      vi.mocked(api.get).mockResolvedValue({ data: EMPTY_RESPONSE });

      const result = await competitorTacticService.list(ACCOUNT_ID);

      expect(result.tactics).toEqual([]);
      expect(result.total_count).toBe(0);
    });
  });

  describe("create", () => {
    it("should create a new tactic linked to competitor", async () => {
      const CREATE_DATA = {
        display_name: "New Tactic",
        description: "A new competitive tactic",
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_TACTIC });

      const result = await competitorTacticService.create(
        ACCOUNT_ID,
        CREATE_DATA,
      );

      expect(result).toEqual(MOCK_TACTIC);
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics`,
        CREATE_DATA,
      );
    });

    it("should create a tactic with references", async () => {
      const CREATE_DATA = {
        display_name: "Tactic with Refs",
        description: "Tactic with references",
        references: ["https://example.com/ref1"],
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_TACTIC });

      await competitorTacticService.create(ACCOUNT_ID, CREATE_DATA);

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics`,
        CREATE_DATA,
      );
    });
  });

  describe("update", () => {
    it("should update tactic display_name", async () => {
      const UPDATE_DATA = { display_name: "Updated Tactic Name" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_TACTIC });

      const result = await competitorTacticService.update(
        ACCOUNT_ID,
        TACTIC_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics/${TACTIC_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update multiple fields", async () => {
      const UPDATE_DATA = {
        display_name: "New Name",
        description: "New description",
        references: ["https://new.com"],
      };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_TACTIC });

      await competitorTacticService.update(
        ACCOUNT_ID,
        TACTIC_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics/${TACTIC_NODE_ID}`,
        UPDATE_DATA,
      );
    });
  });

  describe("delete", () => {
    it("should delete a tactic by node_id", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      await competitorTacticService.delete(ACCOUNT_ID, TACTIC_NODE_ID);

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-tactics/${TACTIC_NODE_ID}`,
      );
    });
  });
});

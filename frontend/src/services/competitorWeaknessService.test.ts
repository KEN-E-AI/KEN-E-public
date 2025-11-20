import { describe, it, expect, vi, beforeEach } from "vitest";
import { competitorWeaknessService } from "./competitorWeaknessService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("CompetitorWeaknessService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;
  const COMPETITOR_NODE_ID = "competitor_node_123";
  const WEAKNESS_NODE_ID = "weakness_node_101";

  const MOCK_WEAKNESS = {
    node_id: WEAKNESS_NODE_ID,
    account_id: ACCOUNT_ID,
    display_name: "Limited Distribution",
    description: "Weak distribution network",
    references: ["https://example.com/analysis"],
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
    it("should fetch weaknesses with default pagination", async () => {
      const MOCK_RESPONSE = {
        weaknesses: [MOCK_WEAKNESS],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorWeaknessService.list(ACCOUNT_ID);

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses`,
        { params: { competitor_node_id: undefined, skip: 0, limit: 1000 } },
      );
    });

    it("should fetch weaknesses filtered by competitor", async () => {
      const MOCK_RESPONSE = {
        weaknesses: [MOCK_WEAKNESS],
        total_count: 1,
      };

      vi.mocked(api.get).mockResolvedValue({ data: MOCK_RESPONSE });

      const result = await competitorWeaknessService.list(
        ACCOUNT_ID,
        COMPETITOR_NODE_ID,
      );

      expect(result).toEqual(MOCK_RESPONSE);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses`,
        {
          params: {
            competitor_node_id: COMPETITOR_NODE_ID,
            skip: 0,
            limit: 1000,
          },
        },
      );
    });

    it("should return empty list when no weaknesses exist", async () => {
      const EMPTY_RESPONSE = {
        weaknesses: [],
        total_count: 0,
      };

      vi.mocked(api.get).mockResolvedValue({ data: EMPTY_RESPONSE });

      const result = await competitorWeaknessService.list(ACCOUNT_ID);

      expect(result.weaknesses).toEqual([]);
      expect(result.total_count).toBe(0);
    });
  });

  describe("create", () => {
    it("should create a new weakness linked to competitor", async () => {
      const CREATE_DATA = {
        display_name: "Outdated Technology",
        description: "Using legacy systems",
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_WEAKNESS });

      const result = await competitorWeaknessService.create(
        ACCOUNT_ID,
        CREATE_DATA,
      );

      expect(result).toEqual(MOCK_WEAKNESS);
      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses`,
        CREATE_DATA,
      );
    });

    it("should create a weakness with references", async () => {
      const CREATE_DATA = {
        display_name: "Poor Customer Service",
        description: "Low customer satisfaction scores",
        references: ["https://example.com/satisfaction-survey"],
        competitor_node_id: COMPETITOR_NODE_ID,
      };

      vi.mocked(api.post).mockResolvedValue({ data: MOCK_WEAKNESS });

      await competitorWeaknessService.create(ACCOUNT_ID, CREATE_DATA);

      expect(api.post).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses`,
        CREATE_DATA,
      );
    });
  });

  describe("update", () => {
    it("should update weakness display_name", async () => {
      const UPDATE_DATA = { display_name: "Updated Weakness" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_WEAKNESS });

      await competitorWeaknessService.update(
        ACCOUNT_ID,
        WEAKNESS_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses/${WEAKNESS_NODE_ID}`,
        UPDATE_DATA,
      );
    });

    it("should update multiple fields", async () => {
      const UPDATE_DATA = {
        display_name: "New Name",
        description: "New description",
        references: ["https://new.com"],
      };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_WEAKNESS });

      await competitorWeaknessService.update(
        ACCOUNT_ID,
        WEAKNESS_NODE_ID,
        UPDATE_DATA,
      );

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses/${WEAKNESS_NODE_ID}`,
        UPDATE_DATA,
      );
    });
  });

  describe("delete", () => {
    it("should delete a weakness by node_id", async () => {
      vi.mocked(api.delete).mockResolvedValue({ data: { success: true } });

      await competitorWeaknessService.delete(ACCOUNT_ID, WEAKNESS_NODE_ID);

      expect(api.delete).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitor-weaknesses/${WEAKNESS_NODE_ID}`,
      );
    });
  });
});

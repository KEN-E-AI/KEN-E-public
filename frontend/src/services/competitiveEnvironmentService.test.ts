import { describe, it, expect, vi, beforeEach } from "vitest";
import { competitiveEnvironmentService } from "./competitiveEnvironmentService";
import type { AccountId } from "@/lib/branded-types";
import api from "@/lib/api";

vi.mock("@/lib/api");

describe("CompetitiveEnvironmentService", () => {
  const ACCOUNT_ID = "acc_test123" as AccountId;

  const MOCK_ENVIRONMENT = {
    node_id: "compenv_node_123",
    account_id: ACCOUNT_ID,
    description: "Highly competitive market with 5 major players",
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
    created_by: "user_123",
    last_modified_by: "user_123",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("get", () => {
    it("should fetch the competitive environment hub node", async () => {
      vi.mocked(api.get).mockResolvedValue({ data: MOCK_ENVIRONMENT });

      const result = await competitiveEnvironmentService.get(ACCOUNT_ID);

      expect(result).toEqual(MOCK_ENVIRONMENT);
      expect(api.get).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitive-environment`,
      );
    });

    it("should include all environment fields", async () => {
      vi.mocked(api.get).mockResolvedValue({ data: MOCK_ENVIRONMENT });

      const result = await competitiveEnvironmentService.get(ACCOUNT_ID);

      expect(result).toHaveProperty("node_id");
      expect(result).toHaveProperty("account_id");
      expect(result).toHaveProperty("description");
      expect(result).toHaveProperty("created_time");
      expect(result).toHaveProperty("last_modified");
    });
  });

  describe("update", () => {
    it("should update competitive environment description", async () => {
      const UPDATE_DATA = {
        description: "Market dynamics have shifted with new entrants",
      };
      const UPDATED_ENVIRONMENT = {
        ...MOCK_ENVIRONMENT,
        description: UPDATE_DATA.description,
      };

      vi.mocked(api.patch).mockResolvedValue({ data: UPDATED_ENVIRONMENT });

      const result = await competitiveEnvironmentService.update(
        ACCOUNT_ID,
        UPDATE_DATA,
      );

      expect(result.description).toBe(UPDATE_DATA.description);
      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitive-environment`,
        UPDATE_DATA,
      );
    });

    it("should handle empty description update", async () => {
      const UPDATE_DATA = { description: "" };

      vi.mocked(api.patch).mockResolvedValue({ data: MOCK_ENVIRONMENT });

      await competitiveEnvironmentService.update(ACCOUNT_ID, UPDATE_DATA);

      expect(api.patch).toHaveBeenCalledWith(
        `/api/v1/knowledge-graph/${ACCOUNT_ID}/competitive-environment`,
        UPDATE_DATA,
      );
    });
  });
});

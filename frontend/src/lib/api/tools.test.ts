import { describe, it, expect, vi, beforeEach } from "vitest";
import { getAccountTools } from "./tools";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockApi = api as { get: ReturnType<typeof vi.fn> };

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── getAccountTools ─────────────────────────────────────────────────────────

describe("getAccountTools", () => {
  it("calls GET /api/v1/accounts/{accountId}/tools and returns the response data", async () => {
    const fixture = {
      tools: [
        {
          tool_id: "function.create_visualization",
          name: "create_visualization",
          description: "Render a chart.",
          category: "visualization",
          source: "global_default",
          mcp_server: null,
          integration_platform: null,
        },
        {
          tool_id: "google_analytics_mcp.list_ga_accounts",
          name: "list_ga_accounts",
          description: "List GA accounts.",
          category: "analytics",
          source: "integration",
          mcp_server: "google_analytics_mcp",
          integration_platform: "google_analytics",
        },
      ],
    };
    mockApi.get.mockResolvedValueOnce({ data: fixture });

    const result = await getAccountTools("acc_test");

    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/accounts/acc_test/tools");
    expect(result).toEqual(fixture);
  });

  it("URL-encodes the accountId", async () => {
    mockApi.get.mockResolvedValueOnce({ data: { tools: [] } });
    await getAccountTools("acc test/with weird chars");
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/accounts/acc%20test%2Fwith%20weird%20chars/tools",
    );
  });
});

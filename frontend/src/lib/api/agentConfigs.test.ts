import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  isAgentConfigId,
  toAgentConfigId,
  tryAgentConfigId,
  listAgentConfigs,
  getAgentConfig,
  createAgentConfig,
  upsertAgentConfigOverlay,
  deleteAgentConfig,
  SUPPORTED_MODELS,
} from "./agentConfigs";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Branded type helpers ─────────────────────────────────────────────────────

describe("isAgentConfigId", () => {
  it("returns true for non-empty strings", () => {
    expect(isAgentConfigId("google_analytics_specialist")).toBe(true);
    expect(isAgentConfigId("custom_abc123")).toBe(true);
  });

  it("returns false for empty string", () => {
    expect(isAgentConfigId("")).toBe(false);
  });
});

describe("toAgentConfigId", () => {
  it("returns a branded AgentConfigId for valid strings", () => {
    const id = toAgentConfigId("google_analytics_specialist");
    expect(id).toBe("google_analytics_specialist");
  });

  it("throws for empty string", () => {
    expect(() => toAgentConfigId("")).toThrow("Invalid AgentConfigId");
  });
});

describe("tryAgentConfigId", () => {
  it("returns the id for non-empty strings", () => {
    expect(tryAgentConfigId("custom_abc")).toBe("custom_abc");
  });

  it("returns undefined for empty string", () => {
    expect(tryAgentConfigId("")).toBeUndefined();
  });
});

// ─── SUPPORTED_MODELS ─────────────────────────────────────────────────────────

describe("SUPPORTED_MODELS", () => {
  it("includes key Gemini models", () => {
    expect(SUPPORTED_MODELS).toContain("gemini-2.5-flash");
    expect(SUPPORTED_MODELS).toContain("gemini-2.5-pro");
  });

  it("includes key OpenAI models", () => {
    expect(SUPPORTED_MODELS).toContain("gpt-4o");
  });
});

// ─── API function — URL construction ─────────────────────────────────────────

describe("listAgentConfigs", () => {
  it("calls GET /api/v1/accounts/{accountId}/agent-configs/ without params by default", async () => {
    mockApi.get.mockResolvedValueOnce({ data: [] });
    await listAgentConfigs("acc_test");
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/",
      { params: {} },
    );
  });

  it("adds visible_in_frontend=true query param when option is set", async () => {
    mockApi.get.mockResolvedValueOnce({ data: [] });
    await listAgentConfigs("acc_test", { visibleInFrontend: true });
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/",
      { params: { visible_in_frontend: "true" } },
    );
  });

  it("returns the response data array", async () => {
    const fixture = [{ config_id: "ga", customization_status: "default" }];
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listAgentConfigs("acc_test");
    expect(result).toEqual(fixture);
  });
});

describe("getAgentConfig", () => {
  it("calls GET /api/v1/accounts/{accountId}/agent-configs/{configId}", async () => {
    const fixture = { config_id: "ga", customization_status: "default" };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await getAgentConfig("acc_test", "ga");
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/ga",
    );
    expect(result).toEqual(fixture);
  });
});

describe("createAgentConfig", () => {
  it("calls POST /api/v1/accounts/{accountId}/agent-configs/", async () => {
    const body = {
      title: "My Agent",
      name: "My Agent",
      instruction: "Be helpful.",
      model: "gemini-2.5-flash",
    };
    const fixture = {
      config_id: "custom_abc",
      customization_status: "custom_agent",
    };
    mockApi.post.mockResolvedValueOnce({ data: fixture });
    const result = await createAgentConfig("acc_test", body);
    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/",
      body,
    );
    expect(result).toEqual(fixture);
  });
});

describe("upsertAgentConfigOverlay", () => {
  it("calls PUT /api/v1/accounts/{accountId}/agent-configs/{configId}", async () => {
    const body = { temperature: 0.5 };
    const fixture = { config_id: "ga", customization_status: "customized" };
    mockApi.put.mockResolvedValueOnce({ data: fixture });
    const result = await upsertAgentConfigOverlay("acc_test", "ga", body);
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/ga",
      body,
    );
    expect(result).toEqual(fixture);
  });
});

describe("deleteAgentConfig", () => {
  it("calls DELETE /api/v1/accounts/{accountId}/agent-configs/{configId}", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: undefined });
    await deleteAgentConfig("acc_test", "ga");
    expect(mockApi.delete).toHaveBeenCalledWith(
      "/api/v1/accounts/acc_test/agent-configs/ga",
    );
  });
});

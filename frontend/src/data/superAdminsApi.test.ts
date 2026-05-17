import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listSuperAdmins,
  grantSuperAdmin,
  revokeSuperAdmin,
} from "./superAdminsApi";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockGet = api.get as ReturnType<typeof vi.fn>;
const mockPost = api.post as ReturnType<typeof vi.fn>;
const mockDelete = api.delete as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("listSuperAdmins", () => {
  it("calls GET /api/v1/admin/super-admins and returns data", async () => {
    const fixture = {
      super_admins: [{ uid: "u1", email: "a@b.com" }],
      total: 1,
    };
    mockGet.mockResolvedValueOnce({ data: fixture });

    const result = await listSuperAdmins();

    expect(mockGet).toHaveBeenCalledWith("/api/v1/admin/super-admins");
    expect(result).toEqual(fixture);
  });
});

describe("grantSuperAdmin", () => {
  it("calls POST with { uid } only when given uid", async () => {
    const fixture = { uid: "u1", email: "a@b.com" };
    mockPost.mockResolvedValueOnce({ data: fixture });

    const result = await grantSuperAdmin({ uid: "u1" });

    expect(mockPost).toHaveBeenCalledWith("/api/v1/admin/super-admins", {
      uid: "u1",
    });
    expect(result).toEqual(fixture);
  });

  it("calls POST with { email } only when given email", async () => {
    const fixture = { uid: "u2", email: "b@c.com" };
    mockPost.mockResolvedValueOnce({ data: fixture });

    const result = await grantSuperAdmin({ email: "b@c.com" });

    expect(mockPost).toHaveBeenCalledWith("/api/v1/admin/super-admins", {
      email: "b@c.com",
    });
    expect(result).toEqual(fixture);
  });
});

describe("revokeSuperAdmin", () => {
  it("calls DELETE at the correct path", async () => {
    const fixture = { success: true, message: "Revoked", data: { uid: "u1" } };
    mockDelete.mockResolvedValueOnce({ data: fixture });

    const result = await revokeSuperAdmin("u1");

    expect(mockDelete).toHaveBeenCalledWith("/api/v1/admin/super-admins/u1");
    expect(result).toEqual(fixture);
  });
});

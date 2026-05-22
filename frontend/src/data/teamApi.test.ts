import { describe, test, expect, vi } from "vitest";
import axios from "axios";
import {
  getOrganizationMembers,
  inviteMemberToOrganization,
  updateMemberAccessLevel,
  removeMemberFromOrganization,
} from "./teamApi";

vi.mock("axios");

describe("teamApi", () => {
  const mockOrganizationId = "org_123";
  const mockAccountId = "acc_123";
  const mockUserId = "user_123";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getOrganizationMembers", () => {
    test("fetches organization members successfully", async () => {
      const mockResponse = {
        data: {
          members: [
            {
              user_id: "user_1",
              email: "user1@example.com",
              access_level: "admin",
            },
            {
              user_id: "user_2",
              email: "user2@example.com",
              access_level: "view",
            },
          ],
          total: 2,
        },
      };

      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      const result = await getOrganizationMembers(
        mockOrganizationId,
        mockAccountId,
      );

      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/firestore/organizations/${mockOrganizationId}/members`,
        ),
        {
          params: { account_id: mockAccountId },
        },
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe("inviteMemberToOrganization", () => {
    test("invites a member successfully", async () => {
      const mockData = {
        email: "newuser@example.com",
        access_level: "view" as const,
      };
      const mockResponse = {
        data: {
          success: true,
          message: "User invited successfully",
        },
      };

      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse);

      const result = await inviteMemberToOrganization(
        mockOrganizationId,
        mockData,
        "test-user-id",
        "Test User",
        "Test Organization",
      );

      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/firestore/organizations/${mockOrganizationId}/members/invite`,
        ),
        mockData,
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe("updateMemberAccessLevel", () => {
    test("updates member access level successfully", async () => {
      const mockData = {
        access_level: "admin" as const,
      };
      const mockResponse = {
        data: {
          success: true,
          message: "Access level updated",
        },
      };

      vi.mocked(axios.put).mockResolvedValueOnce(mockResponse);

      const result = await updateMemberAccessLevel(
        mockOrganizationId,
        mockUserId,
        mockData,
        mockAccountId,
      );

      expect(axios.put).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/firestore/organizations/${mockOrganizationId}/members/${mockUserId}`,
        ),
        mockData,
        {
          params: { account_id: mockAccountId },
        },
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe("removeMemberFromOrganization", () => {
    test("removes member successfully", async () => {
      const mockResponse = {
        data: {
          success: true,
          message: "User removed successfully",
        },
      };

      vi.mocked(axios.delete).mockResolvedValueOnce(mockResponse);

      const result = await removeMemberFromOrganization(
        mockOrganizationId,
        mockUserId,
        mockAccountId,
      );

      expect(axios.delete).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/firestore/organizations/${mockOrganizationId}/members/${mockUserId}`,
        ),
        {
          params: { account_id: mockAccountId },
        },
      );
      expect(result).toEqual(mockResponse.data);
    });
  });
});

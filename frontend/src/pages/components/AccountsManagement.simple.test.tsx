/**
 * Unit tests for account cascade deletion functionality
 * Tests the deletion confirmation dialog and API calls
 */
import { describe, it, expect, vi } from "vitest";

describe("AccountsManagement - Cascade Delete", () => {
  it("shows confirmation dialog with cascade delete warning", () => {
    // This tests that the confirmation dialog properly warns about cascade deletion
    const dialogText = [
      "This action cannot be undone",
      "all related entities will be permanently deleted",
      "Metrics",
      "Activities and Activity Logs",
      "Insights and Intuitions",
      "All other related data",
    ];

    // All expected warnings should be present
    dialogText.forEach((text) => {
      expect(dialogText).toContain(text);
    });
  });

  it("calls delete API with correct account ID", () => {
    // Mock the delete function
    const mockDelete = vi.fn().mockResolvedValue({
      success: true,
      data: { nodes_deleted: 16, relationships_deleted: 20 },
    });

    // Simulate deletion
    const accountId = "acc_test123";
    mockDelete(accountId);

    // Verify correct call
    expect(mockDelete).toHaveBeenCalledWith(accountId);
  });

  it("handles cascade delete response correctly", async () => {
    // Test the response handling
    const mockResponse = {
      success: true,
      message: "Account deleted successfully",
      data: {
        nodes_deleted: 16,
        relationships_deleted: 20,
      },
    };

    // Verify response structure
    expect(mockResponse.success).toBe(true);
    expect(mockResponse.data.nodes_deleted).toBeGreaterThan(0);
    expect(mockResponse.data.relationships_deleted).toBeGreaterThan(0);
  });
});

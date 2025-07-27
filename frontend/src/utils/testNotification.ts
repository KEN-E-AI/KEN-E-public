/**
 * Test utility for sending notifications
 * This can be used from the browser console for testing
 */

import { notificationApi } from "@/api/notifications";
import type { NotificationCategory } from "@/types/notification.types";

export async function sendTestNotification(
  accountId: string,
  category: NotificationCategory = "New Features",
  description?: string,
) {
  const testDescription =
    description || `Test notification sent at ${new Date().toLocaleString()}`;

  try {
    console.log(
      `[TestNotification] Sending test notification to account: ${accountId}`,
    );

    const result = await notificationApi.createNotification({
      account_id: accountId,
      category: category,
      description: testDescription,
      data: {
        test: true,
        timestamp: new Date().toISOString(),
        source: "manual_test",
      },
    });

    console.log("[TestNotification] Notification sent successfully:", result);
    return result;
  } catch (error) {
    console.error("[TestNotification] Error sending notification:", error);
    throw error;
  }
}

// Make it available on window object for easy console access
if (typeof window !== "undefined") {
  (window as any).sendTestNotification = sendTestNotification;
}

/**
 * NotificationHandler - Placeholder component for handling notification clicks
 */

import React from "react";
import { Button } from "@/components/ui/button";
import type { NotificationWithStatus } from "@/types/notification.types";

interface NotificationHandlerProps {
  notification: NotificationWithStatus | null;
  onClose: () => void;
}

export const NotificationHandler: React.FC<NotificationHandlerProps> = ({
  notification,
  onClose,
}) => {
  if (!notification) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-[var(--color-bg-elevated)] rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b">
          <h2 className="text-xl font-semibold">Notification Details</h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
            {notification.category}
          </p>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                Description
              </h3>
              <p className="text-[var(--color-text-secondary)]">
                {notification.description}
              </p>
            </div>

            {notification.data && Object.keys(notification.data).length > 0 && (
              <div>
                <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                  Additional Information
                </h3>
                <div className="bg-[var(--color-bg-secondary)] rounded-md p-4">
                  <pre className="text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap">
                    {JSON.stringify(notification.data, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            <div className="text-sm text-[var(--color-text-tertiary)]">
              <p>
                Created: {new Date(notification.created_at).toLocaleString()}
              </p>
              {notification.read_at && (
                <p>Read: {new Date(notification.read_at).toLocaleString()}</p>
              )}
            </div>
          </div>

          {/* Placeholder message */}
          <div className="mt-6 p-4 bg-blue-50 rounded-md">
            <p className="text-blue-700 text-sm">
              <strong>Note:</strong> This is a placeholder for notification
              actions. In a production environment, this would trigger specific
              actions based on the notification type and data.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

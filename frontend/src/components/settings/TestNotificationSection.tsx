import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Send, AlertCircle } from "lucide-react";
import { notificationApi } from "@/api/notifications";
import type { NotificationCategory } from "@/types/notification.types";

const NOTIFICATION_CATEGORIES: NotificationCategory[] = [
  "Data Quality Alert",
  "News & Press",
  "Industry News",
  "Competitor Activities",
  "Scheduled Report Status",
  "KPI Performance",
  "New Features",
];

export const TestNotificationSection = () => {
  const { toast } = useToast();
  const [accountId, setAccountId] = useState(
    "acc_4eac7dbf731b4c39bd983014efd6c7c8",
  );
  const [category, setCategory] =
    useState<NotificationCategory>("New Features");
  const [description, setDescription] = useState("");
  const [isSending, setIsSending] = useState(false);

  const handleSendNotification = async () => {
    if (!accountId) {
      toast({
        title: "Error",
        description: "Please enter an account ID",
        variant: "destructive",
      });
      return;
    }

    setIsSending(true);
    try {
      const testDescription =
        description ||
        `Test notification sent at ${new Date().toLocaleString()}`;

      await notificationApi.createNotification({
        account_id: accountId,
        category: category,
        description: testDescription,
        data: {
          test: true,
          timestamp: new Date().toISOString(),
          source: "manual_test_ui",
        },
      });

      toast({
        title: "Success",
        description: "Test notification sent successfully",
      });

      // Clear description after sending
      setDescription("");
    } catch (error: any) {
      console.error("[TestNotification] Error:", error);
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to send notification",
        variant: "destructive",
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="h-5 w-5" />
          Test Notifications (Dev Only)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-2">
          <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div className="text-sm text-yellow-800">
            <p className="font-medium">Development Tool</p>
            <p>
              This section is only visible in development mode for testing
              notifications.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="account-id">Account ID</Label>
          <Input
            id="account-id"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            placeholder="Enter account ID"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="category">Category</Label>
          <Select
            value={category}
            onValueChange={(value) =>
              setCategory(value as NotificationCategory)
            }
          >
            <SelectTrigger id="category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {NOTIFICATION_CATEGORIES.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description (Optional)</Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter notification description"
          />
          <p className="text-xs text-[var(--color-text-tertiary)]">
            If left empty, a default test message will be used
          </p>
        </div>

        <Button
          onClick={handleSendNotification}
          disabled={isSending || !accountId}
          className="w-full"
        >
          {isSending ? (
            <>Sending...</>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              Send Test Notification
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

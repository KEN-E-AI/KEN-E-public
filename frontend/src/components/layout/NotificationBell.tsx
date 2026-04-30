import { useState } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NotificationSidebar } from "@/components/notifications/NotificationSidebar";
import { useAuth } from "@/contexts/AuthContext";

export function NotificationBell() {
  const { notifications, selectedOrgAccount } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  const unreadCount = notifications.filter((n) => n.status === "unread").length;

  const handleClick = () => {
    if (!selectedOrgAccount) return;
    setIsOpen((prev) => !prev);
  };

  return (
    <>
      <div className="relative">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Notifications"
          onClick={handleClick}
        >
          <Bell />
        </Button>
        {unreadCount > 0 && (
          <span
            className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-[#F97066] text-[10px] font-bold text-white"
            style={{ boxShadow: "0 0 6px rgba(249, 112, 102, 0.5)" }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </div>
      {selectedOrgAccount && (
        <NotificationSidebar
          accountId={selectedOrgAccount.accountId}
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
        />
      )}
    </>
  );
}

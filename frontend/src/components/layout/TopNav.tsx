import { AccountSwitcher } from "./AccountSwitcher";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";

type TopNavProps = {
  compact?: boolean;
};

export function TopNav({ compact = false }: TopNavProps) {
  return (
    <div className="flex items-center h-16 px-6">
      <div className="flex items-center gap-2 shrink-0">
        <AccountSwitcher compact={compact} />
      </div>
      <div className="h-8 w-px bg-[var(--color-border-default)] mx-5 shrink-0" />
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        <NotificationBell />
        <ProfileMenu compact={compact} />
      </div>
    </div>
  );
}

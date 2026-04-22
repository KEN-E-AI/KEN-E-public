import { useState } from 'react';
import { Info, Unplug } from 'lucide-react';
import { Integration, mockAccountUsers } from '../data/mockData';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Separator } from './ui/separator';
import { IntegrationIcon } from './IntegrationIcon';

interface ConfigureIntegrationPanelProps {
  integration: Integration;
  onClose: () => void;
}

type AccessLevel = 'edit' | 'view' | 'none';

const statusConfig = {
  connected: {
    label: 'Connected',
    dotClass: 'bg-[var(--color-success)]',
    textClass: 'text-[var(--color-success-text)]',
    bgClass: 'bg-[var(--color-success-bg)]',
  },
  disconnected: {
    label: 'Not Connected',
    dotClass: 'bg-[var(--color-error)]',
    textClass: 'text-[var(--color-error-text)]',
    bgClass: 'bg-[var(--color-error-bg)]',
  },
  error: {
    label: 'Issue',
    dotClass: 'bg-[var(--color-warning)]',
    textClass: 'text-[var(--color-warning-text)]',
    bgClass: 'bg-[var(--color-warning-bg)]',
  },
};

export function ConfigureIntegrationPanel({ integration, onClose }: ConfigureIntegrationPanelProps) {
  const [permissions, setPermissions] = useState<Record<string, AccessLevel>>(
    Object.fromEntries(mockAccountUsers.map(u => [u.id, 'edit' as AccessLevel]))
  );

  const status = statusConfig[integration.status];

  const handlePermissionChange = (userId: string, value: AccessLevel) => {
    setPermissions(prev => ({ ...prev, [userId]: value }));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4 pr-12">
        <div>
          <div className="flex items-center gap-3 mb-3">
            <IntegrationIcon name={integration.name} fallbackEmoji={integration.icon} />
            <h3 className="truncate">Configure {integration.name} Integration</h3>
          </div>
          <div className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full ${status.bgClass}`}>
            <span className={`size-2 rounded-full ${status.dotClass}`} />
            <span className={`text-xs ${status.textClass}`} style={{ fontWeight: 600 }}>
              {status.label}
            </span>
          </div>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
        {/* Connection action */}
        {integration.status === 'disconnected' && (
          <div className="p-4 rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border-default)] text-center">
            <p className="text-sm text-[var(--color-text-secondary)] mb-3">
              This integration is not yet connected.
            </p>
            <Button size="sm">
              Connect {integration.name}
            </Button>
          </div>
        )}

        {integration.status === 'error' && (
          <div className="p-4 rounded-[var(--radius-md)] bg-[var(--color-warning-bg)] border border-[var(--color-warning)]">
            <p className="text-sm text-[var(--color-warning-text)] mb-3">
              There was an issue with this integration. Please try reconnecting.
            </p>
            <Button variant="destructive" size="sm">
              Reconnect {integration.name}
            </Button>
          </div>
        )}

        {integration.status === 'connected' && (
          <div className="flex items-center justify-between p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)]">
            <p className="text-sm text-[var(--color-text-secondary)]">
              This integration is active.
            </p>
            <Button variant="ghost" size="sm" className="text-[var(--color-error)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)]">
              <Unplug className="size-3.5 mr-1.5" />
              Disconnect
            </Button>
          </div>
        )}

        {/* Credentials notice */}
        <div className="flex gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-info-bg)] border border-[var(--color-info)]">
          <Info className="size-4 text-[var(--color-info)] shrink-0 mt-0.5" />
          <p className="text-xs text-[var(--color-info-text)]">
            All users in this account will share the same credentials when accessing {integration.name}.
          </p>
        </div>

        <Separator />

        {/* Permissions section */}
        <div>
          <h4 className="mb-2">Permissions</h4>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Enabling this integration makes the <span style={{ fontWeight: 600 }}>{integration.name} Specialist</span> agent
            available to all users in the account unless modified below.
          </p>

          <div className="space-y-2">
            {mockAccountUsers.map(user => (
              <div
                key={user.id}
                className="flex items-center justify-between gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--color-surface-muted)]"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="size-8 rounded-full bg-[var(--color-violet-200)] flex items-center justify-center text-xs text-[var(--color-violet-500)] shrink-0" style={{ fontWeight: 600 }}>
                    {user.avatarInitials}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm truncate" style={{ fontWeight: 500 }}>{user.name}</p>
                    <p className="text-xs text-[var(--color-text-tertiary)] truncate">{user.email}</p>
                  </div>
                </div>
                <Select
                  value={permissions[user.id]}
                  onValueChange={(val: string) => handlePermissionChange(user.id, val as AccessLevel)}
                >
                  <SelectTrigger className="w-[100px] h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="edit">Edit</SelectItem>
                    <SelectItem value="view">View</SelectItem>
                    <SelectItem value="none">None</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-2 p-4 border-t border-[var(--color-border-default)]">
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" onClick={onClose}>
          Save Changes
        </Button>
      </div>
    </div>
  );
}
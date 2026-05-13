import { useState } from 'react';
import { ChevronsUpDown, Check, Building2, Settings, Plus } from 'lucide-react';
import { Link } from 'react-router';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { cn } from './ui/utils';
import {
  mockOrganizations,
  mockAccounts,
  type Organization,
} from '../data/mockData';

function OrgAvatar({ org, size = 'sm' }: { org: Organization; size?: 'sm' | 'md' }) {
  const dims = size === 'sm' ? 'size-6' : 'size-8';
  const text = size === 'sm' ? 'text-[0.625rem]' : 'text-xs';
  return (
    <div
      className={cn(
        dims,
        'rounded-[var(--radius-sm)] flex items-center justify-center shrink-0'
      )}
      style={{ backgroundColor: org.avatarColor }}
    >
      <span className={cn(text, 'text-white font-extrabold')}>
        {org.name.charAt(0)}
      </span>
    </div>
  );
}

interface AccountSwitcherProps {
  compact?: boolean;
}

export function AccountSwitcher({ compact = false }: AccountSwitcherProps) {
  const [activeAccountId, setActiveAccountId] = useState('acct-1');

  const activeAccount = mockAccounts.find((a) => a.id === activeAccountId)!;
  const activeOrg = mockOrganizations.find(
    (o) => o.id === activeAccount.organizationId
  )!;

  // Group accounts by organization
  const accountsByOrg = mockOrganizations.map((org) => ({
    org,
    accounts: mockAccounts.filter((a) => a.organizationId === org.id),
  }));

  const handleAccountSwitch = (accountId: string) => {
    setActiveAccountId(accountId);
    console.log('Switched to account:', accountId);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            'flex items-center gap-1.5 rounded-[var(--radius-md)] transition-all outline-none',
            'hover:bg-[var(--color-accent)] active:scale-[0.98]',
            compact ? 'px-2 py-1.5' : 'px-2.5 py-1.5'
          )}
          style={{
            transitionTimingFunction: 'var(--ease-bounce)',
            transitionDuration: 'var(--duration-fast)',
          }}
        >
          <span
            className="text-[var(--color-text-tertiary)] truncate max-w-[6.25rem]"
            style={{ fontSize: compact ? '0.75rem' : '0.8125rem' }}
          >
            {activeOrg.name}
          </span>
          <span className="text-[var(--color-text-disabled)]">/</span>
          <span
            className="text-[var(--color-text-primary)] truncate max-w-[7.5rem]"
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: compact ? '0.75rem' : '0.8125rem',
            }}
          >
            {activeAccount.name}
          </span>
          <ChevronsUpDown className="size-3 text-[var(--color-text-disabled)] shrink-0 ml-0.5" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="start"
        sideOffset={8}
        className="w-[17.5rem] rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] p-0 shadow-lg"
      >
        {/* Current account header */}
        <div className="px-4 py-3 bg-[var(--color-surface-muted)]">
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] uppercase tracking-wide font-bold">
            Current Account
          </p>
          <div className="flex items-center gap-2.5 mt-1.5">
            <OrgAvatar org={activeOrg} size="md" />
            <div className="min-w-0">
              <p
                className="text-[var(--text-body-md)] text-[var(--color-text-primary)] truncate"
                style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}
              >
                {activeAccount.name}
              </p>
              <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] truncate">
                {activeOrg.name} &middot;{' '}
                <span className="capitalize">{activeAccount.role}</span>
              </p>
            </div>
          </div>
        </div>

        <DropdownMenuSeparator className="m-0" />

        {/* Account list grouped by org */}
        <div className="py-1.5 max-h-[18.75rem] overflow-y-auto">
          {accountsByOrg.map(({ org, accounts }, orgIndex) => (
            <div key={org.id}>
              {orgIndex > 0 && <DropdownMenuSeparator />}
              <DropdownMenuLabel className="flex items-center gap-2 px-4 py-2 text-[var(--text-caption)] text-[var(--color-text-tertiary)] uppercase tracking-wide font-bold">
                <Building2 className="size-3" />
                {org.name}
              </DropdownMenuLabel>
              <DropdownMenuGroup>
                {accounts.map((account) => {
                  const isActive = account.id === activeAccountId;
                  return (
                    <DropdownMenuItem
                      key={account.id}
                      onClick={() => handleAccountSwitch(account.id)}
                      className={cn(
                        'flex items-center gap-3 px-4 py-2.5 cursor-pointer rounded-none transition-colors',
                        isActive && 'bg-[var(--color-violet-100)]'
                      )}
                    >
                      <OrgAvatar org={org} />
                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            'text-[var(--text-body-sm)] truncate',
                            isActive
                              ? 'text-[var(--color-violet-500)]'
                              : 'text-[var(--color-text-primary)]'
                          )}
                          style={{ fontWeight: isActive ? 700 : 500 }}
                        >
                          {account.name}
                        </p>
                        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] capitalize">
                          {account.role}
                        </p>
                      </div>
                      {isActive && (
                        <Check className="size-4 text-[var(--color-violet-500)] shrink-0" />
                      )}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuGroup>
            </div>
          ))}
        </div>

        <DropdownMenuSeparator className="m-0" />

        {/* Footer actions */}
        <div className="py-1.5">
          <DropdownMenuItem asChild>
            <Link
              to="/settings/organization"
              className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]"
            >
              <Settings className="size-4" />
              <span className="text-[var(--text-body-sm)]">Organization Settings</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer rounded-none text-[var(--color-text-secondary)]">
            <Plus className="size-4" />
            <span className="text-[var(--text-body-sm)]">Add Account</span>
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
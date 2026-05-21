import type { TargetingRules } from "@/lib/featureFlags/types";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";

type Props = {
  value: TargetingRules;
  onChange: (next: TargetingRules) => void;
};

function parseList(raw: string): string[] {
  return raw
    .split(/[,\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function joinList(items: string[]): string {
  return items.join("\n");
}

export function TargetingRulesEditor({ value, onChange }: Props) {
  function handleListChange(
    field: keyof Omit<TargetingRules, "rollout_percentage">,
    raw: string,
  ) {
    onChange({ ...value, [field]: parseList(raw) });
  }

  function handleSliderChange(pct: number[]) {
    onChange({ ...value, rollout_percentage: pct[0] ?? 0 });
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="targeting-user-emails">
          User emails
          <span className="ml-1 text-[var(--color-text-tertiary)] font-normal text-xs">
            (comma or newline separated)
          </span>
        </Label>
        <Textarea
          id="targeting-user-emails"
          aria-label="User emails"
          placeholder="alice@example.com&#10;bob@example.com"
          value={joinList(value.user_emails)}
          onChange={(e) => handleListChange("user_emails", e.target.value)}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="targeting-email-domains">
          Email domains
          <span className="ml-1 text-[var(--color-text-tertiary)] font-normal text-xs">
            (comma or newline separated)
          </span>
        </Label>
        <Textarea
          id="targeting-email-domains"
          aria-label="Email domains"
          placeholder="ken-e.ai&#10;example.com"
          value={joinList(value.email_domains)}
          onChange={(e) => handleListChange("email_domains", e.target.value)}
          rows={2}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="targeting-org-ids">
          Organization IDs
          <span className="ml-1 text-[var(--color-text-tertiary)] font-normal text-xs">
            (comma or newline separated)
          </span>
        </Label>
        <Textarea
          id="targeting-org-ids"
          aria-label="Organization IDs"
          placeholder="org_01abc&#10;org_02def"
          value={joinList(value.organization_ids)}
          onChange={(e) => handleListChange("organization_ids", e.target.value)}
          rows={2}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="targeting-account-ids">
          Account IDs
          <span className="ml-1 text-[var(--color-text-tertiary)] font-normal text-xs">
            (comma or newline separated)
          </span>
        </Label>
        <Textarea
          id="targeting-account-ids"
          aria-label="Account IDs"
          placeholder="acc_01abc&#10;acc_02def"
          value={joinList(value.account_ids)}
          onChange={(e) => handleListChange("account_ids", e.target.value)}
          rows={2}
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label htmlFor="targeting-rollout-slider">Rollout percentage</Label>
          <span className="text-sm tabular-nums text-[var(--color-text-primary)]">
            {value.rollout_percentage}%
          </span>
        </div>
        <Slider
          id="targeting-rollout-slider"
          aria-label="Rollout percentage"
          min={0}
          max={100}
          step={1}
          value={[value.rollout_percentage]}
          onValueChange={handleSliderChange}
        />
        <p className="text-xs text-[var(--color-text-tertiary)]">
          0% = disabled for all; 100% = enabled for all (within this entity
          type)
        </p>
      </div>
    </div>
  );
}

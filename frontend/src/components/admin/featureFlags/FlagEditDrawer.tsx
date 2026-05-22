import { useEffect, useMemo } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useCreateFlag, useUpdateFlag } from "@/lib/featureFlags/hooks";
import type { FeatureFlag } from "@/lib/featureFlags/types";
import type {
  FeatureFlagCreate,
  FeatureFlagUpdate,
} from "@/lib/featureFlags/adminClient";
import { toFlagKey } from "@/lib/featureFlags/types";
import { TargetingRulesEditor } from "./TargetingRulesEditor";
import { FlagAuditList } from "./FlagAuditList";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from "@/components/ui/sheet";
import {
  Form,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

// ─── Tab value constants (used by tests for deterministic tab targeting) ──────

export const EDIT_TAB_VALUE = "edit" as const;
export const AUDIT_TAB_VALUE = "audit" as const;

// ─── Canonical admin-facing bucketing_entity help text ────────────────────────
// Kept in sync with docs/design/components/feature-flags/README.md §7.3
// between <!-- BUCKETING_ENTITY_HELP_TEXT_START --> and <!-- BUCKETING_ENTITY_HELP_TEXT_END -->.
// The colocated test snapshot-asserts this constant matches the README block.
export const BUCKETING_ENTITY_HELP_TEXT =
  "'account' is correct for most product flags. Choose 'user' only if the feature travels with the person across accounts (e.g., profile settings). 'organization' for org-wide capabilities.";

// ─── Zod schema ───────────────────────────────────────────────────────────────

const FLAG_KEY_REGEX = /^[a-z0-9][a-z0-9_]{2,63}$/;

export const targetingRulesSchema = z.object({
  user_emails: z.array(z.string()).default([]),
  email_domains: z.array(z.string()).default([]),
  organization_ids: z.array(z.string()).default([]),
  account_ids: z.array(z.string()).default([]),
  rollout_percentage: z.number().int().min(0).max(100).default(0),
});

const flagSchema = z.object({
  key: z
    .string()
    .min(1, "Key is required")
    .regex(
      FLAG_KEY_REGEX,
      "Key must match ^[a-z0-9][a-z0-9_]{2,63}$ (lowercase letters, digits, underscores; 3–64 chars)",
    ),
  description: z.string().min(1, "Description is required"),
  default_enabled: z.boolean().default(false),
  is_active: z.boolean().default(true),
  owner: z
    .string()
    .min(1, "Owner is required")
    .email("Owner must be a valid email"),
  expected_ga_release: z.string().nullable().optional(),
  bucketing_entity: z
    .enum(["account", "organization", "user"] as const)
    .default("account"),
  targeting_rules: targetingRulesSchema.default({
    user_emails: [],
    email_domains: [],
    organization_ids: [],
    account_ids: [],
    rollout_percentage: 0,
  }),
});

type FlagFormValues = z.infer<typeof flagSchema>;

// ─── Props ────────────────────────────────────────────────────────────────────

type FlagEditDrawerProps =
  | {
      open: boolean;
      onOpenChange: (open: boolean) => void;
      mode: "create";
      onSuccess?: (flag: FeatureFlag) => void;
    }
  | {
      open: boolean;
      onOpenChange: (open: boolean) => void;
      mode: "edit";
      flag: FeatureFlag;
      onSuccess?: (flag: FeatureFlag) => void;
    };

// ─── Component ────────────────────────────────────────────────────────────────

export function FlagEditDrawer(props: FlagEditDrawerProps) {
  const { open, onOpenChange, mode } = props;
  const flag = mode === "edit" ? props.flag : undefined;
  const onSuccess = props.onSuccess;

  const { user } = useAuth();
  const createFlag = useCreateFlag();
  const updateFlag = useUpdateFlag();

  const defaultValues = useMemo<FlagFormValues>(
    () =>
      mode === "edit" && flag
        ? {
            key: flag.key,
            description: flag.description,
            default_enabled: flag.default_enabled,
            is_active: flag.is_active,
            owner: flag.owner,
            expected_ga_release: flag.expected_ga_release ?? null,
            bucketing_entity: flag.bucketing_entity,
            targeting_rules: flag.targeting_rules,
          }
        : {
            key: "",
            description: "",
            default_enabled: false,
            is_active: true,
            owner: user?.email ?? "",
            expected_ga_release: null,
            bucketing_entity: "account",
            targeting_rules: {
              user_emails: [],
              email_domains: [],
              organization_ids: [],
              account_ids: [],
              rollout_percentage: 0,
            },
          },
    // flag?.key: recompute when a different flag is loaded; user?.email: seeds
    // the owner field for new flags. Both are stable across re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mode, flag?.key, user?.email],
  );

  const form = useForm<FlagFormValues>({
    resolver: zodResolver(flagSchema),
    defaultValues,
    mode: "onChange",
  });

  useEffect(() => {
    if (open) {
      form.reset(defaultValues);
    }
    // form is a stable ref from useForm; the real triggers are open + defaultValues
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultValues]);

  function onSubmit(data: FlagFormValues) {
    if (mode === "create") {
      const payload: FeatureFlagCreate = {
        key: toFlagKey(data.key),
        description: data.description,
        default_enabled: data.default_enabled,
        is_active: data.is_active,
        owner: data.owner,
        expected_ga_release: data.expected_ga_release ?? null,
        bucketing_entity: data.bucketing_entity,
        targeting_rules: data.targeting_rules,
      };
      createFlag.mutate(payload, {
        onSuccess: (created) => {
          onOpenChange(false);
          onSuccess?.(created);
        },
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "Failed to create flag",
          );
        },
      });
    } else if (mode === "edit" && flag) {
      const body: FeatureFlagUpdate = {
        key: flag.key,
        description: data.description,
        default_enabled: data.default_enabled,
        is_active: data.is_active,
        owner: data.owner,
        expected_ga_release: data.expected_ga_release ?? null,
        bucketing_entity: data.bucketing_entity,
        targeting_rules: data.targeting_rules,
      };
      updateFlag.mutate(
        { key: flag.key, body },
        {
          onSuccess: (updated) => {
            onOpenChange(false);
            onSuccess?.(updated);
          },
          onError: (err) => {
            toast.error(
              err instanceof Error ? err.message : "Failed to update flag",
            );
          },
        },
      );
    }
  }

  const isPending = createFlag.isPending || updateFlag.isPending;
  const title = mode === "create" ? "New feature flag" : "Edit feature flag";

  const formFields = (
    <>
      {/* Key */}
      <FormField
        control={form.control}
        name="key"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Flag key</FormLabel>
            <FormControl>
              <Input
                {...field}
                placeholder="my_feature_flag"
                disabled={mode === "edit"}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* Description */}
      <FormField
        control={form.control}
        name="description"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Description</FormLabel>
            <FormControl>
              <Textarea
                {...field}
                placeholder="What does this flag control?"
                rows={2}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* is_active + default_enabled */}
      <div className="flex gap-6">
        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center gap-3 space-y-0">
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-label="Is active"
                />
              </FormControl>
              <FormLabel className="font-normal">Active</FormLabel>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="default_enabled"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center gap-3 space-y-0">
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-label="Default enabled"
                />
              </FormControl>
              <FormLabel className="font-normal">Default enabled</FormLabel>
            </FormItem>
          )}
        />
      </div>

      {/* Owner */}
      <FormField
        control={form.control}
        name="owner"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Owner</FormLabel>
            <FormControl>
              <Input {...field} placeholder="engineer@ken-e.ai" />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* Expected GA release */}
      <FormField
        control={form.control}
        name="expected_ga_release"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Expected GA release</FormLabel>
            <FormControl>
              <Input
                {...field}
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value || null)}
                placeholder="Release 2"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* Bucketing entity */}
      <FormField
        control={form.control}
        name="bucketing_entity"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Bucketing entity</FormLabel>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger aria-label="Bucketing entity">
                  <SelectValue />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                <SelectItem value="account">account</SelectItem>
                <SelectItem value="organization">organization</SelectItem>
                <SelectItem value="user">user</SelectItem>
              </SelectContent>
            </Select>
            <FormDescription className="text-xs text-[var(--color-text-tertiary)] mt-1">
              {BUCKETING_ENTITY_HELP_TEXT}
            </FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* Targeting rules */}
      <div className="space-y-2">
        <Label className="text-[var(--text-label-md)] font-medium text-[var(--color-text-primary)]">
          Targeting rules
        </Label>
        <Controller
          control={form.control}
          name="targeting_rules"
          render={({ field }) => (
            <TargetingRulesEditor
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>
    </>
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {mode === "create"
              ? "Create a new feature flag with targeting rules."
              : `Editing flag: ${flag?.key}`}
          </SheetDescription>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-5 py-4"
          >
            {mode === "edit" ? (
              <Tabs defaultValue={EDIT_TAB_VALUE}>
                <TabsList>
                  <TabsTrigger value={EDIT_TAB_VALUE}>Edit</TabsTrigger>
                  <TabsTrigger value={AUDIT_TAB_VALUE}>Audit</TabsTrigger>
                </TabsList>

                <TabsContent value={EDIT_TAB_VALUE} className="space-y-5">
                  {formFields}
                </TabsContent>

                <TabsContent value={AUDIT_TAB_VALUE}>
                  <FlagAuditList flagKey={flag!.key} />
                </TabsContent>
              </Tabs>
            ) : (
              <div className="space-y-5">{formFields}</div>
            )}

            <SheetFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending
                  ? mode === "create"
                    ? "Creating…"
                    : "Saving…"
                  : mode === "create"
                    ? "Create flag"
                    : "Save changes"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}

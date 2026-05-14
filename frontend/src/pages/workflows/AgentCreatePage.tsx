import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Bot } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useCreateAgentConfig } from "@/queries/agentConfigs";
import { SUPPORTED_MODELS } from "@/lib/api/agentConfigs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DisabledPlaceholderRow } from "./agents/DisabledPlaceholderRow";

// ─── Schema ───────────────────────────────────────────────────────────────────
//
// Field constraints mirror ``AgentConfigCreate`` in
// ``api/src/kene_api/models/agent_config_models.py``. Keeping them in sync
// surfaces validation problems inline before the request is sent — the API
// still re-validates, and any 422 fields it returns are mapped back onto the
// form by ``onError`` below.

export const schema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Title is required")
    .max(100, "Title must be 100 characters or fewer"),
  name: z
    .string()
    .trim()
    .max(100, "Name must be 100 characters or fewer")
    .optional(),
  instruction: z
    .string()
    .min(10, "Instruction must be at least 10 characters")
    .max(50000, "Instruction must be 50,000 characters or fewer"),
  model: z.enum(SUPPORTED_MODELS as [string, ...string[]], {
    errorMap: () => ({ message: "Model is required" }),
  }),
  temperature: z.number().min(0.1).max(0.9).optional(),
  // Optional, but the API enforces min_length=10 when provided. Allow empty
  // (treated as "not set" — onSubmit converts it to null) or at least 10
  // characters when the user types something.
  description: z
    .string()
    .max(1000, "Description must be 1,000 characters or fewer")
    .refine((v) => v.length === 0 || v.trim().length >= 10, {
      message: "Description must be at least 10 characters",
    })
    .optional(),
});

type FormValues = z.infer<typeof schema>;

// Fields we know how to surface inline from a FastAPI 422 ``detail`` entry.
const FORM_FIELDS = [
  "title",
  "name",
  "instruction",
  "model",
  "temperature",
  "description",
] as const satisfies readonly (keyof FormValues)[];

// ─── AgentCreatePage ──────────────────────────────────────────────────────────

export function AgentCreatePage() {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;
  const mutation = useCreateAgentConfig(accountId);

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isValid },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { temperature: 0.3 },
  });

  function onSubmit(data: FormValues) {
    const trimmedName = data.name?.trim();
    const trimmedDescription = data.description?.trim();
    const payload = {
      ...data,
      name: trimmedName ? trimmedName : null,
      description: trimmedDescription ? trimmedDescription : null,
    };
    mutation.mutate(payload, {
      onSuccess: (created) => {
        toast.success("Agent created.");
        navigate(
          `/workflows/agents?edit=${encodeURIComponent(created.config_id)}`,
        );
      },
      onError: (err) => {
        // FastAPI returns ``{ detail: [{ loc: ["body", "<field>"], msg, ... }] }``
        // for 422 validation failures. Surface each entry on its field so the
        // user sees what to fix instead of a generic toast.
        const detail = (err as { response?: { data?: { detail?: unknown } } })
          ?.response?.data?.detail;
        if (Array.isArray(detail)) {
          let mapped = 0;
          for (const item of detail) {
            const loc = (item as { loc?: unknown[] })?.loc;
            const msg = (item as { msg?: string })?.msg;
            const field =
              Array.isArray(loc) && typeof loc[loc.length - 1] === "string"
                ? (loc[loc.length - 1] as string)
                : undefined;
            if (
              field &&
              (FORM_FIELDS as readonly string[]).includes(field) &&
              typeof msg === "string"
            ) {
              setError(field as keyof FormValues, {
                type: "server",
                message: msg,
              });
              mapped++;
            }
          }
          if (mapped > 0) {
            toast.error("Please fix the highlighted fields and try again.");
            return;
          }
        }
        toast.error("Failed to create agent.");
      },
    });
  }

  const isSubmitDisabled = !accountId || mutation.isPending || !isValid;

  return (
    <div className="px-6 pb-6">
      {/* Back link */}
      <Link to="/workflows/agents">
        <Button
          variant="ghost"
          size="sm"
          className="gap-2 mb-4 -ml-2 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to Agents
        </Button>
      </Link>

      <h1 className="mb-1">Create custom agent</h1>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-5 max-w-2xl mt-6"
      >
        {/* Title (role) */}
        <div>
          <Label htmlFor="agent-title">
            Title <span aria-hidden="true">*</span>
          </Label>
          <Input
            id="agent-title"
            placeholder="e.g. Business Researcher"
            {...register("title")}
            className="mt-1.5"
            data-testid="title-input"
          />
          {errors.title && (
            <p className="text-xs text-destructive mt-1">
              {errors.title.message}
            </p>
          )}
        </div>

        {/* Name (human, optional) */}
        <div>
          <Label htmlFor="agent-name">Name</Label>
          <Input
            id="agent-name"
            placeholder="e.g. Dave (optional)"
            {...register("name")}
            className="mt-1.5"
            data-testid="name-input"
          />
          {errors.name && (
            <p className="text-xs text-destructive mt-1">
              {errors.name.message}
            </p>
          )}
        </div>

        {/* Instruction */}
        <div>
          <Label htmlFor="agent-instruction">
            Instruction <span aria-hidden="true">*</span>
          </Label>
          <Textarea
            id="agent-instruction"
            placeholder="You are a marketing expert who specializes in..."
            {...register("instruction")}
            rows={8}
            className="mt-1.5 min-h-[10rem] resize-y"
            data-testid="instruction-field"
          />
          {errors.instruction && (
            <p className="text-xs text-destructive mt-1">
              {errors.instruction.message}
            </p>
          )}
        </div>

        {/* Model */}
        <div>
          <Label htmlFor="agent-model">
            Model <span aria-hidden="true">*</span>
          </Label>
          <Controller
            name="model"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger
                  id="agent-model"
                  className="mt-1.5"
                  data-testid="model-select"
                >
                  <SelectValue placeholder="Select a model" />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_MODELS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.model && (
            <p className="text-xs text-destructive mt-1">
              {errors.model.message}
            </p>
          )}
        </div>

        {/* Response style (stored as `temperature`) */}
        <div>
          <Controller
            name="temperature"
            control={control}
            render={({ field }) => (
              <div className="flex items-center gap-3">
                <span className="text-[0.75rem] text-[var(--color-text-secondary)]">
                  Precise
                </span>
                <Slider
                  aria-label="Response style: precise to creative"
                  min={0.1}
                  max={0.9}
                  step={0.1}
                  value={[field.value ?? 0.3]}
                  onValueChange={([val]) => field.onChange(val)}
                  thumbContent={(field.value ?? 0.3).toFixed(1)}
                  className="flex-1"
                  data-testid="temperature-slider"
                />
                <span className="text-[0.75rem] text-[var(--color-text-secondary)]">
                  Creative
                </span>
              </div>
            )}
          />
        </div>

        {/* Description (optional) */}
        <div>
          <Label htmlFor="agent-description">Description</Label>
          <Textarea
            id="agent-description"
            placeholder="A brief description of what this agent does"
            {...register("description")}
            rows={3}
            className="mt-1.5"
            data-testid="description-field"
          />
          {errors.description && (
            <p className="text-xs text-destructive mt-1">
              {errors.description.message}
            </p>
          )}
        </div>

        <Separator />

        {/* Disabled placeholder rows */}
        <div className="space-y-2">
          <DisabledPlaceholderRow label="Skills" />
          <DisabledPlaceholderRow label="Sandbox code execution" />
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between pt-6"
          style={{ borderTop: "2px dashed var(--color-border-default)" }}
        >
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/workflows/agents")}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitDisabled} className="gap-2">
            <Bot className="size-4" />
            Create agent
          </Button>
        </div>
      </form>
    </div>
  );
}

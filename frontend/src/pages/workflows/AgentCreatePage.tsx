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

export const schema = z.object({
  title: z.string().min(1, "Title is required"),
  name: z.string().optional(),
  instruction: z.string().min(1, "Instruction is required"),
  model: z.enum(SUPPORTED_MODELS as [string, ...string[]], {
    errorMap: () => ({ message: "Model is required" }),
  }),
  temperature: z.number().min(0.1).max(0.9).optional(),
  description: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

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
    formState: { errors, isValid },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { temperature: 0.3 },
  });

  function onSubmit(data: FormValues) {
    const trimmedName = data.name?.trim();
    const payload = {
      ...data,
      name: trimmedName ? trimmedName : null,
    };
    mutation.mutate(payload, {
      onSuccess: (created) => {
        toast.success("Agent created.");
        navigate(
          `/workflows/agents?edit=${encodeURIComponent(created.config_id)}`,
        );
      },
      onError: () => {
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

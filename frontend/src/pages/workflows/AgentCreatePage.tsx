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

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  instruction: z.string().min(1, "Instruction is required"),
  model: z.enum(SUPPORTED_MODELS as [string, ...string[]], {
    errorMap: () => ({ message: "Model is required" }),
  }),
  temperature: z.number().min(0).max(1).optional(),
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
    watch,
    formState: { errors, isValid },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { temperature: 0.3 },
  });

  function onSubmit(data: FormValues) {
    mutation.mutate(data, {
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

  const temperatureValue = watch("temperature") ?? 0.3;
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
        {/* Name */}
        <div>
          <Label htmlFor="agent-name">
            Name <span aria-hidden="true">*</span>
          </Label>
          <Input
            id="agent-name"
            placeholder="e.g. SEO Analyst..."
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
            className="mt-1.5 min-h-[160px] resize-y"
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

        {/* Temperature (optional) */}
        <div>
          <Label htmlFor="agent-temperature">
            Temperature
            {/* allow-text-tertiary: secondary-metadata slider value readout */}
            <span className="ml-2 text-[11px] text-[var(--color-text-tertiary)]">
              {temperatureValue.toFixed(2)}
            </span>
          </Label>
          <Controller
            name="temperature"
            control={control}
            render={({ field }) => (
              <Slider
                id="agent-temperature"
                min={0}
                max={1}
                step={0.01}
                value={[field.value ?? 0.3]}
                onValueChange={([val]) => field.onChange(val)}
                className="mt-2"
                data-testid="temperature-slider"
              />
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

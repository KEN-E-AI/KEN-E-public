import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Bot, Save, RefreshCw, Info } from "lucide-react";
import {
  agentConfigService,
  type AgentConfig,
  type AgentConfigUpdate,
} from "@/services/agentConfigService";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// Helper function to get model options based on agent type
const getModelOptionsForAgent = (
  configName: string,
): Array<{ value: string; label: string }> => {
  if (
    configName.includes("researcher") ||
    configName === "ken_e_chatbot" ||
    configName === "google_analytics_agent" ||
    configName === "company_news_agent"
  ) {
    // Gemini models for researchers and chatbot
    return [
      { value: "gemini-3-flash-preview", label: "Gemini 3.0 Flash (Preview)" },
      { value: "gemini-3-pro-preview", label: "Gemini 3.0 Pro (Preview)" },
      { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
      {
        value: "gemini-2.0-flash-exp",
        label: "Gemini 2.0 Flash (Experimental)",
      },
      { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
      { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
      { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
    ];
  } else if (configName.includes("formatter")) {
    // OpenAI models for formatters
    return [
      { value: "gpt-4o", label: "GPT-4o (Latest)" },
      { value: "gpt-4o-2024-08-06", label: "GPT-4o (Aug 2024)" },
      { value: "gpt-4o-mini", label: "GPT-4o Mini" },
      { value: "o1-preview", label: "O1 Preview (Reasoning)" },
      { value: "o1-mini", label: "O1 Mini (Reasoning)" },
    ];
  }
  // Default fallback
  return [
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  ];
};

const AgentConfigManagement = () => {
  const navigate = useNavigate();
  const { isSuperAdmin, user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
  const [editedConfig, setEditedConfig] = useState<AgentConfig | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Redirect if not super admin
  if (!isSuperAdmin) {
    navigate("/settings");
    return null;
  }

  // Fetch all config IDs
  const { data: configIds, isLoading: isLoadingList } = useQuery({
    queryKey: ["agent-configs-list"],
    queryFn: () => agentConfigService.listConfigs(),
  });

  // Fetch selected config
  const { data: config, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["agent-config", selectedConfigId],
    queryFn: () => agentConfigService.getConfig(selectedConfigId!),
    enabled: !!selectedConfigId,
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (update: { configId: string; data: AgentConfigUpdate }) =>
      agentConfigService.updateConfig(update.configId, update.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["agent-config", selectedConfigId],
      });
      queryClient.invalidateQueries({ queryKey: ["agent-configs-list"] });
      setEditedConfig(data);
      setHasUnsavedChanges(false);
      toast({
        title: "Config Updated",
        description: `${agentConfigService.formatAgentName(selectedConfigId!)} updated to ${data.metadata.version}`,
      });
    },
    onError: (error: any) => {
      const detail =
        error?.response?.data?.detail ||
        error?.message ||
        String(error) ||
        "Failed to update config";
      toast({
        title: "Update Failed",
        description: typeof detail === "string" ? detail : JSON.stringify(detail),
        variant: "destructive",
      });
    },
  });

  // When config loads, set it as edited config
  if (config && !editedConfig && selectedConfigId) {
    setEditedConfig(config);
  }

  // Reset edited config when selecting new agent
  const handleSelectConfig = (configId: string) => {
    if (hasUnsavedChanges) {
      if (
        !confirm(
          "You have unsaved changes. Are you sure you want to switch configs?",
        )
      ) {
        return;
      }
    }
    setSelectedConfigId(configId);
    setEditedConfig(null);
    setHasUnsavedChanges(false);
  };

  const handleSave = () => {
    if (!editedConfig || !selectedConfigId || !user) return;

    const update: AgentConfigUpdate = {
      instruction: editedConfig.instruction,
      model: editedConfig.model,
      description: editedConfig.description,
      temperature: editedConfig.generate_content_config.temperature,
      max_output_tokens: editedConfig.generate_content_config.max_output_tokens,
      version: editedConfig.metadata.version !== config?.metadata.version
        ? editedConfig.metadata.version
        : undefined,
      variant_name: editedConfig.metadata.variant_name,
      experiment_id: editedConfig.metadata.experiment_id,
      updated_by: user.email || "unknown",
      notes: editedConfig.metadata.notes,
    };

    updateMutation.mutate({ configId: selectedConfigId, data: update });
  };

  const handleReset = () => {
    if (config) {
      setEditedConfig(config);
      setHasUnsavedChanges(false);
    }
  };

  const updateField = (field: string, value: any) => {
    if (!editedConfig) return;

    const updated = { ...editedConfig };

    if (field.startsWith("metadata.")) {
      const metadataField = field.split(".")[1];
      updated.metadata = { ...updated.metadata, [metadataField]: value };
    } else if (field.startsWith("generate_content_config.")) {
      const genField = field.split(".")[1];
      updated.generate_content_config = {
        ...updated.generate_content_config,
        [genField]: value,
      };
    } else {
      (updated as any)[field] = value;
    }

    setEditedConfig(updated);
    setHasUnsavedChanges(true);
  };

  // Categorize configs by strategy type
  const categorizedConfigs = configIds
    ? agentConfigService.categorizeConfigs(configIds)
    : {};

  return (
    <SettingsLayout
      pageTitle="Agent Configuration"
      currentPage="admin"
      showBackButton={true}
      showEntitySelector={false}
      showContextSidebar={false}
    >
      <div className="space-y-6">
        {/* Header */}
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Agent Config Management</AlertTitle>
          <AlertDescription>
            Edit agent configurations including model selection, instructions,
            and generation parameters. All changes are saved to Firestore and
            versioned in Weave.
            <br />
            <br />
            <strong>Note:</strong> For the KEN-E Chatbot agent, restart the API
            server locally or redeploy to apply changes.
          </AlertDescription>
        </Alert>

        <div className="grid grid-cols-12 gap-6">
          {/* Sidebar - Config Selector */}
          <div className="col-span-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Select Agent</CardTitle>
                <CardDescription>Choose an agent to configure</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {isLoadingList ? (
                  <div className="text-sm text-muted-foreground">
                    Loading...
                  </div>
                ) : (
                  Object.entries(categorizedConfigs)
                    .filter(
                      ([, configs]) =>
                        configs.researcher || configs.formatter,
                    )
                    .map(([strategy, configs]) => (
                      <div key={strategy} className="space-y-1">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-2 py-1">
                          {strategy}
                        </div>
                        {configs.researcher && (
                          <Button
                            variant={
                              selectedConfigId === configs.researcher
                                ? "default"
                                : "ghost"
                            }
                            className="w-full justify-start text-sm"
                            size="sm"
                            onClick={() =>
                              handleSelectConfig(configs.researcher)
                            }
                          >
                            <Bot className="h-4 w-4 mr-2" />
                            Researcher
                          </Button>
                        )}
                        {configs.formatter && (
                          <Button
                            variant={
                              selectedConfigId === configs.formatter
                                ? "default"
                                : "ghost"
                            }
                            className="w-full justify-start text-sm"
                            size="sm"
                            onClick={() =>
                              handleSelectConfig(configs.formatter)
                            }
                          >
                            <Bot className="h-4 w-4 mr-2" />
                            Formatter
                          </Button>
                        )}
                      </div>
                    ))
                )}

                {/* Chatbot Agent Section */}
                {categorizedConfigs.chatbot?.chatbot && (
                  <div className="space-y-1 mt-4">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-2 py-1">
                      Chatbot
                    </div>
                    <Button
                      variant={
                        selectedConfigId === categorizedConfigs.chatbot.chatbot
                          ? "default"
                          : "ghost"
                      }
                      className="w-full justify-start text-sm"
                      size="sm"
                      onClick={() =>
                        handleSelectConfig(categorizedConfigs.chatbot.chatbot!)
                      }
                    >
                      <Bot className="h-4 w-4 mr-2" />
                      KEN-E Chatbot
                    </Button>
                  </div>
                )}

                {/* Analytics Agent Section */}
                {categorizedConfigs.analytics?.chatbot && (
                  <div className="space-y-1 mt-4">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-2 py-1">
                      Analytics
                    </div>
                    <Button
                      variant={
                        selectedConfigId ===
                        categorizedConfigs.analytics.chatbot
                          ? "default"
                          : "ghost"
                      }
                      className="w-full justify-start text-sm"
                      size="sm"
                      onClick={() =>
                        handleSelectConfig(
                          categorizedConfigs.analytics.chatbot!,
                        )
                      }
                    >
                      <Bot className="h-4 w-4 mr-2" />
                      Google Analytics
                    </Button>
                  </div>
                )}

                {/* News Agent Section */}
                {categorizedConfigs.news?.chatbot && (
                  <div className="space-y-1 mt-4">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-2 py-1">
                      News
                    </div>
                    <Button
                      variant={
                        selectedConfigId === categorizedConfigs.news.chatbot
                          ? "default"
                          : "ghost"
                      }
                      className="w-full justify-start text-sm"
                      size="sm"
                      onClick={() =>
                        handleSelectConfig(categorizedConfigs.news.chatbot!)
                      }
                    >
                      <Bot className="h-4 w-4 mr-2" />
                      Company News
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Main Content - Config Editor */}
          <div className="col-span-9">
            {!selectedConfigId ? (
              <Card>
                <CardContent className="flex items-center justify-center h-96">
                  <div className="text-center text-muted-foreground">
                    <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p>Select an agent to view and edit its configuration</p>
                  </div>
                </CardContent>
              </Card>
            ) : isLoadingConfig ? (
              <Card>
                <CardContent className="flex items-center justify-center h-96">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            ) : editedConfig ? (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>
                        {agentConfigService.formatAgentName(selectedConfigId)}
                      </CardTitle>
                      <CardDescription>
                        Version: {editedConfig.metadata.version} •{" "}
                        {editedConfig.metadata.variant_name}
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleReset}
                        disabled={
                          !hasUnsavedChanges || updateMutation.isPending
                        }
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Reset
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={
                          !hasUnsavedChanges || updateMutation.isPending
                        }
                      >
                        <Save className="h-4 w-4 mr-2" />
                        Save Changes
                      </Button>
                    </div>
                  </div>
                </CardHeader>

                <CardContent>
                  <Tabs defaultValue="instruction" className="space-y-4">
                    <TabsList>
                      <TabsTrigger value="instruction">Instruction</TabsTrigger>
                      <TabsTrigger value="config">Configuration</TabsTrigger>
                      <TabsTrigger value="metadata">Metadata</TabsTrigger>
                    </TabsList>

                    {/* Instruction Tab */}
                    <TabsContent value="instruction" className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="instruction">Agent Instruction</Label>
                        <Textarea
                          id="instruction"
                          value={editedConfig.instruction}
                          onChange={(e) =>
                            updateField("instruction", e.target.value)
                          }
                          className="font-mono text-sm min-h-[400px]"
                          placeholder="Enter agent instruction..."
                        />
                        <p className="text-xs text-muted-foreground">
                          {editedConfig.instruction.length} characters
                        </p>
                      </div>
                    </TabsContent>

                    {/* Configuration Tab */}
                    <TabsContent value="config" className="space-y-4">
                      <div className="grid gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="model">Model</Label>
                          <Select
                            value={editedConfig.model}
                            onValueChange={(value) =>
                              updateField("model", value)
                            }
                          >
                            <SelectTrigger id="model">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {getModelOptionsForAgent(
                                selectedConfigId || "",
                              ).map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={option.value}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="description">Description</Label>
                          <Input
                            id="description"
                            value={editedConfig.description}
                            onChange={(e) =>
                              updateField("description", e.target.value)
                            }
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="temperature">
                              Temperature (
                              {editedConfig.generate_content_config.temperature}
                              )
                            </Label>
                            <Input
                              id="temperature"
                              type="number"
                              min="0"
                              max="1"
                              step="0.1"
                              value={
                                editedConfig.generate_content_config.temperature
                              }
                              onChange={(e) =>
                                updateField(
                                  "generate_content_config.temperature",
                                  parseFloat(e.target.value),
                                )
                              }
                            />
                            <p className="text-xs text-muted-foreground">
                              0 = focused, 1 = creative
                            </p>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="max_tokens">
                              Max Output Tokens
                            </Label>
                            <Input
                              id="max_tokens"
                              type="number"
                              min="100"
                              max="65535"
                              step="100"
                              value={
                                editedConfig.generate_content_config
                                  .max_output_tokens
                              }
                              onChange={(e) =>
                                updateField(
                                  "generate_content_config.max_output_tokens",
                                  parseInt(e.target.value),
                                )
                              }
                            />
                            <p className="text-xs text-muted-foreground">
                              Increase if output is truncated
                            </p>
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    {/* Metadata Tab */}
                    <TabsContent value="metadata" className="space-y-4">
                      <div className="grid gap-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="version">Version</Label>
                            <Input
                              id="version"
                              value={editedConfig.metadata.version}
                              onChange={(e) =>
                                updateField("metadata.version", e.target.value)
                              }
                              placeholder="v1.0.0"
                            />
                            <p className="text-xs text-muted-foreground">
                              Auto-incremented on save if not changed
                            </p>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="variant_name">Variant Name</Label>
                            <Input
                              id="variant_name"
                              value={editedConfig.metadata.variant_name}
                              onChange={(e) =>
                                updateField(
                                  "metadata.variant_name",
                                  e.target.value,
                                )
                              }
                              placeholder="baseline"
                            />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="experiment_id">Experiment ID</Label>
                          <Input
                            id="experiment_id"
                            value={editedConfig.metadata.experiment_id}
                            onChange={(e) =>
                              updateField(
                                "metadata.experiment_id",
                                e.target.value,
                              )
                            }
                            placeholder="exp_001"
                          />
                          <p className="text-xs text-muted-foreground">
                            Use same ID to group related test variants in Weave
                          </p>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="notes">Change Notes</Label>
                          <Textarea
                            id="notes"
                            value={editedConfig.metadata.notes}
                            onChange={(e) =>
                              updateField("metadata.notes", e.target.value)
                            }
                            placeholder="Describe what changed and why..."
                            rows={3}
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              Created At
                            </Label>
                            <p className="text-sm">
                              {new Date(
                                editedConfig.metadata.created_at,
                              ).toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              Last Updated
                            </Label>
                            <p className="text-sm">
                              {new Date(
                                editedConfig.metadata.updated_at,
                              ).toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              Updated By
                            </Label>
                            <p className="text-sm">
                              {editedConfig.metadata.updated_by}
                            </p>
                          </div>
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>

                  {/* Save indicator */}
                  {hasUnsavedChanges && (
                    <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md">
                      <p className="text-sm text-yellow-800 dark:text-yellow-200">
                        You have unsaved changes. Click "Save Changes" to apply
                        them to Firestore.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </SettingsLayout>
  );
};

export default AgentConfigManagement;

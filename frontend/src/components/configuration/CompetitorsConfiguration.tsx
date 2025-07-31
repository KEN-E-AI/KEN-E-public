import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/use-toast";
import { Loader2, Plus, X, Edit2, Trash2, Globe } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import type { MonitoringTopics, CompetitorEntry } from "@/types/monitoring";
import api from "@/lib/api";

export default function CompetitorsConfiguration() {
  const { selectedOrgAccount } = useAuth();
  const queryClient = useQueryClient();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [formData, setFormData] = useState<Partial<CompetitorEntry>>({
    name: "",
    website: "",
    keywords: [],
  });
  const [keywordInput, setKeywordInput] = useState("");

  // Fetch monitoring topics
  const { data: monitoringTopics, isLoading } = useQuery<MonitoringTopics | null>({
    queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
    queryFn: async () => {
      if (!selectedOrgAccount?.accountId) throw new Error("No account selected");
      const response = await api.get(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}`,
      );
      return response.data.data || null;
    },
    enabled: !!selectedOrgAccount?.accountId,
  });

  // Add competitor mutation
  const addMutation = useMutation({
    mutationFn: async (competitor: Partial<CompetitorEntry>) => {
      if (!selectedOrgAccount?.accountId) throw new Error("No account selected");
      const response = await api.post(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/competitors`,
        {
          account_id: selectedOrgAccount.accountId,
          ...competitor,
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      toast({
        title: "Success",
        description: "Competitor added successfully",
      });
      setIsAddDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to add competitor",
        variant: "destructive",
      });
    },
  });

  // Update competitor mutation
  const updateMutation = useMutation({
    mutationFn: async ({
      index,
      competitor,
    }: {
      index: number;
      competitor: Partial<CompetitorEntry>;
    }) => {
      if (!selectedOrgAccount?.accountId) throw new Error("No account selected");
      const response = await api.put(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/competitors/${index}`,
        {
          account_id: selectedOrgAccount.accountId,
          competitor_index: index,
          ...competitor,
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      toast({
        title: "Success",
        description: "Competitor updated successfully",
      });
      setEditingIndex(null);
      resetForm();
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to update competitor",
        variant: "destructive",
      });
    },
  });

  // Delete competitor mutation
  const deleteMutation = useMutation({
    mutationFn: async (index: number) => {
      if (!selectedOrgAccount?.accountId) throw new Error("No account selected");
      const response = await api.delete(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/competitors/${index}`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      toast({
        title: "Success",
        description: "Competitor removed successfully",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to remove competitor",
        variant: "destructive",
      });
    },
  });

  const resetForm = () => {
    setFormData({ name: "", website: "", keywords: [] });
    setKeywordInput("");
  };

  const handleAddKeyword = () => {
    const trimmedKeyword = keywordInput.trim().toLowerCase();
    if (trimmedKeyword && !formData.keywords?.includes(trimmedKeyword)) {
      setFormData({
        ...formData,
        keywords: [...(formData.keywords || []), trimmedKeyword],
      });
      setKeywordInput("");
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    setFormData({
      ...formData,
      keywords: formData.keywords?.filter((k) => k !== keyword) || [],
    });
  };

  const handleSubmit = () => {
    if (!formData.name?.trim()) {
      toast({
        title: "Error",
        description: "Competitor name is required",
        variant: "destructive",
      });
      return;
    }

    // If no keywords specified, use the competitor name as a keyword
    const finalData = {
      ...formData,
      keywords: formData.keywords?.length
        ? formData.keywords
        : [formData.name.toLowerCase()],
    };

    if (editingIndex !== null) {
      updateMutation.mutate({ index: editingIndex, competitor: finalData });
    } else {
      addMutation.mutate(finalData);
    }
  };

  const handleEdit = (index: number, competitor: CompetitorEntry) => {
    setEditingIndex(index);
    setFormData(competitor);
    setIsAddDialogOpen(true);
  };

  const handleDelete = (index: number) => {
    if (confirm("Are you sure you want to remove this competitor?")) {
      deleteMutation.mutate(index);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  const competitors = monitoringTopics?.competitor_entries || [];

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-end">
            <Button onClick={() => setIsAddDialogOpen(true)} size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Add Competitor
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">

          {competitors.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No competitors added yet
            </p>
          ) : (
            <div className="space-y-3">
              {competitors.map((competitor, index) => (
                <div
                  key={index}
                  className="flex items-start justify-between rounded-lg border p-4"
                >
                  <div className="space-y-2 flex-1">
                    <div>
                      <h4 className="font-medium">{competitor.name}</h4>
                      {competitor.website && (
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <Globe className="h-3 w-3" />
                          <a
                            href={competitor.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {competitor.website}
                          </a>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {competitor.keywords.map((keyword) => (
                        <Badge
                          key={keyword}
                          variant="secondary"
                          className="text-xs"
                        >
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(index, competitor)}
                    >
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={isAddDialogOpen}
        onOpenChange={(open) => {
          setIsAddDialogOpen(open);
          if (!open) {
            setEditingIndex(null);
            resetForm();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingIndex !== null ? "Edit Competitor" : "Add Competitor"}
            </DialogTitle>
            <DialogDescription>
              Enter competitor details to monitor their mentions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Competitor Name</Label>
              <Input
                id="name"
                placeholder="e.g., Acme Corp"
                value={formData.name || ""}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="website">Website (Optional)</Label>
              <Input
                id="website"
                placeholder="e.g., https://acmecorp.com"
                value={formData.website || ""}
                onChange={(e) =>
                  setFormData({ ...formData, website: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Keywords</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Add a keyword"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddKeyword();
                    }
                  }}
                />
                <Button
                  type="button"
                  onClick={handleAddKeyword}
                  disabled={!keywordInput.trim()}
                  size="icon"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formData.keywords?.map((keyword) => (
                  <Badge
                    key={keyword}
                    variant="secondary"
                    className="pl-3 pr-1 py-1 text-sm"
                  >
                    {keyword}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-1 h-4 w-4 p-0 hover:bg-transparent"
                      onClick={() => handleRemoveKeyword(keyword)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                If no keywords are specified, the competitor name will be used
                as a keyword.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={addMutation.isPending || updateMutation.isPending}
            >
              {(addMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editingIndex !== null ? "Update" : "Add"} Competitor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

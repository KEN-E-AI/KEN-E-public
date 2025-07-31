import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import { Loader2, Plus, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import type { MonitoringTopics } from "@/types/monitoring";
import api from "@/lib/api";

export default function CustomerKeywordsConfiguration() {
  const { selectedOrgAccount } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyword, setNewKeyword] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);

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

  // Initialize keywords when data loads
  useEffect(() => {
    if (monitoringTopics?.customer_keywords) {
      setKeywords(monitoringTopics.customer_keywords);
    }
  }, [monitoringTopics]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (updatedKeywords: string[]) => {
      if (!selectedOrgAccount?.accountId) throw new Error("No account selected");
      const response = await api.put(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/customers`,
        {
          account_id: selectedOrgAccount.accountId,
          customer_keywords: updatedKeywords,
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
        description: "Customer keywords updated successfully",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to update customer keywords",
        variant: "destructive",
      });
    },
  });

  const handleAddKeyword = () => {
    const trimmedKeyword = newKeyword.trim().toLowerCase();
    if (trimmedKeyword && !keywords.includes(trimmedKeyword)) {
      const updatedKeywords = [...keywords, trimmedKeyword];
      setKeywords(updatedKeywords);
      setNewKeyword("");
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    const updatedKeywords = keywords.filter((k) => k !== keyword);
    setKeywords(updatedKeywords);
  };

  const handleSaveKeywords = () => {
    updateMutation.mutate(keywords);
  };

  const hasChanges =
    JSON.stringify(keywords) !==
    JSON.stringify(monitoringTopics?.customer_keywords || []);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Customer Concepts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Add a keyword (e.g., customer segment, region, hashtag)"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddKeyword();
              }
            }}
          />
          <Button
            onClick={handleAddKeyword}
            disabled={!newKeyword.trim()}
            size="icon"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword) => (
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
          {keywords.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No keywords added yet
            </p>
          )}
        </div>

        {hasChanges && (
          <div className="flex justify-end">
            <Button
              onClick={handleSaveKeywords}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save Changes
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

import { useState } from "react";
import CompanyKeywordsConfiguration from "@/components/configuration/CompanyKeywordsConfiguration";
import Layout from "@/components/layout/Layout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import type { MonitoringTopics } from "@/types/monitoring";
import api from "@/lib/api";

export default function KnowledgeAccount() {
  const { selectedOrgAccount } = useAuth();

  // Fetch monitoring topics to display industry keywords
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

  return (
    <Layout pageTitle="Account Knowledge">
      <div className="space-y-6">
        <p className="text-muted-foreground">
          Manage keywords that describe your company and industry for news
          monitoring.
        </p>

        <div className="space-y-4">
          {/* Industry Keywords (Read-only) */}
          <Card>
            <CardHeader>
              <CardTitle>Industry Concepts</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Industry:</span>
                    <span className="font-medium text-foreground">
                      {selectedOrgAccount?.metadata?.industry || "Not set"}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {monitoringTopics?.industry_keywords?.length ? (
                      monitoringTopics.industry_keywords.map((keyword) => (
                        <Badge key={keyword} variant="outline">
                          {keyword}
                        </Badge>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No industry keywords defined yet
                      </p>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Company Keywords (Editable) */}
          <CompanyKeywordsConfiguration />
        </div>
      </div>
    </Layout>
  );
}

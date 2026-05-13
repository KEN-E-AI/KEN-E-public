import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  Plus,
  X,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import type { MonitoringTopics } from "@/types/monitoring";
import api from "@/lib/api";
import CompanyKeywordsConfigurationSkeleton from "./CompanyKeywordsConfigurationSkeleton";
import { KeywordValidation } from "@/utils/validation";

interface PaginatedKeywordsResponse {
  keywords: string[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function CompanyKeywordsConfigurationPaginated() {
  const { selectedOrgAccount } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyword, setNewKeyword] = useState("");
  const [localKeywords, setLocalKeywords] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1); // Reset to first page on search
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Fetch all monitoring topics (for getting the full list for updates)
  const { data: monitoringTopics } = useQuery<MonitoringTopics | null>({
    queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
    queryFn: async () => {
      if (!selectedOrgAccount?.accountId)
        throw new Error("No account selected");
      const response = await api.get(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}`,
      );
      return response.data.data || null;
    },
    enabled: !!selectedOrgAccount?.accountId,
  });

  // Fetch paginated keywords
  const { data: paginatedData, isLoading } =
    useQuery<PaginatedKeywordsResponse>({
      queryKey: [
        "company-keywords-paginated",
        selectedOrgAccount?.accountId,
        page,
        pageSize,
        debouncedSearchTerm,
      ],
      queryFn: async () => {
        if (!selectedOrgAccount?.accountId)
          throw new Error("No account selected");
        const params = new URLSearchParams({
          page: page.toString(),
          page_size: pageSize.toString(),
        });
        if (debouncedSearchTerm) {
          params.append("search", debouncedSearchTerm);
        }
        const response = await api.get(
          `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/company/paginated?${params}`,
        );
        return response.data;
      },
      enabled: !!selectedOrgAccount?.accountId,
    });

  // Initialize local keywords from full list
  useEffect(() => {
    if (monitoringTopics?.company_keywords) {
      setLocalKeywords(monitoringTopics.company_keywords);
    }
  }, [monitoringTopics]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (updatedKeywords: string[]) => {
      if (!selectedOrgAccount?.accountId)
        throw new Error("No account selected");
      const response = await api.put(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/company`,
        {
          account_id: selectedOrgAccount.accountId,
          company_keywords: updatedKeywords,
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      queryClient.invalidateQueries({
        queryKey: ["company-keywords-paginated", selectedOrgAccount?.accountId],
      });
      toast({
        title: "Success",
        description: "Company keywords updated successfully",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to update company keywords",
        variant: "destructive",
      });
    },
  });

  const handleAddKeyword = () => {
    const trimmedKeyword = KeywordValidation.normalizeKeyword(newKeyword);

    // Validate keyword
    const validation = KeywordValidation.validateKeyword(trimmedKeyword);
    if (!validation.isValid) {
      toast({
        title: "Invalid keyword",
        description: validation.error,
        variant: "destructive",
      });
      return;
    }

    // Check for duplicates
    if (KeywordValidation.isDuplicate(trimmedKeyword, localKeywords)) {
      toast({
        title: "Duplicate keyword",
        description: "This keyword already exists",
        variant: "destructive",
      });
      return;
    }

    const updatedKeywords = [...localKeywords, trimmedKeyword];
    setLocalKeywords(updatedKeywords);
    setNewKeyword("");
    // Immediately save the new keyword
    updateMutation.mutate(updatedKeywords);
  };

  const handleRemoveKeyword = (keyword: string) => {
    const updatedKeywords = localKeywords.filter((k) => k !== keyword);
    setLocalKeywords(updatedKeywords);
    // Immediately save the removal
    updateMutation.mutate(updatedKeywords);
  };

  const totalPages = paginatedData?.total_pages || 0;

  if (isLoading) {
    return <CompanyKeywordsConfigurationSkeleton />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Company Keywords</CardTitle>
        <CardDescription>
          Add keywords that describe your company. These will be used to monitor
          news and social media mentions.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add keyword input */}
        <div className="flex gap-2">
          <Input
            placeholder="Add a keyword (e.g., your company name, product names)"
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
            disabled={!newKeyword.trim() || updateMutation.isPending}
            size="icon"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {/* Search and pagination controls */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search keywords..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={pageSize.toString()}
              onValueChange={(value) => {
                setPageSize(parseInt(value));
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[6.25rem]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
                <SelectItem value="200">200</SelectItem>
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">per page</span>
          </div>
        </div>

        {/* Total count */}
        {paginatedData && (
          <div className="text-sm text-muted-foreground">
            {paginatedData.total === 0 ? (
              searchTerm ? (
                "No keywords match your search"
              ) : (
                "No keywords added yet"
              )
            ) : (
              <>
                Showing {(page - 1) * pageSize + 1}-
                {Math.min(page * pageSize, paginatedData.total)} of{" "}
                {paginatedData.total} keywords
                {searchTerm && " (filtered)"}
              </>
            )}
          </div>
        )}

        {/* Keywords display */}
        <div className="flex flex-wrap gap-2 min-h-[6.25rem]">
          {paginatedData?.keywords.map((keyword) => (
            <Badge
              key={keyword}
              variant="secondary"
              className="pl-3 pr-1 py-1 text-sm"
            >
              <span className="max-w-[12.5rem] truncate">{keyword}</span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-1 h-4 w-4 p-0 hover:bg-transparent"
                onClick={() => handleRemoveKeyword(keyword)}
                disabled={updateMutation.isPending}
              >
                <X className="h-3 w-3" />
              </Button>
            </Badge>
          ))}
          {paginatedData?.keywords.length === 0 && !searchTerm && (
            <p className="text-sm text-muted-foreground">
              No keywords added yet
            </p>
          )}
        </div>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 pt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }

                return (
                  <Button
                    key={pageNum}
                    variant={page === pageNum ? "default" : "outline"}
                    size="sm"
                    onClick={() => setPage(pageNum)}
                    className="w-10"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Loading overlay */}
        {updateMutation.isPending && (
          <div className="absolute inset-0 bg-background/50 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

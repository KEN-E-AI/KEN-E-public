import { useState, useEffect } from "react";
import { Plus, X, Pencil, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  useMonitoringTopics,
  useAddCustomerProfileKeywords,
  useUpdateCustomerProfileKeywords,
} from "@/queries/monitoringTopics";
import type { CustomerProfileEntry } from "@/types/monitoring";

// Validation constants (matching backend validators)
const MAX_KEYWORDS = 20;
const MAX_KEYWORD_LENGTH = 50;
const MIN_KEYWORD_LENGTH = 2;

interface CustomerKeywordsSectionProps {
  customerProfileNodeId: string;
  hasEditAccess: boolean;
}

export function CustomerKeywordsSection({
  customerProfileNodeId,
  hasEditAccess,
}: CustomerKeywordsSectionProps) {
  const { selectedOrgAccount } = useAuth();
  const { toast } = useToast();
  const accountId = selectedOrgAccount?.accountId || null;

  const { data: monitoringTopics, isLoading: isLoadingTopics } =
    useMonitoringTopics(accountId);

  const addMutation = useAddCustomerProfileKeywords();
  const updateMutation = useUpdateCustomerProfileKeywords();

  const [isEditing, setIsEditing] = useState(false);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState("");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Find the customer profile entry in monitoring topics
  const customerProfileEntry = monitoringTopics?.customer_profile_entries?.find(
    (entry) => entry.node_id === customerProfileNodeId,
  );
  const customerProfileIndex =
    monitoringTopics?.customer_profile_entries?.findIndex(
      (entry) => entry.node_id === customerProfileNodeId,
    );

  useEffect(() => {
    // Only sync when customer profile changes, not on every render
    if (customerProfileEntry && !isEditing && !hasUnsavedChanges) {
      setKeywords(customerProfileEntry.keywords || []);
    }
    // Reset when switching to a different customer profile
    if (!customerProfileEntry && !isEditing) {
      setKeywords([]);
    }
  }, [customerProfileEntry?.node_id]); // Only when customer profile changes

  const handleAddKeyword = () => {
    const trimmedKeyword = keywordInput.trim().toLowerCase();

    // Validation
    if (!trimmedKeyword) {
      return;
    }

    if (trimmedKeyword.length < MIN_KEYWORD_LENGTH) {
      toast({
        title: "Keyword too short",
        description: `Keywords must be at least ${MIN_KEYWORD_LENGTH} characters`,
        variant: "destructive",
      });
      return;
    }

    if (trimmedKeyword.length > MAX_KEYWORD_LENGTH) {
      toast({
        title: "Keyword too long",
        description: `Keywords must be ${MAX_KEYWORD_LENGTH} characters or less`,
        variant: "destructive",
      });
      return;
    }

    if (keywords.length >= MAX_KEYWORDS) {
      toast({
        title: "Maximum keywords reached",
        description: `You can only have up to ${MAX_KEYWORDS} keywords`,
        variant: "destructive",
      });
      return;
    }

    if (keywords.includes(trimmedKeyword)) {
      toast({
        title: "Duplicate keyword",
        description: "This keyword already exists",
        variant: "destructive",
      });
      return;
    }

    setKeywords([...keywords, trimmedKeyword]);
    setKeywordInput("");
    setHasUnsavedChanges(true);
  };

  const handleRemoveKeyword = (keyword: string) => {
    setKeywords(keywords.filter((k) => k !== keyword));
    setHasUnsavedChanges(true);
  };

  const handleSave = async () => {
    if (!accountId) {
      toast({
        title: "Error",
        description: "Unable to update keywords",
        variant: "destructive",
      });
      return;
    }

    try {
      // Check if customer profile exists in monitoring topics
      const customerProfileExists = (customerProfileIndex ?? -1) >= 0;

      if (!customerProfileExists) {
        // Validate customerProfileNodeId is defined
        if (!customerProfileNodeId) {
          toast({
            title: "Error",
            description: "Invalid customer profile ID",
            variant: "destructive",
          });
          return;
        }

        // Create new customer profile entry
        await addMutation.mutateAsync({
          accountId,
          data: {
            node_id: customerProfileNodeId,
            keywords,
          },
        });
      } else {
        // Update existing entry
        await updateMutation.mutateAsync({
          accountId,
          customerProfileIndex,
          data: { keywords },
        });
      }

      toast({
        title: "Success",
        description: "Keywords updated successfully",
      });

      setIsEditing(false);
      setHasUnsavedChanges(false);
    } catch (error: any) {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to update keywords",
        variant: "destructive",
      });
    }
  };

  const handleCancel = () => {
    if (customerProfileEntry) {
      setKeywords(customerProfileEntry.keywords || []);
    }
    setKeywordInput("");
    setIsEditing(false);
    setHasUnsavedChanges(false);
  };

  if (isLoadingTopics) {
    return (
      <div className="border-t border-[var(--color-border-default)] pt-4">
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-disabled)]" />
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-[var(--color-border-default)] pt-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          News Monitoring Keywords
        </h3>
        {hasEditAccess && !isEditing && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsEditing(true)}
            className="h-7 w-7 p-0"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {isEditing ? (
        <div className="space-y-3">
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
              className="text-sm"
            />
            <Button
              type="button"
              onClick={handleAddKeyword}
              disabled={!keywordInput.trim()}
              size="icon"
              className="shrink-0"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {keywords.length > 0 && (
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
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancel}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={addMutation.isPending || updateMutation.isPending}
              className="flex-1"
            >
              {(addMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              )}
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div>
          {keywords.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {keywords.map((keyword) => (
                <Badge key={keyword} variant="secondary" className="text-sm">
                  {keyword}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {customerProfileEntry
                ? "No keywords configured for monitoring"
                : "This customer profile is not being monitored yet. Add keywords to start tracking"}
            </p>
          )}
        </div>
      )}

      {!isEditing && keywords.length === 0 && !customerProfileEntry && (
        <p className="text-xs text-muted-foreground mt-2">
          Keywords help track this customer profile in news and social media
        </p>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import { Loader2, Plus, AlertCircle } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import type { 
  MonitoringTopics, 
  ConceptOption, 
  CustomerKeywordConcept,
  AddCustomerConceptRequest 
} from "@/types/monitoring";
import api from "@/lib/api";
import { ConceptSearchDialog } from "./ConceptSearchDialog";
import { ConceptBadge, PlainKeywordBadge } from "./ConceptBadge";

export default function CustomerKeywordsConfiguration() {
  const { selectedOrgAccount } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyword, setNewKeyword] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [concepts, setConcepts] = useState<CustomerKeywordConcept[]>([]);
  const [showConceptDialog, setShowConceptDialog] = useState(false);
  const [pendingKeyword, setPendingKeyword] = useState("");
  const [disambiguatingKeyword, setDisambiguatingKeyword] = useState<string | null>(null);
  const [editingConcept, setEditingConcept] = useState<CustomerKeywordConcept | null>(null);

  // Fetch monitoring topics
  const { data: monitoringTopics, isLoading } =
    useQuery<MonitoringTopics | null>({
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

  // Initialize keywords and concepts when data loads
  useEffect(() => {
    if (monitoringTopics) {
      // Convert snake_case concepts from API to camelCase for frontend
      const convertedConcepts: CustomerKeywordConcept[] = (monitoringTopics.customer_concepts || []).map((c: any) => ({
        keyword: c.keyword,
        conceptId: c.concept_id,
        conceptType: c.concept_type,
        reference: {
          url: c.reference.url,
          title: c.reference.title,
          description: c.reference.description,
          sourceType: c.reference.source_type,
        },
        addedBy: c.added_by,
        addedAt: c.added_at,
      }));
      
      // Set legacy keywords that don't have concepts
      const conceptKeywords = convertedConcepts.map(c => c.keyword);
      const plainKeywords = monitoringTopics.customer_keywords.filter(
        k => !conceptKeywords.includes(k)
      );
      setKeywords(plainKeywords);
      
      // Set concepts with converted data
      setConcepts(convertedConcepts);
    }
  }, [monitoringTopics]);

  // Update mutation for legacy keywords
  const updateMutation = useMutation({
    mutationFn: async (updatedKeywords: string[]) => {
      if (!selectedOrgAccount?.accountId)
        throw new Error("No account selected");
      
      // Only send plain keywords to the update endpoint
      // Concept keywords are managed separately through add-concept/remove-concept endpoints
      // The backend will combine them when storing
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
      console.error("Failed to update customer keywords:", error);
      let errorMessage = "Failed to update customer keywords";
      
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          // Handle validation error array
          errorMessage = detail.map((e: any) => {
            if (typeof e === 'string') return e;
            return e.msg || e.message || JSON.stringify(e);
          }).join(', ');
        } else if (typeof detail === 'object') {
          // Handle single validation error object
          errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        }
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    },
  });

  // Add concept mutation
  const addConceptMutation = useMutation({
    mutationFn: async (request: any) => {  // Using any since we need snake_case conversion
      const response = await api.post(
        `/api/v1/monitoring-topics/${selectedOrgAccount?.accountId}/customers/add-concept`,
        request
      );
      return response.data;
    },
    onSuccess: (response: any) => {
      // Convert snake_case response to camelCase for frontend
      const data: CustomerKeywordConcept = {
        keyword: response.keyword,
        conceptId: response.concept_id,
        conceptType: response.concept_type,
        reference: {
          url: response.reference.url,
          title: response.reference.title,
          description: response.reference.description,
          sourceType: response.reference.source_type,
        },
        addedBy: response.added_by,
        addedAt: response.added_at,
      };
      
      // Add to local state
      setConcepts(prev => [...prev, data]);
      
      // Invalidate queries
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      
      toast({
        title: "Success",
        description: `Added "${data.keyword}" with concept disambiguation`,
      });
    },
    onError: (error: any) => {
      console.error("Failed to add concept:", error);
      let errorMessage = "Failed to add concept";
      
      if (error.response?.data?.detail) {
        // Handle both string and object error details
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          // Handle validation error array
          errorMessage = detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof detail === 'object') {
          // Handle single validation error object
          errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        }
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    },
  });

  // Remove concept mutation
  const removeConceptMutation = useMutation({
    mutationFn: async (conceptId: string) => {
      if (!selectedOrgAccount?.accountId) {
        throw new Error("No account selected");
      }
      
      const response = await api.delete(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/customers/concepts/${conceptId}`
      );
      return response.data;
    },
    onSuccess: (_, conceptId) => {
      // Update local state immediately
      setConcepts(prev => prev.filter(c => c.conceptId !== conceptId));
      
      // Then invalidate to sync with server
      queryClient.invalidateQueries({
        queryKey: ["monitoring-topics", selectedOrgAccount?.accountId],
      });
      
      toast({
        title: "Success",
        description: "Concept removed successfully",
      });
    },
    onError: (error: any) => {
      console.error("Failed to remove concept:", error);
      let errorMessage = "Failed to remove concept";
      
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        }
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    },
  });

  const handleAddKeyword = () => {
    const trimmedKeyword = newKeyword.trim();
    if (!trimmedKeyword) return;
    
    // Check if keyword already exists
    const keywordLower = trimmedKeyword.toLowerCase();
    const existsAsPlain = keywords.some(k => k.toLowerCase() === keywordLower);
    const existsAsConcept = concepts.some(c => c.keyword.toLowerCase() === keywordLower);
    
    if (existsAsPlain || existsAsConcept) {
      toast({
        title: "Keyword already exists",
        description: `"${trimmedKeyword}" is already in your list`,
        variant: "destructive",
      });
      return;
    }
    
    // Set pending keyword and show concept search dialog
    setPendingKeyword(trimmedKeyword);
    setShowConceptDialog(true);
    setNewKeyword("");
  };

  const handleConceptSelected = async (concept: ConceptOption) => {
    if (!selectedOrgAccount?.accountId) return;
    
    // If we're editing an existing concept, we need to remove the old one first
    if (editingConcept) {
      try {
        // Remove the old concept
        await removeConceptMutation.mutateAsync(editingConcept.conceptId);
        
        // Add the new concept with the same keyword
        const request = {
          account_id: selectedOrgAccount.accountId,
          keyword: editingConcept.keyword,
          concept_id: concept.id,
          concept_type: concept.type,
          reference: {
            url: concept.reference.url,
            title: concept.reference.title,
            description: concept.reference.description,
            source_type: concept.reference.sourceType,
          },
        };
        
        await addConceptMutation.mutateAsync(request);
        setEditingConcept(null);
      } catch (error) {
        console.error("Failed to update concept:", error);
      }
    } else {
      // Normal add flow
      const request = {
        account_id: selectedOrgAccount.accountId,
        keyword: pendingKeyword,
        concept_id: concept.id,
        concept_type: concept.type,
        reference: {
          url: concept.reference.url,
          title: concept.reference.title,
          description: concept.reference.description,
          source_type: concept.reference.sourceType,
        },
      };
      
      try {
        await addConceptMutation.mutateAsync(request);
        
        // If we're disambiguating an existing keyword, remove it from plain keywords
        if (disambiguatingKeyword) {
          const updatedKeywords = keywords.filter(k => k !== disambiguatingKeyword);
          setKeywords(updatedKeywords);
          setDisambiguatingKeyword(null);
        }
      } catch (error) {
        console.error("Failed to add concept:", error);
      }
    }
    
    setShowConceptDialog(false);
    setPendingKeyword("");
  };

  const handleSkipConcept = async () => {
    // If we're editing, just close the dialog
    if (editingConcept) {
      setShowConceptDialog(false);
      setPendingKeyword("");
      setEditingConcept(null);
      return;
    }
    
    // If we're disambiguating an existing keyword, just close the dialog
    if (disambiguatingKeyword) {
      setShowConceptDialog(false);
      setPendingKeyword("");
      setDisambiguatingKeyword(null);
      return;
    }
    
    // Otherwise, add as plain keyword without concept
    // Don't convert to lowercase - let the validator handle normalization
    const keywordToAdd = pendingKeyword.trim();
    const updatedKeywords = [...keywords, keywordToAdd];
    
    // Save immediately to backend
    try {
      await updateMutation.mutateAsync(updatedKeywords);
      setKeywords(updatedKeywords);
      setShowConceptDialog(false);
      setPendingKeyword("");
      
      toast({
        title: "Keyword added",
        description: `"${keywordToAdd}" added without concept disambiguation`,
      });
    } catch (error) {
      // Error is already handled by the mutation's onError
      console.error("Failed to add keyword:", error);
    }
  };

  const handleEditConcept = (concept: CustomerKeywordConcept) => {
    setEditingConcept(concept);
    setPendingKeyword(concept.keyword);
    setShowConceptDialog(true);
  };

  const handleRemoveKeyword = async (keyword: string) => {
    const updatedKeywords = keywords.filter((k) => k !== keyword);
    
    // Save immediately to backend
    try {
      await updateMutation.mutateAsync(updatedKeywords);
      setKeywords(updatedKeywords);
      
      toast({
        title: "Keyword removed",
        description: `"${keyword}" has been removed`,
      });
    } catch (error) {
      // Error is already handled by the mutation's onError
      console.error("Failed to remove keyword:", error);
    }
  };

  const handleRemoveConcept = (conceptId: string) => {
    removeConceptMutation.mutate(conceptId);
  };

  const handleDisambiguateKeyword = (keyword: string) => {
    setDisambiguatingKeyword(keyword);
    setPendingKeyword(keyword);
    setShowConceptDialog(true);
  };

  const handleSaveKeywords = () => {
    updateMutation.mutate(keywords);
  };

  const hasChanges =
    JSON.stringify(keywords) !==
    JSON.stringify(
      monitoringTopics?.customer_keywords.filter(
        k => !concepts.some(c => c.keyword === k)
      ) || []
    );

  const totalItems = keywords.length + concepts.length;

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
    <>
      <Card>
        <CardContent className="space-y-4 pt-6">
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

          {concepts.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-medium">With Context</h4>
                <Badge variant="outline" className="text-xs">
                  {concepts.length}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {concepts.map((concept) => (
                  <ConceptBadge
                    key={concept.conceptId}
                    concept={concept}
                    onRemove={() => handleRemoveConcept(concept.conceptId)}
                    onEdit={() => handleEditConcept(concept)}
                  />
                ))}
              </div>
            </div>
          )}

          {keywords.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-medium">Without Context</h4>
                <Badge variant="outline" className="text-xs">
                  {keywords.length}
                </Badge>
                <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
                <span className="text-xs text-muted-foreground">
                  May fetch irrelevant content
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {keywords.map((keyword) => (
                  <PlainKeywordBadge
                    key={keyword}
                    keyword={keyword}
                    onRemove={() => handleRemoveKeyword(keyword)}
                    onAddContext={() => handleDisambiguateKeyword(keyword)}
                  />
                ))}
              </div>
            </div>
          )}

          {totalItems === 0 && (
            <p className="text-sm text-muted-foreground">
              No keywords added yet. Add keywords to monitor customer-related content.
            </p>
          )}

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

      <ConceptSearchDialog
        term={pendingKeyword}
        isOpen={showConceptDialog}
        onClose={() => {
          setShowConceptDialog(false);
          setPendingKeyword("");
          setDisambiguatingKeyword(null);
          setEditingConcept(null);
        }}
        onSelect={handleConceptSelected}
        onSkip={handleSkipConcept}
      />
    </>
  );
}

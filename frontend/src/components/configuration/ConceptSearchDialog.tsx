import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ExternalLink, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConceptOption } from "@/types/monitoring";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface ConceptSearchDialogProps {
  term: string;
  isOpen: boolean;
  onClose: () => void;
  onSelect: (concept: ConceptOption) => void;
  onSkip: () => void;
}

export function ConceptSearchDialog({
  term,
  isOpen,
  onClose,
  onSelect,
  onSkip,
}: ConceptSearchDialogProps) {
  const { selectedOrgAccount } = useAuth();
  const [concepts, setConcepts] = useState<ConceptOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConcept, setSelectedConcept] = useState<ConceptOption | null>(
    null,
  );
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    if (isOpen && term) {
      searchConcepts(term);
      // Reset selection when dialog opens
      setSelectedConcept(null);
      setIsConfirming(false);
    }
  }, [isOpen, term]);

  const searchConcepts = async (searchTerm: string) => {
    if (!selectedOrgAccount?.accountId) {
      setError("No account selected");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.get(
        `/api/v1/monitoring-topics/${selectedOrgAccount.accountId}/customers/search-concepts`,
        { params: { term: searchTerm } },
      );

      console.log("API Response:", response.data);

      // Check if response.data is an array
      if (!Array.isArray(response.data)) {
        console.error("Unexpected response format:", response.data);
        setError("Unexpected response format from server");
        setConcepts([]);
        return;
      }

      // Convert snake_case to camelCase for frontend
      const convertedConcepts = response.data.map((concept: any) => ({
        id: concept.id,
        label: concept.label,
        type: concept.type,
        description: concept.description,
        reference: {
          url: concept.reference.url,
          title: concept.reference.title,
          description: concept.reference.description,
          sourceType: concept.reference.source_type,
        },
        confidenceScore: concept.confidence_score,
      }));

      setConcepts(convertedConcepts);
    } catch (err: any) {
      console.error("Failed to search concepts:", err);
      setError(err.response?.data?.detail || "Failed to search for concepts");
    } finally {
      setLoading(false);
    }
  };

  const getTypeColor = (type: string) => {
    const colors = {
      company: "bg-blue-100 text-blue-800 border-blue-300",
      location: "bg-green-100 text-green-800 border-green-300",
      person: "bg-purple-100 text-purple-800 border-purple-300",
      topic: "bg-yellow-100 text-yellow-800 border-yellow-300",
      product: "bg-pink-100 text-pink-800 border-pink-300",
      event: "bg-orange-100 text-orange-800 border-orange-300",
      other: "bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-[var(--color-border-default)]",
    };
    return colors[type as keyof typeof colors] || colors.other;
  };

  const getSourceIcon = (sourceType: string) => {
    switch (sourceType) {
      case "wikipedia":
        return "📖";
      case "wikidata":
        return "🔗";
      case "official_website":
        return "🌐";
      default:
        return "🔍";
    }
  };

  const getSourceLabel = (sourceType: string, url: string) => {
    switch (sourceType) {
      case "wikipedia":
        return "Wikipedia";
      case "wikidata":
        return "Wikidata";
      case "official_website":
        try {
          return new URL(url).hostname.replace("www.", "");
        } catch {
          return "Website";
        }
      default:
        return "Search result";
    }
  };

  const handleConceptClick = (concept: ConceptOption) => {
    setSelectedConcept(concept);
  };

  const handleConfirm = async () => {
    if (!selectedConcept) return;

    setIsConfirming(true);
    try {
      await onSelect(selectedConcept);
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>What does "{term}" refer to?</DialogTitle>
          <DialogDescription>
            Select the most relevant interpretation to ensure accurate
            monitoring. This helps avoid fetching irrelevant content.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-sm text-destructive">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => searchConcepts(term)}
                className="mt-4"
              >
                Try again
              </Button>
            </div>
          ) : concepts.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                No concept suggestions found for "{term}"
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                You can still add it as a plain keyword
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {concepts.map((concept) => (
                <button
                  key={concept.id}
                  onClick={() => handleConceptClick(concept)}
                  disabled={isConfirming}
                  className={cn(
                    "w-full text-left p-4 border rounded-lg transition-all group",
                    selectedConcept?.id === concept.id
                      ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                      : "hover:bg-accent",
                    isConfirming && "opacity-50 cursor-not-allowed",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">{concept.label}</span>
                        <Badge
                          variant="outline"
                          className={cn("text-xs", getTypeColor(concept.type))}
                        >
                          {concept.type}
                        </Badge>
                        {concept.confidenceScore > 0 && (
                          <span className="text-xs text-muted-foreground">
                            {Math.round(concept.confidenceScore * 100)}% match
                          </span>
                        )}
                        {selectedConcept?.id === concept.id && (
                          <Badge className="text-xs bg-primary">Selected</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {concept.description}
                      </p>
                      <a
                        href={concept.reference.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <span>
                          {getSourceIcon(concept.reference.sourceType)}
                        </span>
                        <span>
                          {getSourceLabel(
                            concept.reference.sourceType,
                            concept.reference.url,
                          )}
                        </span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          {selectedConcept ? (
            <>
              <Button
                variant="ghost"
                onClick={() => setSelectedConcept(null)}
                disabled={isConfirming}
              >
                Change Selection
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={isConfirming}
                className="min-w-[120px]"
              >
                {isConfirming ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  "Confirm Selection"
                )}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={onSkip}
                disabled={isConfirming}
              >
                Add without context
              </Button>
              <Button variant="ghost" onClick={onClose} disabled={isConfirming}>
                Cancel
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

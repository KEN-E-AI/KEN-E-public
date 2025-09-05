import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ExternalLink, X, Edit2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CustomerKeywordConcept } from "@/types/monitoring";

interface ConceptBadgeProps {
  concept: CustomerKeywordConcept;
  onRemove: () => void;
  onEdit?: () => void;
}

export function ConceptBadge({ concept, onRemove, onEdit }: ConceptBadgeProps) {
  const getTypeColor = (type: string) => {
    const colors = {
      company: "bg-blue-100 text-blue-800 hover:bg-blue-200",
      location: "bg-green-100 text-green-800 hover:bg-green-200",
      person: "bg-purple-100 text-purple-800 hover:bg-purple-200",
      topic: "bg-yellow-100 text-yellow-800 hover:bg-yellow-200",
      product: "bg-pink-100 text-pink-800 hover:bg-pink-200",
      event: "bg-orange-100 text-orange-800 hover:bg-orange-200",
      other: "bg-gray-100 text-gray-800 hover:bg-gray-200",
    };
    return colors[type as keyof typeof colors] || colors.other;
  };

  const getTypeIcon = (type: string) => {
    const icons = {
      company: "🏢",
      location: "📍",
      person: "👤",
      topic: "💡",
      product: "📦",
      event: "📅",
      other: "🏷️",
    };
    return icons[type as keyof typeof icons] || icons.other;
  };

  const getSourceLabel = (sourceType: string) => {
    switch (sourceType) {
      case "wikipedia":
        return "Wikipedia";
      case "wikidata":
        return "Wikidata";
      case "official_website":
        return "Official Website";
      case "gemini_search":
        return "AI Search";
      default:
        return "Source";
    }
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className={cn(
              "pl-3 pr-1 py-1.5 text-sm inline-flex items-center gap-1.5 transition-colors",
              getTypeColor(concept.conceptType),
            )}
          >
            <span className="text-base leading-none">
              {getTypeIcon(concept.conceptType)}
            </span>
            <span className="font-medium">{concept.keyword}</span>
            <a
              href={concept.reference.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-1 p-1 hover:bg-black/10 rounded transition-colors"
              onClick={(e) => e.stopPropagation()}
              aria-label="View reference"
            >
              <ExternalLink className="h-3 w-3" />
            </a>
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                className="ml-0.5 h-5 w-5 p-0 hover:bg-black/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit();
                }}
                aria-label="Edit concept"
              >
                <Edit2 className="h-3 w-3" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="ml-0.5 h-5 w-5 p-0 hover:bg-black/10"
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              aria-label="Remove keyword"
            >
              <X className="h-3 w-3" />
            </Button>
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <div className="space-y-2">
            <div>
              <p className="font-medium text-sm">{concept.reference.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {concept.reference.description}
              </p>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                Source: {getSourceLabel(concept.reference.sourceType)}
              </span>
              <Badge variant="outline" className="text-xs py-0 h-5">
                {concept.conceptType}
              </Badge>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface PlainKeywordBadgeProps {
  keyword: string;
  onRemove: () => void;
  onAddContext?: () => void;
}

export function PlainKeywordBadge({
  keyword,
  onRemove,
  onAddContext,
}: PlainKeywordBadgeProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className="pl-3 pr-1 py-1.5 text-sm inline-flex items-center gap-1.5"
          >
            <span className="font-medium">{keyword}</span>
            {onAddContext && (
              <Button
                variant="ghost"
                size="sm"
                className="ml-0.5 h-5 px-1.5 text-xs hover:bg-black/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onAddContext();
                }}
              >
                Add context
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="ml-0.5 h-5 w-5 p-0 hover:bg-black/10"
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              aria-label="Remove keyword"
            >
              <X className="h-3 w-3" />
            </Button>
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">
            Plain keyword without concept disambiguation
          </p>
          {onAddContext && (
            <p className="text-xs text-muted-foreground mt-1">
              Click "Add context" to disambiguate
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

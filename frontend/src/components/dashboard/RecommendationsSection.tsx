import { useState } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RecommendationItem {
  id: string;
  title: string;
  summary: string;
  detailed: string;
}

const recommendationItems: RecommendationItem[] = [
  {
    id: "1",
    title: "Reallocate display spend",
    summary:
      "Allocate 15% of display ad budget to offset for increased competition.",
    detailed: `To maintain competitive positioning and improve efficiency, we recommend:

1. Decrease spend by 12% on this campaign
2. Increase spend here and there

This reallocation will help offset increased competition costs while maintaining overall campaign effectiveness. Based on current market trends and competitor analysis, this adjustment should improve your cost per acquisition by approximately 8-12% over the next quarter.`,
  },
  {
    id: "2",
    title: "Do something else",
    summary: "Additional recommendation to optimize campaign performance.",
    detailed:
      "Further optimization opportunities include adjusting targeting parameters, updating creative assets, and refining audience segments to improve overall campaign efficiency and reach.",
  },
];

const RecommendationsSection = () => {
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  const toggleItem = (id: string) => {
    setExpandedItem(expandedItem === id ? null : id);
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] mb-6 border-b border-[var(--color-border-strong)] pb-2">
        Recommendations
      </h2>

      <div className="space-y-4">
        {recommendationItems.map((item) => (
          <div
            key={item.id}
            className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg overflow-hidden"
          >
            {/* Collapsed Header */}
            <button
              className="w-full px-6 py-4 text-left hover:bg-[var(--color-bg-secondary)] transition-colors"
              onClick={() => toggleItem(item.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="font-medium text-[var(--color-text-primary)] mb-1">
                    {item.title}
                  </h3>
                  <p className="text-sm text-[var(--color-text-tertiary)]">
                    {item.summary}
                  </p>
                </div>
                <div className="ml-4">
                  {expandedItem === item.id ? (
                    <ChevronUp className="h-5 w-5 text-[var(--color-text-disabled)]" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-[var(--color-text-disabled)]" />
                  )}
                </div>
              </div>
            </button>

            {/* Expanded Content */}
            {expandedItem === item.id && (
              <div className="px-6 pb-6 border-t border-[var(--color-border-subtle)]">
                <div className="pt-4">
                  {/* Detailed Description */}
                  <div className="mb-6">
                    <div className="prose prose-sm text-[var(--color-text-secondary)] max-w-none">
                      {item.detailed.split("\n").map((line, index) => (
                        <p key={index} className="mb-2">
                          {line}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecommendationsSection;

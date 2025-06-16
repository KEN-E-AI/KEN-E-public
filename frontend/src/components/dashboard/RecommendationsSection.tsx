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
      <h2 className="text-2xl font-semibold text-dashboard-gray-900 mb-6 border-b border-dashboard-gray-900 pb-2">
        Recommendations
      </h2>

      <div className="space-y-4">
        {recommendationItems.map((item) => (
          <div
            key={item.id}
            className="bg-white border border-dashboard-gray-200 rounded-lg overflow-hidden"
          >
            {/* Collapsed Header */}
            <button
              className="w-full px-6 py-4 text-left hover:bg-dashboard-gray-50 transition-colors"
              onClick={() => toggleItem(item.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="font-medium text-dashboard-gray-900 mb-1">
                    {item.title}
                  </h3>
                  <p className="text-sm text-dashboard-gray-600">
                    {item.summary}
                  </p>
                </div>
                <div className="ml-4">
                  {expandedItem === item.id ? (
                    <ChevronUp className="h-5 w-5 text-dashboard-gray-400" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-dashboard-gray-400" />
                  )}
                </div>
              </div>
            </button>

            {/* Expanded Content */}
            {expandedItem === item.id && (
              <div className="px-6 pb-6 border-t border-dashboard-gray-100">
                <div className="pt-4">
                  {/* Detailed Description */}
                  <div className="mb-6">
                    <div className="prose prose-sm text-dashboard-gray-700 max-w-none">
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

import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  Search,
  Filter,
  Lightbulb,
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowLeft,
  Trash2,
} from "lucide-react";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { 
  transformAPIInsightsToFrontend, 
  type APIInsightResponse,
  type FrontendInsight
} from "@/lib/insightsUtils";

// Keep the Insight type for compatibility, but rename it to match the frontend structure
type Insight = FrontendInsight;

const Insights = () => {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedImpact, setSelectedImpact] = useState<string>("all");
  const [selectedConfidence, setSelectedConfidence] = useState<string>("all");

  // Fetch insights from API
  useEffect(() => {
    const fetchInsights = async () => {
      if (!selectedOrgAccount) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        
        const response = await axios.get<APIInsightResponse>(
          `${import.meta.env.VITE_API_BASE_URL}/api/v1/insights/`,
          {
            params: {
              account_id: selectedOrgAccount.accountId,
            },
          }
        );

        const transformedInsights = transformAPIInsightsToFrontend(response.data);
        setInsights(transformedInsights);
      } catch (err) {
        console.error("Error fetching insights:", err);
        setError("Failed to load insights. Please try again.");
        setInsights([]); // Fallback to empty array on error
      } finally {
        setLoading(false);
      }
    };

    fetchInsights();
  }, [selectedOrgAccount]);

  // Delete insight function
  const handleDeleteInsight = async (insightId: string) => {
    if (!selectedOrgAccount) {
      alert("No account selected");
      return;
    }

    try {
      // Find the insight to get original API IDs
      const insightToDelete = insights.find(insight => insight.insight_id === insightId);
      if (!insightToDelete) {
        alert("Insight not found");
        return;
      }

      // Call the API to delete the insight
      await axios.delete(
        `${import.meta.env.VITE_API_BASE_URL}/api/v1/insights/`,
        {
          data: {
            account_id: selectedOrgAccount.accountId,
            activity_log_id: insightToDelete._originalData.activity_log_id,
            metric_id: insightToDelete._originalData.metric_id,
          },
        }
      );

      // Remove from local state on successful API deletion
      setInsights((prev) =>
        prev.filter((insight) => insight.insight_id !== insightId),
      );
      
      console.log("Insight deleted successfully:", insightId);
    } catch (err) {
      console.error("Error deleting insight:", err);
      alert("Failed to delete insight. Please try again.");
    }
  };

  // Get unique values for filters
  const categories = useMemo(() => {
    const uniqueCategories = [
      ...new Set(insights.map((insight) => insight.category)),
    ];
    return uniqueCategories;
  }, []);

  // Filter insights based on search and filter criteria
  const filteredInsights = useMemo(() => {
    return insights.filter((insight) => {
      const matchesSearch = insight.description
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
      const matchesCategory =
        selectedCategory === "all" || insight.category === selectedCategory;
      const matchesImpact =
        selectedImpact === "all" || insight.impact === selectedImpact;
      const matchesConfidence =
        selectedConfidence === "all" ||
        insight.confidence_level === selectedConfidence;

      return (
        matchesSearch && matchesCategory && matchesImpact && matchesConfidence
      );
    });
  }, [
    searchTerm,
    selectedCategory,
    selectedImpact,
    selectedConfidence,
    insights,
  ]);

  const getImpactIcon = (impact: string) => {
    switch (impact) {
      case "positive":
        return <TrendingUp className="h-4 w-4 text-green-600" />;
      case "negative":
        return <TrendingDown className="h-4 w-4 text-red-600" />;
      default:
        return <Minus className="h-4 w-4 text-gray-600" />;
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case "positive":
        return "bg-green-50 text-green-700 border-green-200";
      case "negative":
        return "bg-red-50 text-red-700 border-red-200";
      default:
        return "bg-gray-50 text-gray-700 border-gray-200";
    }
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case "high":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "medium":
        return "bg-yellow-50 text-yellow-700 border-yellow-200";
      case "low":
        return "bg-gray-50 text-gray-700 border-gray-200";
      default:
        return "bg-gray-50 text-gray-700 border-gray-200";
    }
  };

  const formatDateRange = (insight: Insight) => {
    const startDate = new Date(insight.date_range.start).toLocaleDateString();
    const endDate = new Date(insight.date_range.end).toLocaleDateString();
    return `${startDate} - ${endDate}`;
  };

  return (
    <Layout pageTitle="Insights">
      <div className="max-w-4xl mx-auto space-y-6 flex flex-col">
        {/* Back to Knowledge Link */}
        <div className="pt-2 mr-auto">
          <Button
            variant="ghost"
            onClick={() => navigate("/knowledge")}
            className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </Button>
        </div>

        {/* Search and Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search insights..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          <div className="flex gap-2">
            <Select
              value={selectedCategory}
              onValueChange={setSelectedCategory}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedImpact} onValueChange={setSelectedImpact}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Impact" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Impact</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
                <SelectItem value="neutral">Neutral</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={selectedConfidence}
              onValueChange={setSelectedConfidence}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Confidence" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Confidence</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="icon">
              <Filter className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Results Count */}
        {!loading && !error && selectedOrgAccount && (
          <div className="text-sm text-gray-600 mt-6 mr-auto">
            {filteredInsights.length} insight
            {filteredInsights.length !== 1 ? "s" : ""} found
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <Card>
            <CardContent className="text-center py-12">
              <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-gray-500">Loading insights...</p>
            </CardContent>
          </Card>
        ) : error ? (
          /* Error State */
          <Card>
            <CardContent className="text-center py-12">
              <div className="text-red-500 mb-4">
                <svg className="h-12 w-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Insights</h3>
              <p className="text-gray-500 mb-4">{error}</p>
              <Button onClick={() => window.location.reload()} variant="outline">
                Try Again
              </Button>
            </CardContent>
          </Card>
        ) : !selectedOrgAccount ? (
          /* No Account Selected */
          <Card>
            <CardContent className="text-center py-12">
              <Lightbulb className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Account Selected</h3>
              <p className="text-gray-500">Please select an organization and account to view insights.</p>
            </CardContent>
          </Card>
        ) : filteredInsights.length > 0 ? (
          <Accordion type="single" collapsible className="space-y-4">
            {filteredInsights.map((insight) => (
              <AccordionItem
                key={insight.insight_id}
                value={insight.insight_id}
                className="border rounded-lg shadow-sm"
              >
                <AccordionTrigger className="px-6 py-4 hover:no-underline">
                  <div className="flex items-start justify-between w-full text-left">
                    <div className="flex-1 mr-4">
                      <div className="font-medium text-gray-900 mb-2">
                        {insight.description}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-gray-500">
                        <div className="flex items-center gap-1">
                          <Calendar className="h-4 w-4" />
                          {formatDateRange(insight)}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={getImpactColor(insight.impact)}>
                            <div className="flex items-center gap-1">
                              {getImpactIcon(insight.impact)}
                              {insight.impact}
                            </div>
                          </Badge>
                          <Badge
                            className={getConfidenceColor(
                              insight.confidence_level,
                            )}
                          >
                            {insight.confidence_level} confidence
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-6 pb-6">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium text-gray-900">
                            Evidence
                          </h4>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete Insight
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>
                                  Delete Insight
                                </AlertDialogTitle>
                                <AlertDialogDescription>
                                  Are you sure you want to delete this insight?
                                  This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() =>
                                    handleDeleteInsight(insight.insight_id)
                                  }
                                  className="bg-red-600 hover:bg-red-700"
                                >
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-md">
                          <p className="text-sm text-gray-700 whitespace-pre-wrap">
                            {insight.evidence}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        ) : (
          <Card>
            <CardContent className="text-center py-12">
              <Lightbulb className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                No insights found
              </h3>
              <p className="text-gray-500">
                {searchTerm ||
                selectedCategory !== "all" ||
                selectedImpact !== "all" ||
                selectedConfidence !== "all"
                  ? "Try adjusting your search criteria or filters"
                  : "KEN-E will populate insights here as they are discovered"}
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Insights;

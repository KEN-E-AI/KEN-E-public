import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Globe, Plus, X, Save, Loader2, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import type { IndustryKeyword } from "@/types/admin.types";

// Common industries list - must match backend INDUSTRY_OPTIONS
const INDUSTRIES = [
  "Agriculture, Forestry, Fishing and Hunting",
  "Utilities",
  "Construction",
  "Manufacturing",
  "Wholesale Trade [B2B]",
  "Retail Trade",
  "Transportation and Warehousing",
  "Information",
  "Finance and Insurance",
  "Real Estate and Rental and Leasing",
  "Professional, Scientific, and Technical Services",
  "Management of Companies and Enterprises",
  "Administrative and Support and Waste Management and Remediation Services",
  "Educational Services",
  "Health Care and Social Assistance",
  "Arts, Entertainment, and Recreation",
  "Accommodation and Food Services",
  "Other Services (except Public Administration)",
  "Public Administration",
];

export const IndustryKeywordsSettings = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [industryKeywords, setIndustryKeywords] = useState<IndustryKeyword[]>(
    [],
  );
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [currentKeyword, setCurrentKeyword] = useState("");
  const [editingIndustry, setEditingIndustry] = useState<string | null>(null);
  const [editingKeywords, setEditingKeywords] = useState<string[]>([]);

  // Fetch industry keywords
  useEffect(() => {
    fetchIndustryKeywords();
  }, []);

  const fetchIndustryKeywords = async () => {
    try {
      setLoading(true);
      const response = await api.get("/api/v1/industry-keywords");
      setIndustryKeywords(response.data || []);
    } catch (error: any) {
      console.error("Failed to fetch industry keywords:", error);
      toast({
        title: "Error",
        description: "Failed to load industry keywords",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddKeyword = () => {
    if (
      currentKeyword.trim() &&
      !editingKeywords.includes(currentKeyword.trim())
    ) {
      setEditingKeywords([...editingKeywords, currentKeyword.trim()]);
      setCurrentKeyword("");
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    setEditingKeywords(editingKeywords.filter((k) => k !== keyword));
  };

  const handleStartEdit = (industry: string) => {
    const existing = industryKeywords.find((ik) => ik.industry === industry);
    setEditingIndustry(industry);
    setEditingKeywords(existing?.keywords || []);
    setSelectedIndustry(industry);
  };

  const handleCancelEdit = () => {
    setEditingIndustry(null);
    setEditingKeywords([]);
    setSelectedIndustry("");
    setCurrentKeyword("");
  };

  const handleSaveKeywords = async () => {
    if (!editingIndustry || editingKeywords.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select an industry and add at least one keyword",
        variant: "destructive",
      });
      return;
    }

    try {
      setSaving(true);
      await api.put(
        `/api/v1/industry-keywords/${editingIndustry}`,
        editingKeywords,
      );

      toast({
        title: "Success",
        description: `Keywords updated for ${editingIndustry}`,
      });

      // Refresh data
      await fetchIndustryKeywords();
      handleCancelEdit();
    } catch (error) {
      console.error("Failed to save industry keywords:", error);
      toast({
        title: "Error",
        description: "Failed to save industry keywords",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteIndustry = async (industry: string) => {
    try {
      await api.delete(`/api/v1/industry-keywords/${industry}`);
      toast({
        title: "Success",
        description: `Keywords removed for ${industry}`,
      });
      await fetchIndustryKeywords();
    } catch (error) {
      console.error("Failed to delete industry keywords:", error);
      toast({
        title: "Error",
        description: "Failed to delete industry keywords",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--color-text-disabled)]" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-brand-medium-blue" />
              <CardTitle>Industry Keywords</CardTitle>
            </div>
            {!editingIndustry && (
              <Button
                onClick={() => {
                  setEditingIndustry("new");
                  setEditingKeywords([]);
                }}
                size="sm"
              >
                <Plus className="h-4 w-4 mr-1" />
                Add Industry
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Edit/Add Form */}
        {editingIndustry && (
          <div className="border rounded-lg p-4 space-y-4 bg-[var(--color-bg-secondary)]">
            <div className="space-y-2">
              <Label htmlFor="industry-select">Industry</Label>
              <Select
                value={selectedIndustry}
                onValueChange={setSelectedIndustry}
                disabled={editingIndustry !== "new"}
              >
                <SelectTrigger id="industry-select">
                  <SelectValue placeholder="Select an industry" />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRIES.map((industry) => (
                    <SelectItem key={industry} value={industry}>
                      {industry}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="keyword-input">Keywords</Label>
              <div className="flex gap-2">
                <Input
                  id="keyword-input"
                  placeholder="Enter a keyword"
                  value={currentKeyword}
                  onChange={(e) => setCurrentKeyword(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddKeyword();
                    }
                  }}
                />
                <Button
                  type="button"
                  onClick={handleAddKeyword}
                  disabled={!currentKeyword.trim()}
                >
                  Add
                </Button>
              </div>

              {/* Keywords Display */}
              <div className="flex flex-wrap gap-2 pt-2">
                {editingKeywords.map((keyword) => (
                  <Badge key={keyword} variant="secondary" className="gap-1">
                    {keyword}
                    <button
                      onClick={() => handleRemoveKeyword(keyword)}
                      className="ml-1 hover:text-red-500"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={handleCancelEdit}>
                Cancel
              </Button>
              <Button
                onClick={handleSaveKeywords}
                disabled={
                  saving || !selectedIndustry || editingKeywords.length === 0
                }
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-1" />
                    Save
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Existing Industries List */}
        <div className="space-y-3">
          {industryKeywords.length === 0 && !editingIndustry ? (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              No industry keywords configured yet
            </div>
          ) : (
            industryKeywords.map((item) => (
              <div
                key={item.industry}
                className="border rounded-lg p-4 hover:bg-[var(--color-bg-secondary)] transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="font-medium text-[var(--color-text-primary)] mb-2">
                      {item.industry}
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {item.keywords.map((keyword) => (
                        <Badge key={keyword} variant="outline">
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-2">
                      Last updated:{" "}
                      {new Date(item.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleStartEdit(item.industry)}
                      disabled={editingIndustry !== null}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteIndustry(item.industry)}
                      disabled={editingIndustry !== null}
                      className="text-red-600 hover:text-red-700"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
};

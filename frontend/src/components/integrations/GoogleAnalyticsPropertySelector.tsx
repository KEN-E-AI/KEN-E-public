import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  AlertCircle,
  CheckCircle,
  Loader2,
  Search,
  Building,
  Globe,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import api from "@/lib/api";

interface GoogleAnalyticsProperty {
  property_id: string;
  display_name: string;
  account_id: string;
  account_display_name: string;
  time_zone?: string;
  industry_category?: string;
  create_time?: string;
}

interface GoogleAnalyticsPropertySelectorProps {
  accountId: string;
  onComplete?: (selectedProperties: GoogleAnalyticsProperty[]) => void;
  onSkip?: () => void;
  isAccountCreation?: boolean;
}

export const GoogleAnalyticsPropertySelector = ({
  accountId,
  onComplete,
  onSkip,
  isAccountCreation = false,
}: GoogleAnalyticsPropertySelectorProps) => {
  console.log(
    "[GoogleAnalyticsPropertySelector] Component mounted/rendered with props:",
    {
      accountId,
      onComplete: !!onComplete,
      onSkip: !!onSkip,
      isAccountCreation,
      timestamp: new Date().toISOString(),
    },
  );

  const [properties, setProperties] = useState<GoogleAnalyticsProperty[]>([]);
  const [selectedPropertyIds, setSelectedPropertyIds] = useState<Set<string>>(
    new Set(),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    fetchProperties();
  }, [accountId]);

  const fetchProperties = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.get(
        `/api/oauth/google-analytics/properties/${accountId}`,
      );
      console.log(
        "[GoogleAnalyticsPropertySelector] Fetched properties:",
        response.data,
      );

      const data = response.data;
      setProperties(data.properties || []);

      // Pre-select previously selected properties
      if (data.selected_property_ids && data.selected_property_ids.length > 0) {
        setSelectedPropertyIds(new Set(data.selected_property_ids));
      }
    } catch (error: any) {
      console.error(
        "[GoogleAnalyticsPropertySelector] Failed to fetch properties:",
        {
          error,
          response: error.response,
          status: error.response?.status,
          data: error.response?.data,
          accountId,
        },
      );
      setError(
        error.response?.data?.detail ||
          "Failed to fetch Google Analytics properties. Please ensure you've connected your Google account.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handlePropertyToggle = (propertyId: string) => {
    const newSelection = new Set(selectedPropertyIds);
    if (newSelection.has(propertyId)) {
      newSelection.delete(propertyId);
    } else {
      newSelection.add(propertyId);
    }
    setSelectedPropertyIds(newSelection);
  };

  const handleSelectAll = () => {
    if (selectedPropertyIds.size === filteredProperties.length) {
      // Deselect all
      setSelectedPropertyIds(new Set());
    } else {
      // Select all visible
      const allIds = new Set(filteredProperties.map((p) => p.property_id));
      setSelectedPropertyIds(allIds);
    }
  };

  const handleSave = async () => {
    if (selectedPropertyIds.size === 0) {
      toast({
        title: "No Properties Selected",
        description: "Please select at least one property to continue.",
        variant: "destructive",
      });
      return;
    }

    setIsSaving(true);
    try {
      const selectedProperties = properties.filter((p) =>
        selectedPropertyIds.has(p.property_id),
      );

      await api.post(`/api/oauth/google-analytics/properties/${accountId}`, {
        property_ids: Array.from(selectedPropertyIds),
        properties: selectedProperties,
      });

      toast({
        title: "Success",
        description: `${selectedPropertyIds.size} ${
          selectedPropertyIds.size === 1 ? "property" : "properties"
        } selected successfully.`,
      });

      if (onComplete) {
        onComplete(selectedProperties);
      }
    } catch (error: any) {
      toast({
        title: "Save Failed",
        description:
          error.response?.data?.detail || "Failed to save property selection",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Calculate filtered properties and grouped properties BEFORE any conditional returns
  // This ensures hooks are always called in the same order
  const filteredProperties = properties.filter(
    (property) =>
      property.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      property.account_display_name
        .toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      property.property_id.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Group properties by account
  const propertiesByAccount = filteredProperties.reduce(
    (acc, property) => {
      const accountName = property.account_display_name;
      if (!acc[accountName]) {
        acc[accountName] = [];
      }
      acc[accountName].push(property);
      return acc;
    },
    {} as Record<string, GoogleAnalyticsProperty[]>,
  );

  // Now we can have conditional returns since all hooks have been called
  if (isLoading) {
    console.log("[GoogleAnalyticsPropertySelector] Rendering loading state");
    return (
      <Card className="w-full max-w-4xl mx-auto bg-white relative z-[10000]">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-dashboard-gray-500" />
          <span className="ml-2">Loading Google Analytics properties...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <div className="mt-4 flex gap-2">
            <Button onClick={fetchProperties} variant="outline">
              Retry
            </Button>
            {onSkip && (
              <Button onClick={onSkip} variant="ghost">
                Skip
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (properties.length === 0) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="py-8">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>No Properties Found</AlertTitle>
            <AlertDescription>
              No Google Analytics properties were found for your account. Please
              ensure you have access to at least one GA4 property.
            </AlertDescription>
          </Alert>
          {onSkip && (
            <Button onClick={onSkip} className="mt-4" variant="outline">
              Continue Without Properties
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  console.log(
    "[GoogleAnalyticsPropertySelector] Rendering main UI with",
    properties.length,
    "properties",
  );
  return (
    <Card className="w-full max-w-4xl mx-auto bg-white relative z-[10000]">
      <CardHeader>
        <CardTitle>Select Google Analytics Properties</CardTitle>
        <CardDescription>
          Choose which Google Analytics properties KEN-E should have access to.
          {isAccountCreation &&
            " You can modify this selection later in account settings."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search and Actions Bar */}
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-dashboard-gray-400 h-4 w-4" />
            <Input
              placeholder="Search properties..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button
            variant="outline"
            onClick={handleSelectAll}
            disabled={filteredProperties.length === 0}
          >
            {selectedPropertyIds.size === filteredProperties.length &&
            filteredProperties.length > 0
              ? "Deselect All"
              : "Select All"}
          </Button>
        </div>

        {/* Selected Count */}
        {selectedPropertyIds.size > 0 && (
          <Alert className="border-green-500">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription>
              {selectedPropertyIds.size}{" "}
              {selectedPropertyIds.size === 1 ? "property" : "properties"}{" "}
              selected
            </AlertDescription>
          </Alert>
        )}

        {/* Properties List */}
        <ScrollArea className="h-[400px] border rounded-lg p-4">
          {Object.entries(propertiesByAccount).map(
            ([accountName, accountProperties]) => (
              <div key={accountName} className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Building className="h-4 w-4 text-dashboard-gray-500" />
                  <h4 className="font-medium text-sm">{accountName}</h4>
                  <Badge variant="secondary" className="text-xs">
                    {accountProperties.length}{" "}
                    {accountProperties.length === 1 ? "property" : "properties"}
                  </Badge>
                </div>
                <div className="space-y-2 ml-6">
                  {accountProperties.map((property) => (
                    <div
                      key={property.property_id}
                      className="flex items-start space-x-3 p-3 rounded-lg hover:bg-dashboard-gray-50 transition-colors"
                    >
                      <Checkbox
                        id={property.property_id}
                        checked={selectedPropertyIds.has(property.property_id)}
                        onCheckedChange={() =>
                          handlePropertyToggle(property.property_id)
                        }
                        className="mt-1"
                      />
                      <label
                        htmlFor={property.property_id}
                        className="flex-1 cursor-pointer"
                      >
                        <div className="flex items-center gap-2">
                          <Globe className="h-3 w-3 text-dashboard-gray-400" />
                          <span className="font-medium text-sm">
                            {property.display_name}
                          </span>
                        </div>
                        <div className="text-xs text-dashboard-gray-500 mt-1">
                          ID: {property.property_id}
                        </div>
                        {property.time_zone && (
                          <div className="text-xs text-dashboard-gray-400 mt-1">
                            Timezone: {property.time_zone}
                          </div>
                        )}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            ),
          )}
        </ScrollArea>

        {/* Action Buttons */}
        <div className="flex justify-between">
          {onSkip && (
            <Button onClick={onSkip} variant="ghost">
              Skip for Now
            </Button>
          )}
          <div className="flex gap-2 ml-auto">
            <Button
              onClick={handleSave}
              disabled={selectedPropertyIds.size === 0 || isSaving}
            >
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  Save Selection
                  {selectedPropertyIds.size > 0 && (
                    <Badge variant="secondary" className="ml-2">
                      {selectedPropertyIds.size}
                    </Badge>
                  )}
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

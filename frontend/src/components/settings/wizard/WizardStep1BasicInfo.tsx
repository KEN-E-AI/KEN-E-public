import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { FileUpload } from "@/components/ui/file-upload";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  DollarSign,
  FileText,
  Sparkles,
  Info,
  Plus,
  X,
  AlertCircle,
} from "lucide-react";
import { AccountCreationData } from "../AccountCreationWizard";
import { IndustrySelectDropdownAPI as IndustrySelect } from "@/components/ui/industry-select-dropdown-api";
import {
  templateService,
  type IndustryTemplate,
} from "@/services/templateService";
import { TIMEZONE_OPTIONS } from "@/data/organizationTypes";

// Region options (from AccountsManagement.tsx)
const REGION_OPTIONS = [
  { value: "Global", label: "Global" },
  { value: "NA", label: "NA: North America" },
  { value: "JAPAC", label: "JAPAC: Japan and Asia Pacific" },
  { value: "EMEA", label: "EMEA: Europe, the Middle East and Africa" },
  { value: "LAC", label: "LAC: Latin America and the Caribbean" },
  { value: "AE", label: "AE: United Arab Emirates" },
  { value: "AR", label: "AR: Argentina" },
  { value: "AT", label: "AT: Austria" },
  { value: "AU", label: "AU: Australia" },
  { value: "BE", label: "BE: Belgium" },
  { value: "BR", label: "BR: Brazil" },
  { value: "CA", label: "CA: Canada" },
  { value: "CH", label: "CH: Switzerland" },
  { value: "CL", label: "CL: Chile" },
  { value: "CN", label: "CN: China" },
  { value: "CO", label: "CO: Colombia" },
  { value: "CZ", label: "CZ: Czechia" },
  { value: "DE", label: "DE: Germany" },
  { value: "DK", label: "DK: Denmark" },
  { value: "DZ", label: "DZ: Algeria" },
  { value: "EC", label: "EC: Ecuador" },
  { value: "EE", label: "EE: Estonia" },
  { value: "EG", label: "EG: Egypt" },
  { value: "ES", label: "ES: Spain" },
  { value: "FI", label: "FI: Finland" },
  { value: "FR", label: "FR: France" },
  { value: "GB", label: "GB: United Kingdom" },
  { value: "GR", label: "GR: Greece" },
  { value: "HK", label: "HK: Hong Kong" },
  { value: "HU", label: "HU: Hungary" },
  { value: "ID", label: "ID: Indonesia" },
  { value: "IE", label: "IE: Ireland" },
  { value: "IL", label: "IL: Israel" },
  { value: "IN", label: "IN: India" },
  { value: "IR", label: "IR: Iran" },
  { value: "IT", label: "IT: Italy" },
  { value: "JP", label: "JP: Japan" },
  { value: "KR", label: "KR: South Korea" },
  { value: "LV", label: "LV: Latvia" },
  { value: "MA", label: "MA: Morocco" },
  { value: "MX", label: "MX: Mexico" },
  { value: "MY", label: "MY: Malaysia" },
  { value: "NG", label: "NG: Nigeria" },
  { value: "NL", label: "NL: Netherlands" },
  { value: "NO", label: "NO: Norway" },
  { value: "NZ", label: "NZ: New Zealand" },
  { value: "PE", label: "PE: Peru" },
  { value: "PH", label: "PH: Philippines" },
  { value: "PK", label: "PK: Pakistan" },
  { value: "PL", label: "PL: Poland" },
  { value: "PT", label: "PT: Portugal" },
  { value: "RO", label: "RO: Romania" },
  { value: "RS", label: "RS: Serbia" },
  { value: "RU", label: "RU: Russia" },
  { value: "SA", label: "SA: Saudi Arabia" },
  { value: "SE", label: "SE: Sweden" },
  { value: "SG", label: "SG: Singapore" },
  { value: "SI", label: "SI: Slovenia" },
  { value: "SK", label: "SK: Slovakia" },
  { value: "TH", label: "TH: Thailand" },
  { value: "TR", label: "TR: Turkey" },
  { value: "TW", label: "TW: Taiwan" },
  { value: "UA", label: "UA: Ukraine" },
  { value: "US", label: "US: United States" },
  { value: "VE", label: "VE: Venezuela" },
  { value: "VN", label: "VN: Vietnam" },
  { value: "ZA", label: "ZA: South Africa" },
];

interface WizardStep1BasicInfoProps {
  formData: AccountCreationData;
  // The component calls setFormData with both direct values and updater
  // functions (see industry-template loader below), so the prop accepts
  // React's full SetStateAction shape.
  setFormData: React.Dispatch<React.SetStateAction<AccountCreationData>>;
  onTemplateLoad?: (template: IndustryTemplate | null) => void;
}

export const WizardStep1BasicInfo = ({
  formData,
  setFormData,
  onTemplateLoad,
}: WizardStep1BasicInfoProps) => {
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [loadedTemplate, setLoadedTemplate] = useState<IndustryTemplate | null>(
    null,
  );
  const [regionSearchTerm, setRegionSearchTerm] = useState("");

  const handleIndustryChange = async (industry: string) => {
    setFormData({ ...formData, industry });

    // Automatically load template for selected industry
    if (industry) {
      setLoadingTemplate(true);
      try {
        const template = await templateService.getTemplateByIndustry(industry);
        setLoadedTemplate(template);

        if (template) {
          setFormData((prev) => ({
            ...prev,
            industry,
            template_id: template.id,
            // Use defaults since recommendedSettings has been removed
            timezone: "America/New_York",
            data_region: "US",
            // Will be used in later steps
            objectives: template.defaultObjectives || [],
            kpis: template.defaultKPIs || [],
            // Only set template values if user hasn't made selections yet
            marketing_channels:
              prev.marketing_channels.length > 0
                ? prev.marketing_channels
                : template.marketingChannels || [],
            product_integrations:
              prev.product_integrations.length > 0
                ? prev.product_integrations
                : template.productIntegrations || [],
          }));

          if (onTemplateLoad) {
            onTemplateLoad(template);
          }
        }
      } catch (error) {
        console.error("Failed to load template for industry:", industry, error);
        setLoadedTemplate(null);
        if (onTemplateLoad) {
          onTemplateLoad(null);
        }
      } finally {
        setLoadingTemplate(false);
      }
    }
  };

  // Website management functions
  const addWebsiteField = () => {
    setFormData({
      ...formData,
      websites: [...formData.websites, ""],
    });
  };

  const removeWebsiteField = (index: number) => {
    const newWebsites = formData.websites.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      websites: newWebsites.length > 0 ? newWebsites : [""],
    });
  };

  const updateWebsiteField = (index: number, value: string) => {
    const newWebsites = [...formData.websites];
    newWebsites[index] = value;
    setFormData({
      ...formData,
      websites: newWebsites,
    });
  };

  // Region management functions
  const toggleRegion = (regionValue: string) => {
    const currentRegions = formData.region;
    const newRegions = currentRegions.includes(regionValue)
      ? currentRegions.filter((r) => r !== regionValue)
      : [...currentRegions, regionValue];

    setFormData({
      ...formData,
      region: newRegions,
    });
  };

  // Filter and organize regions: selected first, then filtered by search
  const getOrganizedRegions = () => {
    const filteredRegions = REGION_OPTIONS.filter((option) =>
      option.label.toLowerCase().includes(regionSearchTerm.toLowerCase()),
    );

    // Separate selected and unselected regions
    const selectedRegions = filteredRegions.filter((option) =>
      formData.region.includes(option.value),
    );
    const unselectedRegions = filteredRegions.filter(
      (option) => !formData.region.includes(option.value),
    );

    // Return selected regions first, then unselected
    return [...selectedRegions, ...unselectedRegions];
  };
  return (
    <TooltipProvider>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Basic Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <Label htmlFor="account_name">Account Name *</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                </TooltipTrigger>
                <TooltipContent className="max-w-md">
                  <p>
                    A friendly name for the account. If you have different types
                    of customers who each require a unique strategy, you should
                    consider creating multiple accounts (example: 'Company B2B
                    Account', and 'Company B2C Account').
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="account_name"
              value={formData.account_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  account_name: e.target.value,
                })
              }
              placeholder="Company B2B Account"
              className="mt-1"
            />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <Label htmlFor="industry">Industry *</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                </TooltipTrigger>
                <TooltipContent className="max-w-md">
                  <p>
                    The industry you choose will help KEN-E understand your
                    customers, your competitors, and your business objectives.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <IndustrySelect
              value={formData.industry}
              onValueChange={handleIndustryChange}
              className="mt-1"
            />
            {loadingTemplate && (
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                Loading industry-specific recommendations...
              </p>
            )}
          </div>

          {/* Alert for website/document requirement */}
          {formData.websites.every((w) => w.trim() === "") &&
            formData.business_strategy_documents.length === 0 && (
              <Alert className="border-orange-200 bg-orange-50">
                <AlertCircle className="h-4 w-4 text-orange-600" />
                <AlertDescription className="text-sm">
                  <strong>Required:</strong> Please provide at least one website
                  URL below OR upload at least one business document in the
                  section below.
                </AlertDescription>
              </Alert>
            )}

          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label>Websites</Label>
                <Badge variant="outline" className="text-xs">
                  {formData.business_strategy_documents.length > 0
                    ? "Optional"
                    : "Required"}
                </Badge>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-md">
                    <p>
                      List all of your websites. KEN-E will study these to
                      understand your business and products/services. You must
                      provide either at least one website or upload at least one
                      business document.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addWebsiteField}
                className="h-8 w-8 p-0"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-2 mt-1">
              {formData.websites.map((website, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    value={website}
                    onChange={(e) => updateWebsiteField(index, e.target.value)}
                    placeholder="https://example.com"
                    type="url"
                    className="flex-1"
                  />
                  {formData.websites.length > 1 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => removeWebsiteField(index)}
                      className="h-10 w-10 p-0 text-red-500 hover:text-red-700"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <Label htmlFor="estimated_annual_ad_budget">
                <DollarSign className="inline h-4 w-4 mr-1" />
                Estimated Annual Ad Budget (USD)
              </Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                </TooltipTrigger>
                <TooltipContent className="max-w-md">
                  <p>
                    This helps KEN-E provide better budget optimization
                    recommendations
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="estimated_annual_ad_budget"
              type="number"
              min="0"
              step="1000"
              value={formData.estimated_annual_ad_budget || ""}
              onChange={(e) => {
                const value = e.target.value;
                setFormData({
                  ...formData,
                  estimated_annual_ad_budget: value
                    ? parseInt(value, 10)
                    : null,
                });
              }}
              placeholder="e.g., 100000"
              className="mt-1"
            />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <Label>Customer Region *</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                </TooltipTrigger>
                <TooltipContent className="max-w-md">
                  <p>
                    Select all regions where your target customers live. This
                    will be used to understand how regional holidays influence
                    your business metrics.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  className="justify-between mt-1"
                >
                  {formData.region.length === 0
                    ? "Select regions..."
                    : `${formData.region.length} region${
                        formData.region.length === 1 ? "" : "s"
                      } selected`}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-full p-0" align="start">
                <div className="p-3 border-b">
                  <Input
                    placeholder="Search regions..."
                    value={regionSearchTerm}
                    onChange={(e) => setRegionSearchTerm(e.target.value)}
                    className="h-8"
                  />
                </div>
                <div className="max-h-64 overflow-y-auto p-2 space-y-1">
                  {getOrganizedRegions().map((option) => {
                    const isSelected = formData.region.includes(option.value);
                    return (
                      <div
                        key={option.value}
                        className={`flex items-center space-x-2 p-2 hover:bg-[var(--color-bg-secondary)] rounded ${
                          isSelected ? "bg-blue-50 border border-blue-200" : ""
                        }`}
                      >
                        <Checkbox
                          id={`region-${option.value}`}
                          checked={isSelected}
                          onCheckedChange={() => toggleRegion(option.value)}
                        />
                        <Label
                          htmlFor={`region-${option.value}`}
                          className={`flex-1 text-sm cursor-pointer ${
                            isSelected ? "font-medium text-blue-700" : ""
                          }`}
                        >
                          {option.label}
                        </Label>
                      </div>
                    );
                  })}
                  {getOrganizedRegions().length === 0 && (
                    <div className="p-2 text-center text-sm text-[var(--color-text-tertiary)]">
                      No regions found matching "{regionSearchTerm}"
                    </div>
                  )}
                </div>
              </PopoverContent>
            </Popover>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <Label htmlFor="data-region">Data Region *</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-[var(--color-text-disabled)]" />
                </TooltipTrigger>
                <TooltipContent className="max-w-md">
                  <p>
                    Choose a location to store your data. Once your account is
                    created you cannot change this setting.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Select
              value={formData.data_region}
              onValueChange={(value) =>
                setFormData({ ...formData, data_region: value })
              }
            >
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select data region..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="US">United States</SelectItem>
                <SelectItem value="EU">Europe</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="timezone">Timezone *</Label>
            <Select
              value={formData.timezone}
              onValueChange={(value) =>
                setFormData({ ...formData, timezone: value })
              }
            >
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEZONE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Business Strategy Documents
            <Badge variant="outline" className="text-xs">
              {formData.websites.some((w) => w.trim() !== "")
                ? "Optional"
                : "Required"}
            </Badge>
          </CardTitle>
          <div className="text-sm text-[var(--color-text-tertiary)]">
            <p className="mb-2">
              Upload documents to help KEN-E understand your business,
              competitors and customers.
            </p>
            <p className="font-medium text-[var(--color-text-secondary)]">
              Examples:
            </p>
            <ul className="list-disc list-inside ml-2 mb-3 space-y-1">
              <li>Business plan</li>
              <li>Competitive analysis</li>
              <li>Marketing strategy</li>
              <li>Customer profiles</li>
              <li>Brand guidelines</li>
              <li>Product catalogs</li>
              <li>Annual reports</li>
            </ul>
          </div>
        </CardHeader>
        <CardContent>
          <FileUpload
            files={formData.business_strategy_documents}
            onFilesChange={(files) =>
              setFormData({
                ...formData,
                business_strategy_documents: files,
              })
            }
            accept={[
              ".pdf",
              ".xlsx",
              ".docx",
              ".pptx",
              ".txt",
              ".png",
              ".jpg",
              ".jpeg",
            ]}
            multiple={true}
            maxSize={25 * 1024 * 1024} // 25MB
            maxTotalSize={100 * 1024 * 1024} // 100MB
            maxFiles={10}
          />
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

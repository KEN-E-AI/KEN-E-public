import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sparkles, CheckCircle } from "lucide-react";
import {
  TEMPLATE_CATEGORIES,
  getTemplatesByCategory,
  type AccountTemplate,
} from "@/data/accountTemplates";
import { AccountCreationData } from "../AccountCreationWizard";

interface WizardStep2TemplateSelectionProps {
  formData: AccountCreationData;
  selectedCategory: string;
  setSelectedCategory: (category: string) => void;
  onTemplateSelect: (template: AccountTemplate) => void;
}

export const WizardStep2TemplateSelection = ({
  formData,
  selectedCategory,
  setSelectedCategory,
  onTemplateSelect,
}: WizardStep2TemplateSelectionProps) => {
  const filteredTemplates = getTemplatesByCategory(selectedCategory);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          Choose Template
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Template Categories */}
        <div className="flex flex-wrap gap-2 mb-6">
          {TEMPLATE_CATEGORIES.map((category) => (
            <Button
              key={category}
              type="button"
              variant={selectedCategory === category ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(category)}
            >
              {category}
            </Button>
          ))}
        </div>

        {/* Template Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredTemplates.map((template) => {
            const Icon = template.icon;
            const isSelected = formData.template_id === template.id;

            return (
              <Card
                key={template.id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  isSelected ? "ring-2 ring-blue-500 bg-blue-50" : ""
                }`}
                onClick={() => onTemplateSelect(template)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Icon className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{template.name}</h3>
                      <Badge variant="secondary" className="text-xs">
                        {template.category}
                      </Badge>
                    </div>
                    {isSelected && (
                      <CheckCircle className="h-5 w-5 text-blue-600 ml-auto" />
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-dashboard-gray-600 mb-3">
                    {template.description}
                  </p>
                  <div className="text-xs text-dashboard-gray-500">
                    {template.defaultObjectives.length} objectives •{" "}
                    {template.defaultChannels.length} channels
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

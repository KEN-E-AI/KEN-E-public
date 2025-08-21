import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Target } from "lucide-react";
import { type IndustryTemplate } from "@/services/templateService";
import { AccountCreationData } from "../AccountCreationWizard";

interface WizardStep4ConfigurationProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate: IndustryTemplate;
}

export const WizardStep4Configuration = ({
  formData,
  setFormData,
  selectedTemplate,
}: WizardStep4ConfigurationProps) => {
  const handleObjectiveToggle = (objective: string, checked: boolean) => {
    if (checked) {
      setFormData({
        ...formData,
        objectives: [...formData.objectives, objective],
      });
    } else {
      setFormData({
        ...formData,
        objectives: formData.objectives.filter((o) => o !== objective),
      });
    }
  };

  const handleKPIToggle = (kpi: string, checked: boolean) => {
    if (checked) {
      setFormData({
        ...formData,
        kpis: [...formData.kpis, kpi],
      });
    } else {
      setFormData({
        ...formData,
        kpis: formData.kpis.filter((k) => k !== kpi),
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5" />
          Configuration
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Objectives */}
          <div>
            <Label className="text-base font-medium mb-3 block">
              Objectives
            </Label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {selectedTemplate.defaultObjectives.map((objective, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <Checkbox
                    id={`objective-${index}`}
                    checked={formData.objectives.includes(objective)}
                    onCheckedChange={(checked) =>
                      handleObjectiveToggle(objective, checked as boolean)
                    }
                  />
                  <Label htmlFor={`objective-${index}`} className="text-sm">
                    {objective}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* KPIs */}
          <div>
            <Label className="text-base font-medium mb-3 block">
              Key Performance Indicators
            </Label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {selectedTemplate.defaultKPIs.map((kpi, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <Checkbox
                    id={`kpi-${index}`}
                    checked={formData.kpis.includes(kpi)}
                    onCheckedChange={(checked) =>
                      handleKPIToggle(kpi, checked as boolean)
                    }
                  />
                  <Label htmlFor={`kpi-${index}`} className="text-sm">
                    {kpi}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

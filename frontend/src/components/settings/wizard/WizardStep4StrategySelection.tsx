import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Info, Plus, X } from "lucide-react";
import { useState } from "react";
import {
  VALID_STRATEGY_TYPES,
  STRATEGY_LABELS,
  STRATEGY_DESCRIPTIONS,
  DEFAULT_PRODUCT_CATEGORIES,
  type StrategyType,
} from "@/constants/strategies";

export interface WizardStep4StrategySelectionProps {
  enabled_strategies: string[];
  override_product_categories: string[];
  dry_run?: boolean;
  onUpdate: (
    data: Partial<{
      enabled_strategies: string[];
      override_product_categories: string[];
      dry_run?: boolean;
    }>,
  ) => void;
}

export const WizardStep4StrategySelection = ({
  enabled_strategies,
  override_product_categories,
  dry_run = false,
  onUpdate,
}: WizardStep4StrategySelectionProps) => {
  const [newCategory, setNewCategory] = useState("");

  const handleStrategyToggle = (strategy: StrategyType) => {
    const updated = enabled_strategies.includes(strategy)
      ? enabled_strategies.filter((s) => s !== strategy)
      : [...enabled_strategies, strategy];
    onUpdate({ enabled_strategies: updated });
  };

  const handleAddCategory = () => {
    if (
      newCategory.trim() &&
      !override_product_categories.includes(newCategory.trim())
    ) {
      onUpdate({
        override_product_categories: [
          ...override_product_categories,
          newCategory.trim(),
        ],
      });
      setNewCategory("");
    }
  };

  const handleRemoveCategory = (category: string) => {
    onUpdate({
      override_product_categories: override_product_categories.filter(
        (c) => c !== category,
      ),
    });
  };

  const handleUseDefaults = () => {
    onUpdate({ override_product_categories: [...DEFAULT_PRODUCT_CATEGORIES] });
  };

  const isMarketingEnabled = enabled_strategies.includes("marketing_strategy");
  const isBusinessEnabled = enabled_strategies.includes("business_strategy");
  const showCategoryInput = isMarketingEnabled && !isBusinessEnabled;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-2">Strategy Selection</h3>
        <p className="text-sm text-muted-foreground">
          Select which marketing strategies to generate for this account. All
          strategies are selected by default.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Available Strategies</CardTitle>
          <CardDescription>
            Choose which strategy documents to generate during account setup
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {VALID_STRATEGY_TYPES.map((strategy) => (
            <div
              key={strategy}
              className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors"
            >
              <Checkbox
                id={strategy}
                checked={enabled_strategies.includes(strategy)}
                onCheckedChange={() => handleStrategyToggle(strategy)}
              />
              <div className="flex-1 space-y-1">
                <Label
                  htmlFor={strategy}
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                >
                  {STRATEGY_LABELS[strategy]}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {STRATEGY_DESCRIPTIONS[strategy]}
                </p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {showCategoryInput && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-4">
              <p>
                Marketing Strategy is selected without Business Strategy. Please
                provide product categories to use for marketing strategy
                generation, or use the default categories.
              </p>

              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter product category (e.g., Core Products)"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddCategory();
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={handleAddCategory}
                    disabled={!newCategory.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {override_product_categories.length === 0 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleUseDefaults}
                  >
                    Use Default Categories
                  </Button>
                )}

                {override_product_categories.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">
                      Product Categories:
                    </Label>
                    <div className="flex flex-wrap gap-2">
                      {override_product_categories.map((category) => (
                        <div
                          key={category}
                          className="flex items-center gap-1 px-3 py-1 bg-primary/10 text-[var(--color-violet-600)] rounded-full text-sm"
                        >
                          <span>{category}</span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-4 w-4 p-0 hover:bg-transparent"
                            onClick={() => handleRemoveCategory(category)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Evaluation Mode</CardTitle>
          <CardDescription>
            For @ken-e.ai users: Enable dry-run mode to skip database storage
            (for testing/evaluation)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
            <Checkbox
              id="dry_run"
              checked={dry_run}
              onCheckedChange={(checked) => {
                console.log("[DRY_RUN] Checkbox changed to:", checked);
                onUpdate({ dry_run: checked as boolean });
              }}
            />
            <div className="flex-1 space-y-1">
              <Label
                htmlFor="dry_run"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
              >
                Dry-run mode (Skip storage)
              </Label>
              <p className="text-sm text-muted-foreground">
                When enabled, strategies will be generated and traced in W&B
                Weave, but NOT saved to Firestore or Neo4j. Use this for
                evaluation runs without polluting production data.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {enabled_strategies.length === 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            Please select at least one strategy to generate.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};

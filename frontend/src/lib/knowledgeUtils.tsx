import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle, Edit, Settings, XCircle } from "lucide-react";
import { Product } from "@/types/knowledge";

// Utility function to render a simple configuration section
export const renderConfigurationSection = (
  icon: React.ElementType,
  title: string,
  description: string,
  buttonText: string = "Coming Soon",
  onButtonClick?: () => void,
  isDisabled: boolean = true,
) => {
  const Icon = icon;

  return (
    <div className="border rounded-lg bg-[var(--color-bg-elevated)]">
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Icon className="h-5 w-5 text-[var(--color-text-tertiary)]" />
          <div className="text-left">
            <div className="font-medium">{title}</div>
            <div className="text-sm text-[var(--color-text-tertiary)]">
              {description}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isDisabled && (
            <span className="text-sm text-[var(--color-text-disabled)]">
              Coming Soon
            </span>
          )}
          <Button
            onClick={onButtonClick}
            variant="outline"
            disabled={isDisabled}
            className="flex items-center gap-2"
          >
            <Edit className="h-4 w-4" />
            {!isDisabled && buttonText}
          </Button>
        </div>
      </div>
    </div>
  );
};

// Utility function to render product cards
export const renderProductCard = (product: Product) => (
  <Card key={product.id} className="hover:shadow-lg transition-shadow">
    <CardHeader className="pb-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="text-lg font-semibold tracking-tight">
            {product.name}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            console.log(`Configure ${product.name}`);
          }}
        >
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {product.connected ? (
            <>
              <CheckCircle className="h-4 w-4 text-brand-dark-blue" />
              <Badge className="bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40">
                Connected
              </Badge>
            </>
          ) : (
            <>
              <XCircle className="h-4 w-4 text-red-600" />
              <Badge variant="outline" className="text-red-700 border-red-200">
                Not Connected
              </Badge>
            </>
          )}
        </div>
      </div>
    </CardContent>
  </Card>
);

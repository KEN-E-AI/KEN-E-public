import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  BarChart3,
  Activity,
  Lightbulb,
  Building,
  Users,
  TrendingUp,
  ExternalLink,
  Edit,
} from "lucide-react";
import { products } from "@/data";
import {
  renderConfigurationSection,
  renderProductCard,
} from "@/lib/knowledgeUtils";

const Knowledge = () => {
  const navigate = useNavigate();

  const renderProducts = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-dashboard-gray-900">
            Connected Products
          </h2>
          <p className="text-dashboard-gray-600">
            Link your MarTech products to enable AI-powered insights and
            automation
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {products.map(renderProductCard)}
      </div>
    </div>
  );

  return (
    <Layout pageTitle="Knowledge">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="text-dashboard-gray-600">
              Configure the information that KEN-E can access, and ensure that
              he understands your business.
            </div>
          </div>
        </div>

        {/* Configuration Sections */}
        <div className="space-y-4">
          {/* Products Section */}
          <Accordion type="single" collapsible>
            <AccordionItem value="products" className="border rounded-lg">
              <AccordionTrigger className="px-6 py-4 hover:no-underline">
                <div className="flex items-center gap-3">
                  <ExternalLink className="h-5 w-5 text-dashboard-gray-600" />
                  <div className="text-left">
                    <div className="font-medium">Products</div>
                    <div className="text-sm text-dashboard-gray-500">
                      Link and configure your MarTech products
                    </div>
                  </div>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-6 pb-6">
                {renderProducts()}
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {/* Metrics Section */}
          {renderConfigurationSection(
            BarChart3,
            "Metrics",
            "Define metrics that can be used to analyze performance",
            "",
            () => navigate("/knowledge/metrics"),
            false,
          )}

          {/* Activities Section */}
          {renderConfigurationSection(
            Activity,
            "Activities",
            "Define the internal and external activities that influence your business metrics",
            "",
            () => navigate("/knowledge/activities"),
            false,
          )}

          {/* Insights Section */}
          {renderConfigurationSection(
            Lightbulb,
            "Insights",
            "Review and manage the insights that KEN-E has uncovered about your business",
          )}

          {/* Measurement Strategy Section */}
          {renderConfigurationSection(
            TrendingUp,
            "Measurement Strategy",
            "Define your organizations objectives and KPI's",
            "",
            () => navigate("/measurement-strategy"),
            false,
          )}

          {/* Account Overview Section */}
          {renderConfigurationSection(
            Building,
            "Account Overview",
            "Configure KEN-E's understanding of your business strategy, goals and history",
          )}

          {/* Customers Section */}
          {renderConfigurationSection(
            Users,
            "Customers",
            "Configure KEN-E's understanding of your customers and ICP's",
          )}

          {/* Competitors Section */}
          {renderConfigurationSection(
            TrendingUp,
            "Competitors",
            "Configure KEN-E's understanding of your competitors",
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Knowledge;

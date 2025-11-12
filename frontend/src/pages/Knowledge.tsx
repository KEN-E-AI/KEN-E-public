import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import {
  BarChart3,
  Activity,
  Lightbulb,
  Building,
  Users,
  TrendingUp,
  Package,
  Palette,
} from "lucide-react";
import { renderConfigurationSection } from "@/lib/knowledgeUtils";

const Knowledge = () => {
  const navigate = useNavigate();

  return (
    <Layout pageTitle="Knowledge Base" maxWidth={false}>
      <div>
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
          {renderConfigurationSection(
            Package,
            "Products",
            "Describe the products or services that you offer, as well as the substitutes that are offered by your competitors.",
            "",
            () => navigate("/knowledge/products"),
            false,
          )}

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
            "",
            () => navigate("/knowledge/insights"),
            false,
          )}

          {/* Marketing Strategies Section */}
          {renderConfigurationSection(
            TrendingUp,
            "Marketing Strategies",
            "Define your organizations objectives and KPI's",
            "",
            () => navigate("/knowledge/strategy"),
            false,
          )}

          {/* Account Overview Section */}
          {renderConfigurationSection(
            Building,
            "Account Overview",
            "Configure KEN-E's understanding of your business strategy, goals and history",
            "",
            () => navigate("/knowledge/account"),
            false,
          )}

          {/* Customers Section */}
          {renderConfigurationSection(
            Users,
            "Customers",
            "Configure KEN-E's understanding of your customers and ICP's",
            "",
            () => navigate("/knowledge/customers"),
            false,
          )}

          {/* Competitors Section */}
          {renderConfigurationSection(
            TrendingUp,
            "Competitors",
            "Configure KEN-E's understanding of your competitors",
            "",
            () => navigate("/knowledge/competitors"),
            false,
          )}

          {/* Brand Guidelines Section */}
          {renderConfigurationSection(
            Palette,
            "Brand Guidelines",
            "Describe the standards that define your brand's identity to ensure that all content drafted by KEN-E is consistent and aligned with your brand strategy.",
            "",
            () => navigate("/knowledge/brand"),
            false,
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Knowledge;

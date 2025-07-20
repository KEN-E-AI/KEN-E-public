import Layout from "@/components/layout/Layout";
import { products } from "@/data";
import { renderProductCard } from "@/lib/knowledgeUtils";

const KnowledgeProducts = () => {
  return (
    <Layout pageTitle="Products Configuration">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-xl font-semibold text-dashboard-gray-900">
            Connected Products
          </h2>
          <p className="text-dashboard-gray-600">
            Link your MarTech products to enable AI-powered insights and
            automation
          </p>
        </div>

        {/* Products Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {products.map(renderProductCard)}
        </div>
      </div>
    </Layout>
  );
};

export default KnowledgeProducts;

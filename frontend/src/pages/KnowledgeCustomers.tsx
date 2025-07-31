import CustomerKeywordsConfiguration from "@/components/configuration/CustomerKeywordsConfiguration";
import Layout from "@/components/layout/Layout";

export default function KnowledgeCustomers() {
  return (
    <Layout>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">
            Customer Knowledge
          </h2>
          <p className="text-muted-foreground">
            Manage keywords related to your customers for targeted monitoring.
          </p>
        </div>

        <CustomerKeywordsConfiguration />
      </div>
    </Layout>
  );
}

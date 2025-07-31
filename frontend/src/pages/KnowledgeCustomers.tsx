import CustomerKeywordsConfiguration from "@/components/configuration/CustomerKeywordsConfiguration";
import Layout from "@/components/layout/Layout";

export default function KnowledgeCustomers() {
  return (
    <Layout pageTitle="Customer Knowledge">
      <div className="space-y-6">
        <p className="text-muted-foreground">
          Manage keywords related to your customers for targeted monitoring.
        </p>

        <CustomerKeywordsConfiguration />
      </div>
    </Layout>
  );
}

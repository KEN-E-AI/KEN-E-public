import CompetitorsConfiguration from "@/components/configuration/CompetitorsConfiguration";
import Layout from "@/components/layout/Layout";

export default function KnowledgeCompetitors() {
  return (
    <Layout pageTitle="Competitor Knowledge">
      <div className="space-y-6">
        <p className="text-muted-foreground">
          Track your competitors' mentions and activities in news and social
          media.
        </p>

        <CompetitorsConfiguration />
      </div>
    </Layout>
  );
}

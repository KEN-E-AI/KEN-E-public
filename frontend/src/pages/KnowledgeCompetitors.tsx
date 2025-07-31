import CompetitorsConfiguration from "@/components/configuration/CompetitorsConfiguration";
import Layout from "@/components/layout/Layout";

export default function KnowledgeCompetitors() {
  return (
    <Layout>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">
            Competitor Knowledge
          </h2>
          <p className="text-muted-foreground">
            Track your competitors' mentions and activities in news and social
            media.
          </p>
        </div>

        <CompetitorsConfiguration />
      </div>
    </Layout>
  );
}

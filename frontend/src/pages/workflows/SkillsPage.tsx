import { Lightbulb } from "lucide-react";
import { EmptyState } from "./components/EmptyState";

export function SkillsPage() {
  return (
    <div className="px-6 pb-6">
      <EmptyState
        icon={<Lightbulb className="size-8 text-muted-foreground" />}
        title="No skills yet"
        description="Package your team's playbooks as reusable skills."
        actionLabel="Create a skill"
        onAction={() => {}}
      />
    </div>
  );
}

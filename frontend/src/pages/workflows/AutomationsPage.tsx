import { PlayCircle } from "lucide-react";
import { EmptyState } from "./components/EmptyState";

export function AutomationsPage() {
  return (
    <div className="px-6 pb-6">
      <EmptyState
        icon={<PlayCircle className="size-8 text-muted-foreground" />}
        title="Schedule recurring work."
        description="Let KEN-E take it from here."
        actionLabel="Create an automation"
        onAction={() => {}}
      />
    </div>
  );
}

export default AutomationsPage;

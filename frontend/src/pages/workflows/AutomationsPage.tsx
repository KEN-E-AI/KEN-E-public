import { PlayCircle } from "lucide-react";
import { EmptyState } from "./components/EmptyState";

export function AutomationsPage() {
  return (
    <div className="px-6 pb-6">
      <EmptyState
        icon={<PlayCircle className="size-8 text-muted-foreground" />}
        title="Schedule recurring work."
        description="Let KEN-E take it from here. Automations are coming soon — ask KEN-E in chat to set one up."
      />
    </div>
  );
}

export default AutomationsPage;

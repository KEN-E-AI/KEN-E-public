import { Bot } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { EmptyState } from "./components/EmptyState";

export function AgentsPage() {
  const navigate = useNavigate();

  return (
    <EmptyState
      icon={<Bot className="size-8 text-muted-foreground" />}
      title="Assemble specialist agents tailored to your workflow."
      actionLabel="Create an agent"
      onAction={() => navigate("/workflows/agents/new")}
    />
  );
}

export default AgentsPage;

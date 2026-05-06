import { useState } from "react";

const Campaigns = () => {
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);

  return (
    <>
      <header className="px-6 pt-6 pb-4">
        <h1 className="text-3xl font-bold">Campaigns</h1>
      </header>
      <div className="space-y-6">
        <div className="bg-[var(--color-bg-elevated)] rounded-lg p-6 border border-[var(--color-border-default)]">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Campaigns Overview
          </h2>
          <p className="text-[var(--color-text-tertiary)]">
            Manage and track your marketing campaigns, analyze performance, and
            optimize campaign strategies across all channels.
          </p>
        </div>
      </div>
    </>
  );
};

export default Campaigns;

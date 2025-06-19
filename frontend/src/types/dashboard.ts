export interface Objective {
  id: string;
  name: string;
  objective: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  order: number;
  supportingMetrics: string[];
  channels: ChannelWithTactics[];
}

// Legacy interface for backward compatibility
export interface FunnelStep extends Objective {}

export interface Channel {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

export interface Tactic {
  id: string;
  name: string;
  effectivenessKPI: string;
  efficiencyKPI: string;
  supportingMetrics: string[];
}

export interface StepChannelsAndTactics {
  channels: Channel[];
  channelTactics: Record<string, Tactic[]>;
}

export interface AccountData {
  funnelSteps: FunnelStep[];
  stepChannelsAndTactics: Record<string, StepChannelsAndTactics>;
}

export interface DateRange {
  from: Date;
  to: Date;
}

export interface DashboardState {
  selectedAccount: string;
  selectedChannel: string;
  selectedTactic: string;
  selectedTab: string;
  dateRange: DateRange;
  comparisonDateRange?: DateRange;
  editStepsModalOpen: boolean;
}

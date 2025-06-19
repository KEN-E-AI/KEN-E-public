import { useState, useCallback } from "react";
import { ACCOUNTS_DATA, DEFAULT_STEP_DATA } from "@/data/accountData";
import {
  DashboardState,
  FunnelStep,
  Channel,
  Tactic,
  AccountData,
} from "@/types/dashboard";

const INITIAL_STATE: DashboardState = {
  selectedAccount: "acme-corp",
  selectedChannel: "Overview",
  selectedTactic: "",
  selectedTab: "Awareness",
  dateRange: {
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  },
  comparisonDateRange: undefined,
  editStepsModalOpen: false,
};

export const useDashboardState = () => {
  const [state, setState] = useState<DashboardState>(INITIAL_STATE);
  const [accountDataVersion, setAccountDataVersion] = useState(0);

  // Get current account data
  const getCurrentAccountData = useCallback((): AccountData => {
    return ACCOUNTS_DATA[state.selectedAccount] || ACCOUNTS_DATA["acme-corp"];
  }, [state.selectedAccount]);

  // Get current step's channels and tactics
  const getCurrentStepData = useCallback(() => {
    const accountData = getCurrentAccountData();
    return (
      accountData.stepChannelsAndTactics[state.selectedTab] || DEFAULT_STEP_DATA
    );
  }, [getCurrentAccountData, state.selectedTab]);

  // Handle account change
  const handleAccountChange = useCallback((newAccount: string) => {
    const newAccountData = ACCOUNTS_DATA[newAccount];
    const firstStep = newAccountData?.funnelSteps
      .slice()
      .sort((a, b) => a.order - b.order)[0];

    setState((prev) => ({
      ...prev,
      selectedAccount: newAccount,
      selectedChannel: "Overview",
      selectedTactic: "",
      selectedTab: firstStep?.name || "Awareness",
    }));
  }, []);

  // Handle channels change
  const handleChannelsChange = useCallback(
    (newChannels: Channel[]) => {
      const currentAccountData = getCurrentAccountData();
      const currentStepData = getCurrentStepData();

      const updatedStepData = {
        ...currentStepData,
        channels: newChannels,
      };

      const updatedAccountData = {
        ...currentAccountData,
        stepChannelsAndTactics: {
          ...currentAccountData.stepChannelsAndTactics,
          [state.selectedTab]: updatedStepData,
        },
      };

      ACCOUNTS_DATA[state.selectedAccount] = updatedAccountData;
      setAccountDataVersion((prev) => prev + 1);
    },
    [
      getCurrentAccountData,
      getCurrentStepData,
      state.selectedAccount,
      state.selectedTab,
    ],
  );

  // Handle channel tactics change
  const handleChannelTacticsChange = useCallback(
    (channelName: string, newTactics: Tactic[]) => {
      const currentAccountData = getCurrentAccountData();
      const currentStepData = getCurrentStepData();

      const updatedChannelTactics = {
        ...currentStepData.channelTactics,
        [channelName]: newTactics,
      };

      const updatedStepData = {
        ...currentStepData,
        channelTactics: updatedChannelTactics,
      };

      const updatedAccountData = {
        ...currentAccountData,
        stepChannelsAndTactics: {
          ...currentAccountData.stepChannelsAndTactics,
          [state.selectedTab]: updatedStepData,
        },
      };

      ACCOUNTS_DATA[state.selectedAccount] = updatedAccountData;
      setAccountDataVersion((prev) => prev + 1);
    },
    [
      getCurrentAccountData,
      getCurrentStepData,
      state.selectedAccount,
      state.selectedTab,
    ],
  );

  // Handle funnel steps change
  const handleFunnelStepsChange = useCallback(
    (newSteps: FunnelStep[]) => {
      const currentAccountData = getCurrentAccountData();
      const updatedAccountData = {
        ...currentAccountData,
        funnelSteps: newSteps,
      };

      ACCOUNTS_DATA[state.selectedAccount] = updatedAccountData;

      // Check if current tab still exists
      const sortedSteps = newSteps.slice().sort((a, b) => a.order - b.order);
      const currentTabExists = sortedSteps.some(
        (step) => step.name === state.selectedTab,
      );

      if (!currentTabExists && sortedSteps.length > 0) {
        setState((prev) => ({
          ...prev,
          selectedTab: sortedSteps[0].name,
        }));
      }
    },
    [getCurrentAccountData, state.selectedAccount, state.selectedTab],
  );

  // Handle tab change with proper selection reset
  const handleTabChange = useCallback(
    (newTab: string) => {
      const accountData = getCurrentAccountData();
      const newStepData =
        accountData.stepChannelsAndTactics[newTab] || DEFAULT_STEP_DATA;

      const channelExists =
        state.selectedChannel === "Overview" ||
        newStepData.channels.some(
          (channel) => channel.name === state.selectedChannel,
        );

      let newSelectedChannel = state.selectedChannel;
      let newSelectedTactic = state.selectedTactic;

      if (!channelExists) {
        newSelectedChannel = "Overview";
        newSelectedTactic = "";
      } else if (state.selectedChannel !== "Overview") {
        const tactics = newStepData.channelTactics[state.selectedChannel] || [];
        const tacticExists = tactics.some(
          (tactic) => tactic.name === state.selectedTactic,
        );
        if (!tacticExists) {
          newSelectedTactic = "Overview";
        }
      } else {
        newSelectedTactic = "";
      }

      setState((prev) => ({
        ...prev,
        selectedTab: newTab,
        selectedChannel: newSelectedChannel,
        selectedTactic: newSelectedTactic,
      }));
    },
    [getCurrentAccountData, state.selectedChannel, state.selectedTactic],
  );

  // Update specific state values
  const updateState = useCallback((updates: Partial<DashboardState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  }, []);

  return {
    state,
    getCurrentAccountData,
    getCurrentStepData,
    handleAccountChange,
    handleChannelsChange,
    handleChannelTacticsChange,
    handleFunnelStepsChange,
    handleTabChange,
    updateState,
    accountDataVersion,
  };
};

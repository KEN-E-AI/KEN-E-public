import { useState, useCallback } from "react";
import { ACCOUNTS_DATA, DEFAULT_STEP_DATA } from "@/data/accountData";
import {
  DashboardState,
  FunnelStep,
  Objective,
  Channel,
  Tactic,
  AccountData,
  ChannelWithTactics,
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

  // Get current objective's channels and tactics
  const getCurrentStepData = useCallback(() => {
    const accountData = getCurrentAccountData();

    // Find the current objective by name
    const currentObjective = accountData.objectives?.find(
      (obj) => obj.name === state.selectedTab,
    );

    if (currentObjective) {
      // Convert the new structure to the old format for backward compatibility
      const channelTactics: Record<string, Tactic[]> = {};
      currentObjective.channels.forEach((channel) => {
        channelTactics[channel.name] = channel.tactics || [];
      });

      return {
        channels: currentObjective.channels,
        channelTactics,
      };
    }

    // Fallback to legacy structure if objectives don't exist
    return (
      accountData.stepChannelsAndTactics?.[state.selectedTab] ||
      DEFAULT_STEP_DATA
    );
  }, [getCurrentAccountData, state.selectedTab]);

  // Handle account change
  const handleAccountChange = useCallback((newAccount: string) => {
    const newAccountData = ACCOUNTS_DATA[newAccount];

    // Try to get first objective, fallback to funnelSteps for backward compatibility
    const firstObjective = newAccountData?.objectives
      ?.slice()
      .sort((a, b) => a.order - b.order)[0];

    const firstStep =
      firstObjective ||
      newAccountData?.funnelSteps?.slice().sort((a, b) => a.order - b.order)[0];

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

      if (currentAccountData.objectives) {
        // Update the new objectives structure
        const updatedObjectives = currentAccountData.objectives.map(
          (objective) => {
            if (objective.name === state.selectedTab) {
              // Convert Channel[] to ChannelWithTactics[] by preserving existing tactics
              const updatedChannels: ChannelWithTactics[] = newChannels.map(
                (channel) => {
                  const existingChannel = objective.channels.find(
                    (c) => c.id === channel.id,
                  );
                  return {
                    ...channel,
                    tactics: existingChannel?.tactics || [],
                  };
                },
              );

              return {
                ...objective,
                channels: updatedChannels,
              };
            }
            return objective;
          },
        );

        const updatedAccountData = {
          ...currentAccountData,
          objectives: updatedObjectives,
        };

        ACCOUNTS_DATA[state.selectedAccount] = updatedAccountData;
      } else {
        // Fallback for legacy structure
        const currentStepData = getCurrentStepData();
        const updatedStepData = {
          ...currentStepData,
          channels: newChannels,
        };

        const updatedAccountData = {
          ...currentAccountData,
          stepChannelsAndTactics: {
            ...currentAccountData.stepChannelsAndTactics!,
            [state.selectedTab]: updatedStepData,
          },
        };

        ACCOUNTS_DATA[state.selectedAccount] = updatedAccountData;
      }

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

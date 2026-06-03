import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { AgentToolPicker } from "./AgentToolPicker";
import type { AccountToolEntry } from "@/lib/api/tools";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const fixtureTools: AccountToolEntry[] = [
  {
    tool_id: "function.create_visualization",
    name: "create_visualization",
    description: "Render a Vega-Lite chart artifact.",
    category: "general",
    source: "global_default",
    mcp_server: null,
    integration_platform: null,
  },
  {
    tool_id: "google_analytics_mcp.list_ga_accounts",
    name: "list_ga_accounts",
    description: "List Google Analytics accounts.",
    category: "analytics",
    source: "integration",
    mcp_server: "google_analytics_mcp",
    integration_platform: "google_analytics",
  },
  {
    tool_id: "google_analytics_mcp.query_ga_report",
    name: "query_ga_report",
    description: "Run an analytics report.",
    category: "analytics",
    source: "integration",
    mcp_server: "google_analytics_mcp",
    integration_platform: "google_analytics",
  },
];

// Convenience for asserting onChange args without caring about array order —
// the picker preserves insertion order, but tests should not be coupled to
// that internal detail.
function asSet(value: string[]) {
  return new Set(value);
}

// ─── States ───────────────────────────────────────────────────────────────────

describe("AgentToolPicker — loading / error / empty", () => {
  it("shows a skeleton while loading", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={undefined}
        isLoading={true}
        isError={false}
      />,
    );
    expect(screen.getByTestId("tool-picker-loading")).toBeInTheDocument();
  });

  it("shows an error message on failure", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={undefined}
        isLoading={false}
        isError={true}
      />,
    );
    expect(screen.getByTestId("tool-picker-error")).toBeInTheDocument();
  });

  it("shows the empty-inventory state when no tools are returned", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={[]}
        isLoading={false}
        isError={false}
      />,
    );
    expect(
      screen.getByTestId("tool-picker-empty-inventory"),
    ).toBeInTheDocument();
  });
});

// ─── Grouping ─────────────────────────────────────────────────────────────────

describe("AgentToolPicker — grouping", () => {
  it("renders a Built-in group plus one group per mcp_server", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    expect(
      screen.getByTestId("tool-picker-group-__builtin__"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("tool-picker-group-google_analytics_mcp"),
    ).toBeInTheDocument();
  });

  it("humanizes the integration platform in the group label", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByText("Google Analytics")).toBeInTheDocument();
    expect(screen.getByText("Built-in")).toBeInTheDocument();
  });

  it("renders selection count badge per group", () => {
    render(
      <AgentToolPicker
        value={["google_analytics_mcp.list_ga_accounts"]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    expect(
      screen.getByTestId("tool-picker-group-count-google_analytics_mcp"),
    ).toHaveTextContent("1 / 2");
    expect(
      screen.getByTestId("tool-picker-group-count-__builtin__"),
    ).toHaveTextContent("0 / 1");
  });

  it("renders the summary count above the groups", () => {
    render(
      <AgentToolPicker
        value={["function.create_visualization"]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByTestId("tool-picker-summary")).toHaveTextContent(
      "1 of 3 selected",
    );
  });

  it("places an agent-as-a-tool under Built-in and toggles its id (AH-98)", () => {
    const onChange = vi.fn();
    const toolsWithAgent: AccountToolEntry[] = [
      ...fixtureTools,
      {
        tool_id: "agent.google_search",
        name: "google_search",
        description: "Search the public web via Google.",
        category: "research",
        source: "global_default",
        mcp_server: null,
        integration_platform: null,
      },
    ];
    render(
      <AgentToolPicker
        value={[]}
        onChange={onChange}
        tools={toolsWithAgent}
        isLoading={false}
        isError={false}
      />,
    );
    // The agent tool (source=global_default) groups under "Built-in".
    const builtIn = screen.getByTestId("tool-picker-group-__builtin__");
    expect(
      within(builtIn).getByTestId("tool-picker-tool-agent.google_search"),
    ).toBeInTheDocument();
    // Selecting it persists the agent.google_search id.
    fireEvent.click(
      screen.getByTestId("tool-picker-checkbox-agent.google_search"),
    );
    expect(onChange).toHaveBeenCalledWith(["agent.google_search"]);
  });
});

// ─── Selection ────────────────────────────────────────────────────────────────

describe("AgentToolPicker — selection", () => {
  it("toggles a single tool on click", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={[]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.click(
      screen.getByTestId(
        "tool-picker-checkbox-google_analytics_mcp.list_ga_accounts",
      ),
    );
    expect(onChange).toHaveBeenCalledWith([
      "google_analytics_mcp.list_ga_accounts",
    ]);
  });

  it("removes a tool when unchecking", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={[
          "function.create_visualization",
          "google_analytics_mcp.list_ga_accounts",
        ]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.click(
      screen.getByTestId(
        "tool-picker-checkbox-google_analytics_mcp.list_ga_accounts",
      ),
    );
    expect(onChange).toHaveBeenCalledWith(["function.create_visualization"]);
  });

  it("selects every tool in a group with 'Select all'", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={["function.create_visualization"]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.click(
      screen.getByTestId("tool-picker-group-select-all-google_analytics_mcp"),
    );
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as string[];
    expect(asSet(next)).toEqual(
      asSet([
        "function.create_visualization",
        "google_analytics_mcp.list_ga_accounts",
        "google_analytics_mcp.query_ga_report",
      ]),
    );
  });

  it("clears a fully-selected group with 'Deselect all'", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={[
          "google_analytics_mcp.list_ga_accounts",
          "google_analytics_mcp.query_ga_report",
        ]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    // With all of the group selected, the button reads "Deselect all".
    const button = screen.getByTestId(
      "tool-picker-group-select-all-google_analytics_mcp",
    );
    expect(button).toHaveTextContent("Deselect all");
    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledWith([]);
  });
});

// ─── Search ───────────────────────────────────────────────────────────────────

describe("AgentToolPicker — search", () => {
  it("narrows the list by name (case-insensitive)", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.change(screen.getByTestId("tool-picker-search"), {
      target: { value: "REPORT" },
    });
    expect(
      screen.getByTestId(
        "tool-picker-tool-google_analytics_mcp.query_ga_report",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId(
        "tool-picker-tool-google_analytics_mcp.list_ga_accounts",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("tool-picker-tool-function.create_visualization"),
    ).not.toBeInTheDocument();
  });

  it("matches against the tool description too", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.change(screen.getByTestId("tool-picker-search"), {
      target: { value: "vega" },
    });
    expect(
      screen.getByTestId("tool-picker-tool-function.create_visualization"),
    ).toBeInTheDocument();
  });

  it("shows the no-results state when nothing matches", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.change(screen.getByTestId("tool-picker-search"), {
      target: { value: "nonexistent-thing" },
    });
    expect(screen.getByTestId("tool-picker-no-results")).toBeInTheDocument();
  });

  it("hides empty groups but keeps non-empty groups", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.change(screen.getByTestId("tool-picker-search"), {
      target: { value: "create_visualization" },
    });
    expect(
      screen.getByTestId("tool-picker-group-__builtin__"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("tool-picker-group-google_analytics_mcp"),
    ).not.toBeInTheDocument();
  });

  it("'Select all' only operates on tools currently matching the search", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={[]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.change(screen.getByTestId("tool-picker-search"), {
      target: { value: "report" },
    });
    fireEvent.click(
      screen.getByTestId("tool-picker-group-select-all-google_analytics_mcp"),
    );
    expect(onChange).toHaveBeenCalledWith([
      "google_analytics_mcp.query_ga_report",
    ]);
  });
});

// ─── Rendering details ────────────────────────────────────────────────────────

describe("AgentToolPicker — rendering", () => {
  it("renders the tool description alongside the name", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    const row = screen.getByTestId(
      "tool-picker-tool-function.create_visualization",
    );
    expect(within(row).getByText("create_visualization")).toBeInTheDocument();
    expect(
      within(row).getByText("Render a Vega-Lite chart artifact."),
    ).toBeInTheDocument();
  });
});

// ─── AH-95: google_analytics_mcp group rendering ─────────────────────────────

describe("AgentToolPicker — GA MCP group (AH-95)", () => {
  it("renders the google_analytics_mcp group when GA tools are in the inventory", () => {
    render(
      <AgentToolPicker
        value={[]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    // The GA MCP group must render.
    expect(
      screen.getByTestId("tool-picker-group-google_analytics_mcp"),
    ).toBeInTheDocument();
    // Both GA tools must appear inside that group.
    const gaGroup = screen.getByTestId(
      "tool-picker-group-google_analytics_mcp",
    );
    expect(
      within(gaGroup).getByTestId(
        "tool-picker-tool-google_analytics_mcp.list_ga_accounts",
      ),
    ).toBeInTheDocument();
    expect(
      within(gaGroup).getByTestId(
        "tool-picker-tool-google_analytics_mcp.query_ga_report",
      ),
    ).toBeInTheDocument();
  });

  it("selecting a GA tool adds its id to the onChange callback", () => {
    const onChange = vi.fn();
    render(
      <AgentToolPicker
        value={[]}
        onChange={onChange}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    fireEvent.click(
      screen.getByTestId(
        "tool-picker-checkbox-google_analytics_mcp.list_ga_accounts",
      ),
    );
    expect(onChange).toHaveBeenCalledWith([
      "google_analytics_mcp.list_ga_accounts",
    ]);
  });

  it("pre-selected GA tools appear as checked checkboxes", () => {
    render(
      <AgentToolPicker
        value={["google_analytics_mcp.list_ga_accounts"]}
        onChange={() => {}}
        tools={fixtureTools}
        isLoading={false}
        isError={false}
      />,
    );
    const checkbox = screen.getByTestId(
      "tool-picker-checkbox-google_analytics_mcp.list_ga_accounts",
    );
    // Radix Checkbox stores state as aria-checked
    expect(checkbox).toHaveAttribute("aria-checked", "true");
  });
});

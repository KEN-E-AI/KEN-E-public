import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { Artifact } from "@/lib/chatApi";

// ─── Mock firebase (defensive, avoids auth initialisation side-effects) ────────
vi.mock("@/lib/firebase", () => ({ auth: { currentUser: null } }));

// ─── VegaEmbed mock: a vi.fn() so individual tests can override implementation ──
// Default behaviour: render a div with the serialised spec (no real Vega).
const mockVegaEmbed = vi.fn(
  (props: { spec: unknown; onError?: (e: unknown) => void }) => (
    <div data-testid="vega-embed" data-spec={JSON.stringify(props.spec)} />
  ),
);

vi.mock("react-vega", () => ({
  // Wrap in a plain function so React treats it as a function component; the
  // inner call goes to the vi.fn() so tests can spy on args or swap impl.
  VegaEmbed: (props: { spec: unknown; onError?: (e: unknown) => void }) =>
    mockVegaEmbed(props),
}));

// ─── Stub getComputedStyle so useVegaTheme's cssVar calls don't return "" ───────
beforeEach(() => {
  vi.spyOn(window, "getComputedStyle").mockReturnValue({
    getPropertyValue: (name: string) =>
      name.includes("color") || name.startsWith("--color") ? "#ffffff" : "",
  } as unknown as CSSStyleDeclaration);
});

// ─── Import component AFTER mocks are registered ─────────────────────────────
import { ChatArtifactRenderer } from "../ChatArtifactRenderer";

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const sampleArtifact: Artifact = {
  type: "visualization" as const,
  spec: {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    mark: "line",
    data: { values: [{ x: 1, y: 2 }] },
    encoding: {
      x: { field: "x", type: "ordinal" },
      y: { field: "y", type: "quantitative" },
    },
  },
  metadata: {
    chart_type_suggestion: "line" as const,
    title: "Test Chart",
    data_source: "google_analytics",
  },
};

// ─── Tests ────────────────────────────────────────────────────────────────────
describe("ChatArtifactRenderer", () => {
  // AC-1: valid spec → VegaEmbed renders inside wrapper
  test("renders wrapper and passes spec with $schema to VegaEmbed", () => {
    render(<ChatArtifactRenderer artifact={sampleArtifact} />);

    expect(screen.getByTestId("chat-artifact-renderer")).toBeInTheDocument();

    const embed = screen.getByTestId("vega-embed");
    expect(embed).toBeInTheDocument();

    const passedSpec = JSON.parse(embed.getAttribute("data-spec") ?? "{}");
    expect(passedSpec.$schema).toBe(
      "https://vega.github.io/schema/vega-lite/v6.json",
    );
  });

  // AC-2: non-visualization artifact → returns null
  test("returns null and does not render wrapper for non-visualization artifact type", () => {
    const consoleSpy = vi
      .spyOn(console, "debug")
      .mockImplementation(() => undefined);

    const textArtifact: Artifact = {
      ...sampleArtifact,
      type: "text" as const,
    };

    const { container } = render(
      <ChatArtifactRenderer artifact={textArtifact} />,
    );

    expect(
      container.querySelector('[data-testid="chat-artifact-renderer"]'),
    ).toBeNull();
    expect(consoleSpy).toHaveBeenCalledWith(
      "[ChatArtifactRenderer] non-visualization artifact skipped",
      "text",
    );

    consoleSpy.mockRestore();
  });

  // AC-3: viewOverride swaps spec.mark
  test("passes mark from viewOverride to VegaEmbed, overriding the original mark", () => {
    render(
      <ChatArtifactRenderer artifact={sampleArtifact} viewOverride="bar" />,
    );

    const embed = screen.getByTestId("vega-embed");
    const passedSpec = JSON.parse(embed.getAttribute("data-spec") ?? "{}");
    expect(passedSpec.mark).toBe("bar");
  });

  // AC-4: showDataLabels wraps spec in layer
  test("wraps spec in a layer when showDataLabels is true", () => {
    render(
      <ChatArtifactRenderer artifact={sampleArtifact} showDataLabels={true} />,
    );

    const embed = screen.getByTestId("vega-embed");
    const passedSpec = JSON.parse(embed.getAttribute("data-spec") ?? "{}");
    expect(passedSpec).toHaveProperty("layer");
    expect(Array.isArray(passedSpec.layer)).toBe(true);
  });

  // AC-5: onError callback → SpecFallback renders "Could not render chart"
  test("renders SpecFallback when VegaEmbed calls onError", () => {
    // Override for this test only: call onError immediately on mount
    mockVegaEmbed.mockImplementationOnce(
      (props: { spec: unknown; onError?: (e: unknown) => void }) => {
        if (props.onError) {
          props.onError("Vega render failed: bad spec");
        }
        return (
          <div
            data-testid="vega-embed"
            data-spec={JSON.stringify(props.spec)}
          />
        );
      },
    );

    render(<ChatArtifactRenderer artifact={sampleArtifact} />);

    expect(screen.getByText("Could not render chart")).toBeInTheDocument();
  });

  // The settings gear button lives in ChartArtifactItem (ChatInterface.tsx), not here.
  // Its open/close behavior is tested in ChatInterface.artifacts.spec.tsx.
  test("renders wrapper with data-testid and no settings button inside", () => {
    render(<ChatArtifactRenderer artifact={sampleArtifact} />);
    expect(screen.getByTestId("chat-artifact-renderer")).toBeInTheDocument();
    // The gear button is not rendered inside ChatArtifactRenderer itself
    expect(
      screen.queryByRole("button", { name: /chart settings/i }),
    ).not.toBeInTheDocument();
  });
});

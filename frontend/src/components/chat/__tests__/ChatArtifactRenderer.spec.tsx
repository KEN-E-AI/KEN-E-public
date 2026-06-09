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
import { ChatArtifactRenderer, SpecFallback } from "../ChatArtifactRenderer";

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

  // Regression (AH-PRD-04 follow-up): the spec must carry an explicit NUMERIC
  // width, never "container". react-vega v8's <VegaEmbed> embeds into a bare
  // <div> whose ``width: "container"`` measurement resolves to 0, painting the
  // chart into a 0px-wide <svg> (blank chart, no error). The renderer measures
  // the container and passes a number instead.
  test("passes an explicit numeric width to VegaEmbed (never 'container')", () => {
    render(<ChatArtifactRenderer artifact={sampleArtifact} />);

    const embed = screen.getByTestId("vega-embed");
    const passedSpec = JSON.parse(embed.getAttribute("data-spec") ?? "{}");
    expect(typeof passedSpec.width).toBe("number");
    expect(passedSpec.width).toBeGreaterThan(0);
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

  // SpecFallback: clicking "Show spec" toggles the collapsible JSON block
  test("SpecFallback toggles <pre> block open and closed on Show spec click", () => {
    const spec = {
      mark: "line",
      $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    };
    render(<SpecFallback spec={spec} error="render failed" />);

    // Pre block not visible initially
    expect(screen.queryByTestId("spec-json")).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: /show spec/i });
    fireEvent.click(toggle);

    // Pre block now visible and contains spec JSON
    const pre = screen.getByTestId("spec-json");
    expect(pre).toBeInTheDocument();
    expect(pre.textContent).toContain('"line"');

    // Clicking again collapses
    fireEvent.click(toggle);
    expect(screen.queryByTestId("spec-json")).not.toBeInTheDocument();
  });

  // SpecFallback: error text and JSON content are rendered correctly when open
  test("SpecFallback renders error text and serialised spec JSON when open", () => {
    const spec = { mark: "bar", data: { values: [{ x: 1 }] } };
    const errorMsg = "Error: Unknown encoding channel";
    render(<SpecFallback spec={spec} error={errorMsg} />);

    // Error text always visible
    expect(screen.getByText(errorMsg)).toBeInTheDocument();
    expect(screen.getByText("Could not render chart")).toBeInTheDocument();

    // Open the spec block
    fireEvent.click(screen.getByRole("button", { name: /show spec/i }));

    const pre = screen.getByTestId("spec-json");
    expect(pre).toBeInTheDocument();
    expect(pre.textContent).toContain(JSON.stringify(spec, null, 2));
  });

  // ChartErrorBoundary: sync throw inside VisualizationRenderer is caught and
  // shows SpecFallback; the outer data-testid wrapper remains mounted.
  test("ChartErrorBoundary catches sync render throw and shows SpecFallback; wrapper stays mounted", () => {
    // Replace VegaEmbed with a component that throws synchronously during render.
    // mockImplementation (not mockImplementationOnce) is used because React 18's
    // dev-mode error-replay consumes the once-queue when it re-renders the
    // offending subtree for stack-trace capture — the permanent implementation
    // survives the replay and ensures the boundary commits its fallback.
    const ThrowOnRender = () => {
      throw new Error("synthetic sync throw");
    };
    mockVegaEmbed.mockImplementation(() => <ThrowOnRender />);

    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    // Prevent React 18 dev-mode window error events from failing the test.
    const errorHandler = (e: ErrorEvent) => e.preventDefault();
    window.addEventListener("error", errorHandler);

    try {
      render(<ChatArtifactRenderer artifact={sampleArtifact} />);

      // Fallback text is present
      expect(screen.getByText("Could not render chart")).toBeInTheDocument();

      // The outer wrapper is still mounted (boundary is scoped to the chart subtree)
      expect(screen.getByTestId("chat-artifact-renderer")).toBeInTheDocument();

      // componentDidCatch called console.error; componentStack may be null in some
      // environments so expect.anything() is used for the third argument.
      expect(consoleSpy).toHaveBeenCalledWith(
        "[ChartErrorBoundary]",
        expect.any(Error),
        expect.anything(),
      );
    } finally {
      consoleSpy.mockRestore();
      window.removeEventListener("error", errorHandler);
      // Explicitly restore the default implementation so subsequent tests are
      // unaffected (documents intent; vi.clearAllMocks does not reset implementations).
      mockVegaEmbed.mockImplementation(
        (props: { spec: unknown; onError?: (e: unknown) => void }) => (
          <div
            data-testid="vega-embed"
            data-spec={JSON.stringify(props.spec)}
          />
        ),
      );
    }
  });
});

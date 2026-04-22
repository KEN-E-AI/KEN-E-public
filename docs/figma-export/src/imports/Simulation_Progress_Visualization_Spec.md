# Simulation Progress Visualization — Figma Make Implementation Spec

## Overview

Build a **SimulationProgressPanel** component that replaces the "Planned Spend by Funnel Stage" card inside `SimulationsSection` when a simulation is running. This visualization showcases a multi-step AI + statistical model pipeline to build user trust during a ~30-60 second wait.

The component is self-contained with its own state machine. When `simulating` is `true`, `SimulationsSection` renders this panel instead of the funnel breakdown card. When the simulation completes, it crossfades to `SimulationResults`.

---

## Integration Point

In `SimulationsSection.tsx`, the `{/* Funnel Breakdown */}` card is conditionally replaced:

```tsx
{simulating ? (
  <SimulationProgressPanel
    simulationMonths={simulationMonths}
    onComplete={() => { setSimulating(false); setSimulationRun(true); }}
    onCancel={() => { setSimulating(false); }}
  />
) : (
  <Card className="p-5">
    {/* existing funnel breakdown */}
  </Card>
)}
```

The `SimulationSidebar` also updates during simulation to show a compact status instead of the spinner.

---

## Layout

The panel occupies the full width of the main content area (~800px). It is a `Card` with a violet-tinted gradient background and a `border-2 border-[var(--color-violet-300)]` border.

```
┌──────────────────────────────────────────────────────────────┐
│  [Phase Label]                                    [Timer]    │
│  [Sub-label / description]                                   │
│                                                              │
│  [═══════════════════░░░░░░░░░░░░░░░░░░░░] Progress Bar     │
│                                                              │
│  ┌────────────┐  →  ┌────────────┐  →  ┌────────────┐      │
│  │ March 2026 │     │ April 2026 │     │  May 2026  │      │
│  │            │     │            │     │            │      │
│  │ ◉ Prob Awr │     │ ○ Prob Awr │     │ ○ Prob Awr │      │
│  │ ● Brand Aw │     │ ○ Brand Aw │     │ ○ Brand Aw │      │
│  │ ○ Consider │     │ ○ Consider │     │ ○ Consider │      │
│  │ ○ Convert  │     │ ○ Convert  │     │ ○ Convert  │      │
│  └────────────┘     └────────────┘     └────────────┘      │
│                                                              │
│  [Activity insight line]                         [Cancel]    │
└──────────────────────────────────────────────────────────────┘
```

---

## Component: SimulationProgressPanel

### Props
```tsx
type SimulationProgressPanelProps = {
  simulationMonths: { month: number; year: number; label: string; abbr: string }[];
  onComplete: () => void;
  onCancel: () => void;
};
```

### Internal State Machine

Use `useState` and `useEffect` with timers to progress through phases. The phase state drives all visual changes.

```tsx
type Phase = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

// Phase durations in ms (simulated — no backend dependency)
const PHASE_DURATIONS: Record<Phase, number> = {
  0: 1200,   // Preparing
  1: 12000,  // Analyzing Month 1 (4 steps × ~3s each)
  2: 800,    // Computing Month 1
  3: 12000,  // Analyzing Month 2
  4: 800,    // Computing Month 2
  5: 12000,  // Analyzing Month 3
  6: 800,    // Computing Month 3
  7: 1500,   // Assembling forecast
};
```

During "Analyzing" phases (1, 3, 5), the 4 funnel step cells within the active month animate **sequentially** — one cell transitions from "waiting" to "analyzing" to "computed" every ~3 seconds.

When phase 7 completes, call `onComplete()` after a 1.5-second completion animation sequence.

### Elapsed Timer

A `useEffect` with `setInterval(1000)` increments a seconds counter. Display as `{seconds}s` in `font-mono text-xs text-muted-foreground` with `tabular-nums` to prevent layout shift.

---

## The Pipeline Grid

### Structure

A CSS Grid with 3 columns (one per month) and a header row + 4 funnel rows. Between columns, render arrow connectors.

```tsx
<div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] gap-0 items-stretch">
  {/* Month 1 Column */}
  <MonthColumn month={months[0]} cells={cells[0]} isActive={activeMonth === 0} isComplete={completedMonths.has(0)} />
  {/* Connector 1→2 */}
  <MonthConnector active={completedMonths.has(0)} />
  {/* Month 2 Column */}
  <MonthColumn month={months[1]} cells={cells[1]} isActive={activeMonth === 1} isComplete={completedMonths.has(1)} />
  {/* Connector 2→3 */}
  <MonthConnector active={completedMonths.has(1)} />
  {/* Month 3 Column */}
  <MonthColumn month={months[2]} cells={cells[2]} isActive={activeMonth === 2} isComplete={completedMonths.has(2)} />
</div>
```

### MonthColumn

Each month column is a rounded card with:
- Month name header
- 4 funnel step rows
- Activity count subtitle

```tsx
<div className={cn(
  "rounded-[var(--radius-lg)] border-2 p-4 transition-all",
  isActive ? "border-[var(--color-violet-400)] bg-[var(--color-bg-elevated)] shadow-md" :
  isComplete ? "border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)]" :
  "border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] opacity-60"
)} style={{
  transitionDuration: 'var(--duration-default)',
  transitionTimingFunction: 'var(--ease-default)',
}}>
  <h3 className="text-sm font-medium mb-3 text-center">{month.label}</h3>
  <div className="space-y-2.5">
    {cells.map(cell => <FunnelStepCell key={cell.stepId} {...cell} />)}
  </div>
  <p className="text-[10px] text-muted-foreground text-center mt-3">
    {activityCount} activities · {formatCurrency(spend)}
  </p>
</div>
```

### FunnelStepCell

Each cell displays one funnel stage's status within a month.

**Waiting state:**
```tsx
<div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)]">
  <div className="size-3 rounded-full border-2 shrink-0" style={{ borderColor: `${stepColor}50` }} />
  <span className="text-xs text-muted-foreground">{stepLabel}</span>
</div>
```

**Analyzing state:**
```tsx
<div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)] relative overflow-hidden">
  {/* Shimmer sweep */}
  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_ease-in-out_infinite]"
    style={{ background: `linear-gradient(90deg, transparent 0%, ${stepColor}15 50%, transparent 100%)` }}
  />
  <div className="size-3 rounded-full shrink-0 animate-pulse" style={{ backgroundColor: stepColor }} />
  <span className="text-xs relative z-10">{stepLabel}</span>
  <Sparkles className="size-3 text-[var(--color-violet-400)] ml-auto animate-pulse relative z-10" />
</div>
```

**Computed state:**
```tsx
<div className="flex items-center gap-2.5 py-1.5 px-2 rounded-[var(--radius-sm)]">
  <div className="size-3 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: stepColor }}>
    <Check className="size-2 text-white" strokeWidth={3} />
  </div>
  <span className="text-xs">{stepLabel}</span>
  <span className="text-[11px] font-mono text-emerald-600 ml-auto tabular-nums">
    +{estimatedLift.toFixed(1)}%
  </span>
</div>
```

### MonthConnector

An arrow between month columns that activates when the preceding month completes.

```tsx
<div className="flex items-center justify-center px-2 self-center">
  <div className={cn(
    "flex items-center gap-0.5 transition-all",
    active ? "text-[var(--color-violet-500)]" : "text-[var(--color-border-default)]"
  )} style={{ transitionDuration: 'var(--duration-moderate)' }}>
    <div className={cn("w-6 h-0.5 rounded-full transition-colors", active ? "bg-[var(--color-violet-500)]" : "bg-[var(--color-border-default)]")} />
    <ArrowRight className="size-4" />
  </div>
</div>
```

When `active` becomes true, briefly flash a rainbow gradient on the connecting line using a CSS animation:

```css
@keyframes rainbow-flash {
  0% { background: var(--color-violet-500); }
  33% { background: var(--color-blue-500); }
  66% { background: var(--color-teal-500); }
  100% { background: var(--color-violet-500); }
}
```

---

## Progress Bar

Use the existing Radix `Progress` component with a custom gradient indicator.

```tsx
<div className="space-y-2 mb-6">
  <div className="flex items-center justify-between">
    <p className="text-sm font-medium" aria-live="polite">{phaseLabel}</p>
    <span className="text-xs font-mono text-muted-foreground tabular-nums">{elapsedSeconds}s</span>
  </div>
  <p className="text-xs text-muted-foreground">{phaseSubLabel}</p>
  <div className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--color-bg-secondary)]"
    role="progressbar" aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100}
    aria-label="Simulation progress"
  >
    <div className="h-full rounded-full transition-all"
      style={{
        width: `${progressPercent}%`,
        background: 'linear-gradient(90deg, var(--color-blue-500), var(--color-violet-500))',
        transitionDuration: 'var(--duration-moderate)',
        transitionTimingFunction: 'var(--ease-default)',
      }}
    />
  </div>
</div>
```

### Progress Percentages by Phase

| Phase | % |
|-------|---|
| 0 | 3% |
| 1 | 15% (increases to 28% as individual steps complete) |
| 2 | 33% |
| 3 | 45% (increases to 58% as individual steps complete) |
| 4 | 63% |
| 5 | 75% (increases to 88% as individual steps complete) |
| 6 | 93% |
| 7 | 100% |

---

## Phase Labels & Copy

All copy avoids causal language. Uses "AI" (not "LLM"), "funnel model" (not "VAR/IRF").

| Phase | Label | Sub-label |
|-------|-------|-----------|
| 0 | Preparing your simulation | Loading historical patterns and forecast data |
| 1 | Analyzing {Month 1} plans | AI is reviewing your tactical plans against similar past campaigns |
| 2 | Computing {Month 1} outcomes | Estimating how your plans may flow through the funnel based on historical patterns |
| 3 | Analyzing {Month 2} plans | Building on {Month 1}'s estimated outcomes as the new baseline |
| 4 | Computing {Month 2} outcomes | Propagating estimated effects through the funnel model |
| 5 | Analyzing {Month 3} plans | Incorporating two months of estimated cumulative effects |
| 6 | Computing {Month 3} outcomes | Finalizing the 3-month estimated outlook |
| 7 | Assembling your forecast | Combining all periods into your simulation results |

---

## Activity Insight Line

At the bottom of the pipeline grid, show a contextual line that rotates through insights as each funnel step is analyzed. This adds a sense of "the AI is actually looking at your data."

```tsx
const INSIGHT_LINES = [
  "Reviewing 8 planned activities across Paid Search and Social channels",
  "Comparing against 12 similar campaigns from the past 6 months",
  "Evaluating channel mix efficiency for Problem Awareness spend",
  "Cross-referencing seasonal patterns from prior Q2 periods",
  "Assessing how Brand Awareness momentum compounds into Consideration",
  "Estimating conversion rates based on historical funnel flow patterns",
  "Checking for diminishing returns at current spend levels",
  "Analyzing interaction effects between concurrent campaigns",
  "Weighting recent performance trends more heavily than older data",
  "Factoring in planned promotional activity impact on conversion",
  "Evaluating cross-channel synergies in your media mix",
  "Calibrating confidence intervals based on data consistency",
];
```

Display one line at a time, fading between them every 3 seconds:

```tsx
<p className="text-[11px] text-muted-foreground/70 italic text-center mt-4 h-4 transition-opacity"
  style={{ transitionDuration: 'var(--duration-default)' }}>
  {currentInsight}
</p>
```

---

## Completion Sequence

When phase 7 finishes, run a 1.5-second completion animation before calling `onComplete()`:

### Step 1 (0-400ms): Rainbow border pulse
The card's `border-color` transitions through a rainbow sequence:
```tsx
// Use Framer Motion's animate
<motion.div
  animate={{ borderColor: ['var(--color-violet-300)', 'var(--color-blue-400)', 'var(--color-teal-400)', 'var(--color-amber-400)', 'var(--color-violet-400)'] }}
  transition={{ duration: 0.8, ease: 'easeInOut' }}
>
```

### Step 2 (400-1000ms): Summary preview
Three key numbers fade in below the pipeline grid:

```tsx
<div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-[var(--color-border-default)]">
  <div className="text-center">
    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Expected Revenue</p>
    <p className="text-xl font-mono tabular-nums mt-1">$1.2M</p>
  </div>
  <div className="text-center">
    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">New Accounts</p>
    <p className="text-xl font-mono tabular-nums mt-1">847</p>
  </div>
  <div className="text-center">
    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Total Investment</p>
    <p className="text-xl font-mono tabular-nums mt-1">$142k</p>
  </div>
</div>
```

These use mock values (seeded by month/year for consistency, same pattern as the rest of SimulationsSection).

### Step 3 (1000-1500ms): Crossfade out
The entire panel fades to `opacity: 0` over 500ms, then `onComplete()` is called.

---

## Sidebar Updates During Simulation

Replace the spinner in `SimulationSidebar` with a richer compact status:

```tsx
{simulating && (
  <div className="space-y-4 py-2">
    {/* Animated icon */}
    <div className="flex justify-center">
      <div className="size-12 rounded-full bg-[var(--color-violet-100)] flex items-center justify-center">
        <FlaskConical className="size-5 text-[var(--color-violet-500)] animate-pulse" />
      </div>
    </div>

    {/* Phase label */}
    <p className="text-xs text-center font-medium">{shortPhaseLabel}</p>
    <p className="text-[11px] text-muted-foreground text-center">{phaseSubLabel}</p>

    {/* Mini progress */}
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
      <div className="h-full rounded-full" style={{
        width: `${progressPercent}%`,
        background: 'linear-gradient(90deg, var(--color-blue-500), var(--color-violet-500))',
        transition: 'width var(--duration-moderate) var(--ease-default)',
      }} />
    </div>

    {/* Timer */}
    <p className="text-center text-xs font-mono text-muted-foreground tabular-nums">{elapsedSeconds}s elapsed</p>

    {/* Cancel */}
    <Button variant="ghost" size="sm" onClick={onCancel} className="w-full text-xs">
      Cancel
    </Button>
  </div>
)}
```

Short phase labels for sidebar (space-constrained):

| Phase | Short Label |
|-------|-------------|
| 0 | Preparing... |
| 1 | Analyzing {Month 1 abbr}... |
| 2 | Computing {Month 1 abbr}... |
| 3 | Analyzing {Month 2 abbr}... |
| 4 | Computing {Month 2 abbr}... |
| 5 | Analyzing {Month 3 abbr}... |
| 6 | Computing {Month 3 abbr}... |
| 7 | Assembling forecast... |

---

## Custom CSS Animations

Add these to the component or to `index.css`:

```css
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}

@keyframes rainbow-border {
  0%, 100% { border-color: var(--color-violet-300); }
  25% { border-color: var(--color-blue-400); }
  50% { border-color: var(--color-teal-400); }
  75% { border-color: var(--color-amber-400); }
}

@media (prefers-reduced-motion: reduce) {
  .animate-pulse, [class*="animate-"] {
    animation: none !important;
  }
  .transition-all, .transition-opacity, .transition-colors {
    transition-duration: 0ms !important;
  }
}
```

---

## Funnel Stage Constants

Reuse the same constants already defined in `SimulationsSection`:

```tsx
const FUNNEL_STEPS = [
  { id: 'problem-awareness', label: 'Problem Awareness', objective: 'Problem Awareness', color: '#3B82F6' },
  { id: 'brand-awareness', label: 'Brand Awareness', objective: 'Brand Awareness', color: '#6366F1' },
  { id: 'consideration', label: 'Consideration', objective: 'Consideration', color: '#F59E0B' },
  { id: 'conversion', label: 'Conversion', objective: 'Conversion', color: '#2EC4B6' },
];
```

---

## Mock Estimated Lift Values

Generate deterministic mock lift values for the computed state (same seeded random pattern as the rest of the file):

```tsx
function getMockLift(monthIndex: number, stepIndex: number): number {
  const seed = (monthIndex + 1) * 1000 + stepIndex * 100;
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  const rand = x - Math.floor(x);
  return +(1.5 + rand * 6).toFixed(1); // Range: 1.5% to 7.5%
}
```

---

## Accessibility

- Progress bar: `role="progressbar"`, `aria-valuenow`, `aria-valuemin={0}`, `aria-valuemax={100}`, `aria-label="Simulation progress"`
- Phase label container: `aria-live="polite"` so screen readers announce phase changes
- Each computed cell's check icon: include `aria-label="Complete"` on the icon
- Elapsed timer: `aria-hidden="true"`
- Cancel button: standard focus ring via existing button component
- All cell states use text labels alongside color indicators — color is never the sole state differentiator
- `prefers-reduced-motion: reduce` — disable all pulsing, shimmer, and animate classes

---

## Summary of Behavioral Requirements

1. **Start**: When `simulating` becomes true, mount the panel at phase 0
2. **Progress**: Advance through phases 0-7 using timers, animating individual funnel step cells sequentially within each "Analyzing" phase
3. **Insight rotation**: Cycle through contextual insight lines every 3 seconds
4. **Completion**: Run the 1.5s celebration sequence (rainbow pulse → summary numbers → fade out), then call `onComplete()`
5. **Cancel**: Immediately unmount the panel and call `onCancel()`
6. **Never blocks**: All animations are CSS-only or requestAnimationFrame-based. No heavy JS computation.

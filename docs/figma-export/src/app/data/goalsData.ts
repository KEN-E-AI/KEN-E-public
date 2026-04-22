/* ========== Goals Data Layer ========== */
/* Mock data for config_funnel_mapping, historic actuals, and goal types */

export const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const MONTHS_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/* ---- Current month anchor ---- */
export const CURRENT_MONTH = 2; // March (0-indexed)
export const CURRENT_YEAR = 2026;

/* ---- Funnel stages (shared across the app) ---- */
export interface FunnelStage {
  id: string;
  label: string;
  color: string;
}

export const FUNNEL_STAGES: FunnelStage[] = [
  { id: 'problem-awareness', label: 'Problem Awareness', color: '#3B82F6' },
  { id: 'brand-awareness', label: 'Brand Awareness', color: '#6366F1' },
  { id: 'consideration', label: 'Consideration', color: '#F59E0B' },
  { id: 'conversion', label: 'Conversion', color: '#2EC4B6' },
];

/* ---- config_funnel_mapping (mock) ---- */
export interface FunnelMapping {
  stage: string;
  kpi_name: string;
  display_name: string;
}

export const CONFIG_FUNNEL_MAPPING: FunnelMapping[] = [
  { stage: 'Problem Awareness', kpi_name: 'unbranded_search', display_name: 'Unbranded Search' },
  { stage: 'Brand Awareness', kpi_name: 'branded_search', display_name: 'Branded Search' },
  { stage: 'Consideration', kpi_name: 'pdp_views', display_name: 'PDP Views' },
  { stage: 'Conversion', kpi_name: 'first_purchases', display_name: 'First Purchases' },
];

/* ---- history_funnel_mapping (mock — change-event log) ---- */
export interface HistoricFunnelMapping {
  effective_date: string; // YYYY-MM-DD
  stage: string;
  kpi_name: string;
  display_name: string;
}

export const HISTORY_FUNNEL_MAPPING: HistoricFunnelMapping[] = [
  { effective_date: '2025-01-01', stage: 'Problem Awareness', kpi_name: 'unbranded_search', display_name: 'Unbranded Search' },
  { effective_date: '2025-01-01', stage: 'Brand Awareness', kpi_name: 'branded_search', display_name: 'Branded Search' },
  { effective_date: '2025-01-01', stage: 'Consideration', kpi_name: 'pdp_views', display_name: 'PDP Views' },
  { effective_date: '2025-01-01', stage: 'Conversion', kpi_name: 'first_purchases', display_name: 'First Purchases' },
  // Mapping change in Sep 2025:
  { effective_date: '2025-09-01', stage: 'Problem Awareness', kpi_name: 'organic_impressions', display_name: 'Organic Impressions' },
];

/** Resolve which KPI was mapped to a stage for a given month */
export function getKpiForStageMonth(stage: string, month: number, year: number): { kpi_name: string; display_name: string } {
  const firstOfMonth = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const matching = HISTORY_FUNNEL_MAPPING
    .filter(h => h.stage === stage && h.effective_date <= firstOfMonth)
    .sort((a, b) => b.effective_date.localeCompare(a.effective_date));

  if (matching.length > 0) {
    return { kpi_name: matching[0].kpi_name, display_name: matching[0].display_name };
  }
  // Fallback to current mapping
  const current = CONFIG_FUNNEL_MAPPING.find(m => m.stage === stage);
  return current ? { kpi_name: current.kpi_name, display_name: current.display_name } : { kpi_name: 'unknown', display_name: 'Unknown' };
}

/* ---- Historic actuals (seeded mock data) ---- */
export function generateActualValue(stageId: string, month: number, year: number): number {
  const seed = year * 1000 + month * 10;
  const rand = (j: number) => {
    const x = Math.sin(seed * 9301 + j * 49297 + 233280) * 49297;
    return x - Math.floor(x);
  };

  const stageMultipliers: Record<string, { base: number; variance: number; seedOffset: number }> = {
    'problem-awareness': { base: 85000, variance: 40000, seedOffset: 10 },
    'brand-awareness': { base: 45000, variance: 20000, seedOffset: 20 },
    'consideration': { base: 18000, variance: 8000, seedOffset: 30 },
    'conversion': { base: 1200, variance: 600, seedOffset: 40 },
  };

  const cfg = stageMultipliers[stageId] || stageMultipliers['problem-awareness'];
  return Math.round(cfg.base + rand(cfg.seedOffset) * cfg.variance);
}

/* ---- Historic goals (mock — some months have goals, some don't) ---- */
export interface HistoricGoal {
  stageId: string;
  month: number;
  year: number;
  target: number;
}

const MOCK_HISTORIC_GOALS: HistoricGoal[] = [
  // 2025 Q3-Q4 goals
  { stageId: 'problem-awareness', month: 6, year: 2025, target: 90000 },
  { stageId: 'brand-awareness', month: 6, year: 2025, target: 48000 },
  { stageId: 'consideration', month: 6, year: 2025, target: 20000 },
  { stageId: 'conversion', month: 6, year: 2025, target: 1400 },

  { stageId: 'problem-awareness', month: 7, year: 2025, target: 92000 },
  { stageId: 'brand-awareness', month: 7, year: 2025, target: 50000 },
  { stageId: 'consideration', month: 7, year: 2025, target: 21000 },
  { stageId: 'conversion', month: 7, year: 2025, target: 1450 },

  // Aug has no goals (to demo the "—" state)

  { stageId: 'problem-awareness', month: 9, year: 2025, target: 95000 },
  { stageId: 'brand-awareness', month: 9, year: 2025, target: 52000 },
  { stageId: 'consideration', month: 9, year: 2025, target: 22000 },
  { stageId: 'conversion', month: 9, year: 2025, target: 1500 },

  { stageId: 'problem-awareness', month: 10, year: 2025, target: 98000 },
  { stageId: 'brand-awareness', month: 10, year: 2025, target: 53000 },
  { stageId: 'consideration', month: 10, year: 2025, target: 23000 },
  { stageId: 'conversion', month: 10, year: 2025, target: 1550 },

  { stageId: 'problem-awareness', month: 11, year: 2025, target: 100000 },
  { stageId: 'brand-awareness', month: 11, year: 2025, target: 55000 },
  { stageId: 'consideration', month: 11, year: 2025, target: 24000 },
  { stageId: 'conversion', month: 11, year: 2025, target: 1600 },

  // 2026 Jan & Feb
  { stageId: 'problem-awareness', month: 0, year: 2026, target: 102000 },
  { stageId: 'brand-awareness', month: 0, year: 2026, target: 56000 },
  { stageId: 'consideration', month: 0, year: 2026, target: 25000 },
  { stageId: 'conversion', month: 0, year: 2026, target: 1650 },

  { stageId: 'problem-awareness', month: 1, year: 2026, target: 105000 },
  { stageId: 'brand-awareness', month: 1, year: 2026, target: 58000 },
  { stageId: 'consideration', month: 1, year: 2026, target: 26000 },
  { stageId: 'conversion', month: 1, year: 2026, target: 1700 },
];

export function getHistoricGoal(stageId: string, month: number, year: number): number | null {
  const found = MOCK_HISTORIC_GOALS.find(g => g.stageId === stageId && g.month === month && g.year === year);
  return found ? found.target : null;
}

/* ---- Goal key helper ---- */
export function goalKey(stageId: string, month: number, year: number): string {
  return `${stageId}-${month}-${year}`;
}

/* ---- Historic month range ---- */
/** Returns past months with actual data (going back ~12 months from current) */
export function getHistoricMonths(): { month: number; year: number }[] {
  const months: { month: number; year: number }[] = [];
  // Go back 12 months from current (not including current)
  for (let i = 12; i >= 1; i--) {
    let m = CURRENT_MONTH - i;
    let y = CURRENT_YEAR;
    while (m < 0) { m += 12; y -= 1; }
    months.push({ month: m, year: y });
  }
  return months;
}

/** Returns current + next 2 months */
export function getFutureMonths(): { month: number; year: number }[] {
  const months: { month: number; year: number }[] = [];
  for (let i = 0; i < 3; i++) {
    let m = CURRENT_MONTH + i;
    let y = CURRENT_YEAR;
    if (m > 11) { m -= 12; y += 1; }
    months.push({ month: m, year: y });
  }
  return months;
}

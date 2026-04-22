/* ========== Diagnostics Data & Types ========== */

export type HealthStatus = 'green' | 'yellow' | 'red';
export type IssueSeverity = 'warning' | 'error';

export interface HealthIssue {
  id: string;
  severity: IssueSeverity;
  summary: string;
  action: string;
  technicalDetail: string;
  defaultExpanded?: boolean;
}

export interface StatCard {
  id: string;
  label: string;
  value: string;
  tooltip?: string;
  annotation?: string;
  accentColor: string;
}

export interface AdfRow {
  stage: string;
  pValue: number;
  status: 'Stable' | 'Unstable trend';
}

export interface ResidualRow {
  stage: string;
  autocorrelation: 'No issues' | 'Patterns found';
  durbinWatson: number;
  normality: 'Normal' | 'Irregular';
}

export interface DiagnosticsData {
  healthStatus: HealthStatus;
  healthLabel: string;
  structuralBreakDetected: boolean;
  issues: HealthIssue[];
  statCards: StatCard[];
  adfTests: AdfRow[];
  residualDiagnostics: ResidualRow[];
}

/* Funnel accent colors */
const FUNNEL_COLORS = [
  '#8b5cf6', // violet - Problem Awareness
  '#3b82f6', // blue - Brand Awareness
  '#14b8a6', // teal - Consideration
  '#f59e0b', // amber - Conversion
];

export const MOCK_DIAGNOSTICS: DiagnosticsData = {
  healthStatus: 'yellow',
  healthLabel: 'Attention Needed',
  structuralBreakDetected: false,

  issues: [
    {
      id: 'issue-1',
      severity: 'warning',
      summary:
        'Brand Awareness is showing an unstable trend, which may reduce forecast reliability for this part of the funnel.',
      action:
        'Consider re-estimating after 4-6 more weeks of data. If the issue persists, escalate to your data science team.',
      technicalDetail:
        'Brand Awareness failed the ADF stationarity test (p=0.1247). The null hypothesis of a unit root could not be rejected at the 5% level.',
      defaultExpanded: false,
    },
    {
      id: 'issue-2',
      severity: 'warning',
      summary:
        "The model's predictions for Consideration have patterns in their errors, suggesting the model is missing something systematic.",
      action:
        'This may resolve when the model is re-estimated with more data. If it persists, ask your data science team about adding events or adjusting the lag order.',
      technicalDetail:
        'Consideration has significant residual autocorrelation (Durbin-Watson = 1.3842). Values far from 2.0 indicate serial correlation.',
      defaultExpanded: true,
    },
  ],

  statCards: [
    {
      id: 'last-estimated',
      label: 'Last Estimated',
      value: 'Mar 25, 2026, 2:30 PM',
      accentColor: FUNNEL_COLORS[0],
    },
    {
      id: 'lag-order',
      label: 'Lag Order',
      value: '3',
      tooltip:
        'Number of past weekly periods used as predictors. Selected automatically by minimizing AIC.',
      accentColor: FUNNEL_COLORS[1],
    },
    {
      id: 'model-frequency',
      label: 'Model Frequency',
      value: 'Weekly',
      accentColor: FUNNEL_COLORS[2],
    },
    {
      id: 'observations',
      label: 'Observations',
      value: '104',
      accentColor: FUNNEL_COLORS[3],
    },
    {
      id: 'aic',
      label: 'AIC',
      value: '-14.32',
      annotation: '(selected)',
      accentColor: FUNNEL_COLORS[0],
    },
    {
      id: 'bic',
      label: 'BIC',
      value: '-13.87',
      accentColor: FUNNEL_COLORS[1],
    },
    {
      id: 'exog-columns',
      label: 'Exog Columns',
      value: '5',
      annotation: '(2 pulse)',
      tooltip:
        'Total exogenous variables in the model. Includes 2 pulse intensity column(s) with smoothing alpha=0.3.',
      accentColor: FUNNEL_COLORS[2],
    },
  ],

  adfTests: [
    { stage: 'Problem Awareness', pValue: 0.0087, status: 'Stable' },
    { stage: 'Brand Awareness', pValue: 0.1247, status: 'Unstable trend' },
    { stage: 'Consideration', pValue: 0.0342, status: 'Stable' },
    { stage: 'Conversion', pValue: 0.0156, status: 'Stable' },
  ],

  residualDiagnostics: [
    { stage: 'Problem Awareness', autocorrelation: 'No issues', durbinWatson: 2.0134, normality: 'Normal' },
    { stage: 'Brand Awareness', autocorrelation: 'No issues', durbinWatson: 1.8756, normality: 'Normal' },
    { stage: 'Consideration', autocorrelation: 'Patterns found', durbinWatson: 1.3842, normality: 'Irregular' },
    { stage: 'Conversion', autocorrelation: 'No issues', durbinWatson: 2.1203, normality: 'Normal' },
  ],
};

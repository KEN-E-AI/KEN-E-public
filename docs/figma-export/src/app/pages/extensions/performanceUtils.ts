import type { PerformanceMetric } from '../../data/mockData';

export function isMetricOnTarget(metric: PerformanceMetric): boolean {
  if (metric.name === 'Cost Per Acquisition') return metric.value <= metric.target;
  return metric.value >= metric.target;
}

export function getOnTargetCount(metrics: PerformanceMetric[]): number {
  return metrics.filter(isMetricOnTarget).length;
}

export function getBelowTargetMetrics(metrics: PerformanceMetric[]): PerformanceMetric[] {
  return metrics.filter((m) => !isMetricOnTarget(m));
}

export function formatMetricValue(metric: PerformanceMetric): string {
  if (metric.unit === '%') return `${metric.value}%`;
  if (metric.unit === 'USD') return `$${metric.value}`;
  return metric.value.toLocaleString();
}

export function formatTargetValue(metric: PerformanceMetric): string {
  if (metric.unit === '%') return `${metric.target}%`;
  if (metric.unit === 'USD') return `$${metric.target}`;
  return metric.target.toLocaleString();
}

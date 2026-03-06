# Alerting policy: fires when p95 API latency exceeds 5 seconds
# for 5 minutes on any /api/v1/* route.

resource "google_monitoring_alert_policy" "api_latency_p95" {
  display_name = "API Latency p95 > 5s - Production"
  combiner     = "OR"

  conditions {
    display_name = "p95 latency > 5000ms for /api/v1/* routes"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\" AND metric.label.route=monitoring.regex.full_match(\"/api/v1/.*\")"
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_95"
        group_by_fields      = ["metric.label.route"]
      }
    }
  }

  notification_channels = var.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }
}

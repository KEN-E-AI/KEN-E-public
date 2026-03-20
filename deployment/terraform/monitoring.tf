# Log-based distribution metric for HTTP request latency.
# Captures structured logs from LatencyMiddleware and exposes them
# as a Cloud Monitoring distribution metric with route/method labels.

resource "google_logging_metric" "http_request_duration" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "api/http_request_duration_ms"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"HTTP request completed\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"

    labels {
      key         = "route"
      value_type  = "STRING"
      description = "API route pattern"
    }

    labels {
      key         = "method"
      value_type  = "STRING"
      description = "HTTP method"
    }
  }

  value_extractor = "EXTRACT(jsonPayload.duration_ms)"

  label_extractors = {
    "route"  = "EXTRACT(jsonPayload.route)"
    "method" = "EXTRACT(jsonPayload.method)"
  }

  bucket_options {
    explicit_buckets {
      bounds = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]
    }
  }
}

# Cloud Monitoring dashboard for API latency.
# Shows latency heatmap, p50/p95/p99 percentiles, and request rate per route.

resource "google_monitoring_dashboard" "api_latency" {
  for_each       = local.deploy_project_ids
  project        = each.value
  dashboard_json = jsonencode({
    displayName = "API Latency - ${each.key}"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 12
          height = 4
          widget = {
            title = "Request Latency Distribution (Heatmap)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\""
                  }
                }
                plotType = "HEATMAP"
              }]
              yAxis = {
                label = "Latency (ms)"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 12
          height = 4
          widget = {
            title = "p50 / p95 / p99 Latency by Route"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_50"
                        groupByFields      = ["metric.label.route"]
                      }
                    }
                  }
                  plotType   = "LINE"
                  legendTemplate = "p50 $${metric.label.route}"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_95"
                        groupByFields      = ["metric.label.route"]
                      }
                    }
                  }
                  plotType   = "LINE"
                  legendTemplate = "p95 $${metric.label.route}"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_99"
                        groupByFields      = ["metric.label.route"]
                      }
                    }
                  }
                  plotType   = "LINE"
                  legendTemplate = "p99 $${metric.label.route}"
                }
              ]
              yAxis = {
                label = "Latency (ms)"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 8
          width  = 12
          height = 4
          widget = {
            title = "Request Rate by Route"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/api/http_request_duration_ms\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.route"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Requests / sec"
              }
            }
          }
        }
      ]
    }
  })
}

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
  for_each = local.deploy_project_ids
  project  = each.value

  # Cloud Monitoring's API normalizes dashboard JSON on read (strips
  # default xPos/yPos, adds an etag, returns explicit defaults like
  # targetAxis="Y1" / scale="LINEAR"), so the round-trip never matches
  # the input. Ignore the field entirely — re-applying changes requires
  # `terraform state taint` or temporarily removing this block.
  lifecycle {
    ignore_changes = [dashboard_json]
  }

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

# ---------------------------------------------------------------------------
# Per-turn dispatch observability (AH-68)
# Log-based metrics for config cache, agent cache, MCP pool, and dispatch
# errors emitted by specialist_runtime, mcp_pool, and config_cache modules.
# ---------------------------------------------------------------------------

resource "google_logging_metric" "config_cache_hit_rate" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "agentic_harness/config_cache_hit_rate"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"config_cache_read\" AND jsonPayload.cache_hit=true"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "BOOLEAN"
  }
}

resource "google_logging_metric" "agent_cache_hit_rate" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "agentic_harness/agent_cache_hit_rate"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"specialist_agent_resolved\" AND jsonPayload.agent_cache_hit=true"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "BOOLEAN"
  }
}

resource "google_logging_metric" "mcp_pool_cache_hit_rate" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "agentic_harness/mcp_pool_cache_hit_rate"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"mcp_pool_checkout\" AND jsonPayload.cache_hit=true"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "BOOLEAN"
  }
}

resource "google_logging_metric" "mcp_pool_size" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "agentic_harness/mcp_pool_size"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"mcp_pool_checkout\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  value_extractor = "EXTRACT(jsonPayload.pool_size_after)"
}

resource "google_logging_metric" "dispatch_error_count" {
  for_each = local.deploy_project_ids
  project  = each.value

  name   = "agentic_harness/dispatch_error_count"
  filter = "resource.type=\"cloud_run_revision\" AND severity=\"ERROR\" AND (jsonPayload.message=~\"Failed to build toolset|Unexpected error checking out MCP toolset|mcp_pool_checkout_timeout\")"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# Cloud Monitoring dashboard for per-turn dispatch caches and pool health.

resource "google_monitoring_dashboard" "per_turn_dispatch" {
  for_each = local.deploy_project_ids
  project  = each.value

  lifecycle {
    ignore_changes = [dashboard_json]
  }

  dashboard_json = jsonencode({
    displayName = "Per-Turn Dispatch — ${each.key}"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Config Cache Hit Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/agentic_harness/config_cache_hit_rate\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Hits / sec"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Agent Cache Hit Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/agentic_harness/agent_cache_hit_rate\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Hits / sec"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "MCP Pool Cache Hit Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/agentic_harness/mcp_pool_cache_hit_rate\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Hits / sec"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "MCP Pool Size"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/agentic_harness/mcp_pool_size\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Pool entries"
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
            title = "Dispatch Error Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/agentic_harness/dispatch_error_count\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = {
                label = "Errors / sec"
              }
            }
          }
        }
      ]
    }
  })
}

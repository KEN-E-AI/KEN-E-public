# Google Cloud Memorystore (Redis) for production environment

module "memorystore" {
  source = "../../modules/memorystore"
  
  instance_name  = "ken-e-production-cache"
  display_name   = "KEN-E Production Redis Cache"
  tier           = "STANDARD_HA"  # High availability for production
  memory_size_gb = 5
  
  zone             = var.zone
  alternative_zone = var.alternative_zone
  network_id       = data.google_compute_network.default.id
  
  environment = "production"
  
  redis_configs = {
    "maxmemory-policy"       = "allkeys-lru"
    "notify-keyspace-events" = ""
    "timeout"                = "300"
    "tcp-keepalive"         = "60"
    "maxclients"            = "10000"
  }
  
  labels = {
    team        = "kene"
    cost_center = "engineering"
    critical    = "true"
  }
}

# Grant Cloud Run service account access to Redis secrets
resource "google_secret_manager_secret_iam_member" "redis_host_access" {
  secret_id = module.memorystore.redis_host_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "redis_port_access" {
  secret_id = module.memorystore.redis_port_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Output Redis connection details for use in Cloud Build
output "redis_host" {
  description = "Redis instance IP address"
  value       = module.memorystore.host
  sensitive   = true
}

output "redis_port" {
  description = "Redis instance port"
  value       = module.memorystore.port
}

# Create monitoring alert for Redis memory usage
resource "google_monitoring_alert_policy" "redis_memory_alert" {
  display_name = "Redis Memory Usage - Production"
  combiner     = "OR"
  
  conditions {
    display_name = "Redis memory usage > 80%"
    
    condition_threshold {
      filter          = "metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\" AND resource.type=\"redis_instance\" AND resource.labels.instance_id=\"${module.memorystore.id}\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
  
  notification_channels = var.notification_channels
  
  alert_strategy {
    auto_close = "1800s"
  }
}
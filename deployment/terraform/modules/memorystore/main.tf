resource "google_redis_instance" "cache" {
  name               = var.instance_name
  tier               = var.tier
  memory_size_gb     = var.memory_size_gb
  location_id        = var.zone
  alternative_location_id = var.tier == "STANDARD_HA" ? var.alternative_zone : null

  redis_version = var.redis_version
  display_name  = var.display_name
  
  authorized_network = var.network_id
  connect_mode      = "PRIVATE_SERVICE_ACCESS"

  redis_configs = var.redis_configs

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  labels = merge(
    var.labels,
    {
      environment = var.environment
      managed_by  = "terraform"
    }
  )

  lifecycle {
    prevent_destroy = true
  }
}

# Export connection details to Secret Manager
resource "google_secret_manager_secret" "redis_host" {
  secret_id = "${var.instance_name}-redis-host"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_host" {
  secret = google_secret_manager_secret.redis_host.id
  secret_data = google_redis_instance.cache.host
}

resource "google_secret_manager_secret" "redis_port" {
  secret_id = "${var.instance_name}-redis-port"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_port" {
  secret = google_secret_manager_secret.redis_port.id
  secret_data = tostring(google_redis_instance.cache.port)
}
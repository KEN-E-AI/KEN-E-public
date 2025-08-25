# Google Cloud Memorystore (Redis) for staging environment

module "memorystore" {
  source = "../../modules/memorystore"
  
  instance_name  = "ken-e-staging-cache"
  display_name   = "KEN-E Staging Redis Cache"
  tier           = "BASIC"  # Use BASIC tier for staging to save costs
  memory_size_gb = 1
  
  zone             = var.zone
  alternative_zone = var.alternative_zone
  network_id       = data.google_compute_network.default.id
  
  environment = "staging"
  
  redis_configs = {
    "maxmemory-policy"       = "allkeys-lru"
    "notify-keyspace-events" = ""
    "timeout"                = "300"
    "tcp-keepalive"         = "60"
  }
  
  labels = {
    team        = "kene"
    cost_center = "engineering"
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
output "host" {
  description = "The IP address of the Redis instance"
  value       = google_redis_instance.cache.host
}

output "port" {
  description = "The port of the Redis instance"
  value       = google_redis_instance.cache.port
}

output "current_location_id" {
  description = "The current zone where the Redis instance is located"
  value       = google_redis_instance.cache.current_location_id
}

output "id" {
  description = "The ID of the Redis instance"
  value       = google_redis_instance.cache.id
}

output "name" {
  description = "The name of the Redis instance"
  value       = google_redis_instance.cache.name
}

output "redis_host_secret_id" {
  description = "Secret Manager secret ID for Redis host"
  value       = google_secret_manager_secret.redis_host.secret_id
}

output "redis_port_secret_id" {
  description = "Secret Manager secret ID for Redis port"
  value       = google_secret_manager_secret.redis_port.secret_id
}
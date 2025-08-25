variable "instance_name" {
  description = "Name of the Redis instance"
  type        = string
}

variable "tier" {
  description = "Service tier of the instance (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
  
  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "Tier must be either BASIC or STANDARD_HA"
  }
}

variable "memory_size_gb" {
  description = "Redis memory size in GiB"
  type        = number
  default     = 1
}

variable "zone" {
  description = "Zone where the instance will be located"
  type        = string
  default     = "us-central1-a"
}

variable "alternative_zone" {
  description = "Alternative zone for STANDARD_HA tier"
  type        = string
  default     = "us-central1-b"
}

variable "redis_version" {
  description = "Version of Redis"
  type        = string
  default     = "REDIS_7_0"
}

variable "display_name" {
  description = "Display name of the Redis instance"
  type        = string
}

variable "network_id" {
  description = "VPC network ID for the Redis instance"
  type        = string
}

variable "redis_configs" {
  description = "Redis configuration parameters"
  type        = map(string)
  default = {
    "maxmemory-policy" = "allkeys-lru"
    "notify-keyspace-events" = ""
  }
}

variable "environment" {
  description = "Environment (staging or production)"
  type        = string
}

variable "labels" {
  description = "Labels to apply to the Redis instance"
  type        = map(string)
  default     = {}
}
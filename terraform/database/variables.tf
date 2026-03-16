variable "pg_host" {
  description = "PostgreSQL host"
  type        = string
  default     = "localhost"
}

variable "pg_port" {
  description = "PostgreSQL port"
  type        = number
  default     = 5434
}

variable "pg_superuser" {
  description = "PostgreSQL superuser name"
  type        = string
  default     = "postgres"
}

variable "pg_superuser_password" {
  description = "PostgreSQL superuser password"
  type        = string
  sensitive   = true
}

variable "pg_sslmode" {
  description = "PostgreSQL SSL mode"
  type        = string
  default     = "prefer"
}

variable "app_role_name" {
  description = "Application database role name"
  type        = string
  default     = "stock_radar_app"
}

variable "app_role_password" {
  description = "Application database role password"
  type        = string
  sensitive   = true
}

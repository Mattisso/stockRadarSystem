output "database_name" {
  description = "The PostgreSQL database name"
  value       = postgresql_database.stock_radar.name
}

output "schema_name" {
  description = "The PostgreSQL schema name"
  value       = postgresql_schema.stock_radar.name
}

output "app_role_name" {
  description = "The application role name"
  value       = postgresql_role.app_role.name
}

output "database_url" {
  description = "SQLAlchemy connection string for the application"
  value       = "postgresql://${postgresql_role.app_role.name}:${var.app_role_password}@${var.pg_host}:${var.pg_port}/${postgresql_database.stock_radar.name}"
  sensitive   = true
}

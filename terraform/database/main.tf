terraform {
  required_version = ">= 1.5"

  required_providers {
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.22"
    }
  }
}

provider "postgresql" {
  host     = var.pg_host
  port     = var.pg_port
  username = var.pg_superuser
  password = var.pg_superuser_password
  sslmode  = var.pg_sslmode
}

# ── Database ────────────────────────────────────────────────────────
resource "postgresql_database" "stock_radar" {
  name              = "stock_radar"
  owner             = postgresql_role.app_role.name
  encoding          = "UTF8"
  lc_collate        = "en_US.UTF-8"
  lc_ctype          = "en_US.UTF-8"
  template          = "template0"
  connection_limit  = -1
  allow_connections = true
}

# ── Application role ────────────────────────────────────────────────
resource "postgresql_role" "app_role" {
  name     = var.app_role_name
  login    = true
  password = var.app_role_password

  lifecycle {
    ignore_changes = [password]
  }
}

# ── Schema ──────────────────────────────────────────────────────────
resource "postgresql_schema" "stock_radar" {
  name     = "stock_radar"
  database = postgresql_database.stock_radar.name
  owner    = postgresql_role.app_role.name

  depends_on = [postgresql_database.stock_radar]
}

# ── Grants ──────────────────────────────────────────────────────────
resource "postgresql_grant" "app_schema_usage" {
  database    = postgresql_database.stock_radar.name
  role        = postgresql_role.app_role.name
  schema      = postgresql_schema.stock_radar.name
  object_type = "schema"
  privileges  = ["CREATE", "USAGE"]

  depends_on = [postgresql_schema.stock_radar]
}

resource "postgresql_grant" "app_table_all" {
  database    = postgresql_database.stock_radar.name
  role        = postgresql_role.app_role.name
  schema      = postgresql_schema.stock_radar.name
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]

  depends_on = [postgresql_schema.stock_radar]
}

resource "postgresql_grant" "app_sequence_usage" {
  database    = postgresql_database.stock_radar.name
  role        = postgresql_role.app_role.name
  schema      = postgresql_schema.stock_radar.name
  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]

  depends_on = [postgresql_schema.stock_radar]
}

# ── Default privileges (for future tables created by app_role) ──────
resource "postgresql_default_privileges" "app_tables" {
  database = postgresql_database.stock_radar.name
  role     = postgresql_role.app_role.name
  schema   = postgresql_schema.stock_radar.name
  owner    = postgresql_role.app_role.name

  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]

  depends_on = [postgresql_schema.stock_radar]
}

resource "postgresql_default_privileges" "app_sequences" {
  database = postgresql_database.stock_radar.name
  role     = postgresql_role.app_role.name
  schema   = postgresql_schema.stock_radar.name
  owner    = postgresql_role.app_role.name

  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]

  depends_on = [postgresql_schema.stock_radar]
}

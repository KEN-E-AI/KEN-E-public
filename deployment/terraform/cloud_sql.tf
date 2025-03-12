# creating cloud sql instances for staging and prod
resource "google_sql_database_instance" "staging_sql" {
  name             = "genai-staging-sql"
  database_version = "MYSQL_8_0"
  region           = var.region
  project          = var.staging_project_id

  settings {
    tier              = "db-f1-micro"  # Change if a bigger instance is needed
    availability_type = "REGIONAL"
    disk_autoresize   = true
    ip_configuration {
      ipv4_enabled = true
    }
  }
}

resource "google_sql_database_instance" "prod_sql" {
  name             = "genai-prod-sql"
  database_version = "MYSQL_8_0"
  region           = var.region
  project          = var.prod_project_id

  settings {
    tier              = "db-f1-micro"
    availability_type = "REGIONAL"
    disk_autoresize   = true
    ip_configuration {
      ipv4_enabled = true
    }
  }
}

# creating sql dbs for staging and prod
resource "google_sql_database" "staging_db" {
  name     = "genai_db"
  instance = google_sql_database_instance.staging_sql.name
  project  = var.staging_project_id
}

resource "google_sql_database" "prod_db" {
  name     = "genai_db"
  instance = google_sql_database_instance.prod_sql.name
  project  = var.prod_project_id
}

# creating db users for staging and prod
resource "google_sql_user" "staging_user" {
  name     = "genai_user"
  instance = google_sql_database_instance.staging_sql.name
  project  = var.staging_project_id
  password = ""
}

resource "google_sql_user" "prod_user" {
  name     = "genai_user"
  instance = google_sql_database_instance.prod_sql.name
  project  = var.prod_project_id
  password = ""
}

# storage buckets for sql import (separate for staging & prod)
resource "google_storage_bucket" "sql_bucket_staging" {
  name          = "${var.staging_project_id}-sql-init"
  location      = var.region
  project       = var.staging_project_id
  force_destroy = true
}

resource "google_storage_bucket" "sql_bucket_prod" {
  name          = "${var.prod_project_id}-sql-init"
  location      = var.region
  project       = var.prod_project_id
  force_destroy = true
}

# upload init.sql to each bucket
resource "google_storage_bucket_object" "sql_script_staging" {
  name   = "init.sql"
  bucket = google_storage_bucket.sql_bucket_staging.name
  source = "deployment/terraform/sql/init.sql"
}

resource "google_storage_bucket_object" "sql_script_prod" {
  name   = "init.sql"
  bucket = google_storage_bucket.sql_bucket_prod.name
  source = "deployment/terraform/sql/init.sql"
}

# excute sql script on cloud sql
resource "null_resource" "import_sql" {
  depends_on = [google_storage_bucket_object.sql_script_staging, google_storage_bucket_object.sql_script_prod]

  provisioner "local-exec" {
    command = <<EOT
      gcloud sql import sql ${google_sql_database_instance.staging_sql.name} \
        gs://${google_storage_bucket.sql_bucket_staging.name}/init.sql \
        --database=genai_db --project=${var.staging_project_id}

      gcloud sql import sql ${google_sql_database_instance.prod_sql.name} \
        gs://${google_storage_bucket.sql_bucket_prod.name}/init.sql \
        --database=genai_db --project=${var.prod_project_id}
    EOT
  }
}

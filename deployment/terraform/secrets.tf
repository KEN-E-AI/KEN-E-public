resource "google_secret_manager_secret" "firebase_key_staging" {
  project = var.staging_project_id
  secret_id   = "firebase-key-staging"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "firebase_key_staging_version" {
  secret       = google_secret_manager_secret.firebase_key_staging.id
  secret_data  = file("${path.module}/keys/ken-e-staging-d58ae37ec45d.json")
}

resource "google_secret_manager_secret" "firebase_key_prod" {
  project = var.prod_project_id
  secret_id    = "firebase-key-prod"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "firebase_key_prod_version" {
  secret       = google_secret_manager_secret.firebase_key_prod.id
  secret_data  = file("${path.module}/keys/ken-e-production-d3211c0d2100.json")
}

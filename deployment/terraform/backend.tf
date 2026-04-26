terraform {
  backend "gcs" {
    bucket = "ken-e-cicd-tfstate"
    prefix = "root"
  }
}

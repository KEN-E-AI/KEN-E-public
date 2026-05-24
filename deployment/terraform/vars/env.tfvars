# Your Production Google Cloud project id
prod_project_id = "ken-e-production"

# Your Staging / Test Google Cloud project id
staging_project_id = "ken-e-staging"

# Your Google Cloud project ID that will be used to host the Cloud Build pipelines.
cicd_runner_project_id = "ken-e-cicd"

# Name of the host connection you created in Cloud Build
host_connection_name = "KEN-E_Github_Connection"

# Name of the repository you added to Cloud Build
repository_name = "KEN-E-AI-KEN-E"

# The Google Cloud region you will use to deploy the infrastructure
region = "us-central1"

telemetry_bigquery_dataset_id = "telemetry_genai_app_sample_sink"
telemetry_sink_name = "telemetry_logs_genai_app_sample"
telemetry_logs_filter = "jsonPayload.attributes.\"traceloop.association.properties.log_type\"=\"tracing\" jsonPayload.resource.attributes.\"service.name\"=\"ken-e\""

feedback_bigquery_dataset_id = "feedback_genai_app_sample_sink"
feedback_sink_name = "feedback_logs_genai_app_sample"
feedback_logs_filter = "jsonPayload.log_type=\"feedback\""

cicd_runner_sa_name = "cicd-runner"

suffix_bucket_name_load_test_results = "cicd-load-test-results"

# Architectural decision (DM-73): all Firestore index changes apply to all 3
# environments simultaneously. Previously defaulted to ken-e-dev only; expanded
# here as part of the performance_profiles bottleneck index provisioning.
# DM-PRD-06 data migration is the remaining prerequisite for staging/prod to
# serve live queries, but indexes are pre-provisioned.
firestore_index_project_ids = ["ken-e-dev", "ken-e-staging", "ken-e-production"]

# CMEK keys for skills GCS buckets (kene-skills-{env} + kene-skills-{env}-trash).
# Default is empty map (Google-managed encryption). Populate via a follow-up ops PR
# once KMS keys are provisioned — no code change required to enable CMEK.
# Format: { development = "projects/.../keyRings/.../cryptoKeys/...", staging = "...", production = "..." }
# skills_bucket_kms_key_name = {}

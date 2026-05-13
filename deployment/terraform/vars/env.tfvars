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

# Per Ken's directive: "any changes to databases are applied to all 3 environments."
# Previously defaulted to ["ken-e-dev"] only; expanded here to include staging and
# production as part of DM-73 (performance_profiles bottleneck index provisioning).
# All subsequent Firestore index deployments now target all three environments.
firestore_index_project_ids = ["ken-e-dev", "ken-e-staging", "ken-e-production"]

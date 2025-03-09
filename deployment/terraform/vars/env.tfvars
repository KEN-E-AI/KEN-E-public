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
search_engine_name = "sample-search-engine"
datastore_name = "sample-datastore"
vertexai_pipeline_sa_name = "vertexai-pipelines-sa"
pipeline_cron_schedule = "0 0 * * 0"

#The value can only be one of "global", "us" and "eu".
data_store_region = "us"

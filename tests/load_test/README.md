# Robust Load Testing for Generative AI Applications

This directory provides a comprehensive load testing framework for your Generative AI application, leveraging the power of [Locust](http://locust.io), a leading open-source load testing tool.

##  Load Testing

Before running load tests, ensure you have deployed the backend remotely.

Follow these steps to execute load tests:

**1. Deploy the Backend Remotely:**
   ```bash
   gcloud config set project <your-dev-project-id>
   make backend
   ```

**2. Create a Virtual Environment for Locust:**
   It's recommended to use a separate terminal tab and create a virtual environment for Locust to avoid conflicts with your application's Python environment.

   ```bash
   # Create and activate virtual environment
   python3 -m venv locust_env
   source locust_env/bin/activate
   
   # Install required packages
   pip install locust==2.31.1 "google-cloud-aiplatform[langchain,reasoningengine]>=1.77.0"
   ```

**3. Execute the Load Test:**
   Trigger the Locust load test with the following command:

   ```bash
   export _AUTH_TOKEN=$(gcloud auth print-access-token -q)
   locust -f tests/load_test/load_test.py \
   --headless \
   -t 30s -u 5 -r 2 \
   --csv=tests/load_test/.results/results \
   --html=tests/load_test/.results/report.html
   ```

   This command initiates a 30-second load test, simulating 2 users spawning per second, reaching a maximum of 10 concurrent users.

---

## Chat sidebar polling load test

Validates that `GET /api/v1/chat/conversations` (the Chat component's sidebar polling endpoint) sustains **1 000 concurrent simulated browser tabs polling every 5–10 s** with **p95 response time under 100 ms**. This is AC-16 from `docs/design/components/chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md` §7.

### Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_WEB_API_KEY` | Firebase web API key (not the service-account JSON). Available as `_VITE_FIREBASE_API_KEY` in Cloud Build. |
| `CHAT_LOADTEST_UID` | Firebase Auth UID of the load-test user (`chat-loadtest@ken-e-loadtest.local`). Set once by running the seed script and recording the printed UID. |
| `API_BASE_URL` | Base URL of the API to load (e.g., `https://kene-api-staging-391472102753.us-central1.run.app`). |
| `GOOGLE_CLOUD_PROJECT_ID` | GCP project ID used by the seed script to access Firestore (staging: `ken-e-staging`). |

### Step 1 — Provision the seed data

The seed script creates the load-test account (`acc_load_test`) and 200 synthetic chat sessions in Firestore. Run it once per environment; it is idempotent (safe to re-run).

```bash
export GOOGLE_CLOUD_PROJECT_ID=ken-e-staging
export ENVIRONMENT=staging
python api/scripts/seed_chat_load_test_data.py
```

On first run the script prints the load-test user's UID — record it as `CHAT_LOADTEST_UID`.

To verify the seed worked:

```bash
# Should return 20 sessions (the first page of 200) with next_cursor non-null
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://kene-api-staging-391472102753.us-central1.run.app/api/v1/chat/conversations?account_id=acc_load_test"
```

To tear down the seeded data:

```bash
python api/scripts/seed_chat_load_test_data.py --cleanup
```

Note: the Firebase Auth user is **not** deleted by `--cleanup`. If you need to delete it, use the Firebase console or `firebase auth:delete <uid>`.

### Step 2 — Run locally against staging

Install dependencies:

```bash
pip install locust==2.32.6 gevent==24.11.1 requests firebase-admin
```

Run a small local test (100 users × 1 minute):

```bash
export FIREBASE_WEB_API_KEY=<your-firebase-web-api-key>
export CHAT_LOADTEST_UID=<uid-from-seed-step>
export API_BASE_URL=https://kene-api-staging-391472102753.us-central1.run.app

locust -f tests/load_test/chat_sidebar_polling.py \
  --headless -t 1m -u 100 -r 10 \
  --csv=tests/load_test/.results/chat_sidebar \
  --html=tests/load_test/.results/chat_sidebar_report.html
```

Full-scale run (1 000 users × 6 minutes — same as staging CI):

```bash
locust -f tests/load_test/chat_sidebar_polling.py \
  --headless -t 6m -u 1000 -r 33 \
  --csv=tests/load_test/.results/chat_sidebar \
  --html=tests/load_test/.results/chat_sidebar_report.html
```

### Step 3 — Check the p95 threshold

After the Locust run, verify the gate:

```bash
python tests/load_test/check_p95_threshold.py \
  tests/load_test/.results/chat_sidebar_stats.csv \
  --threshold-ms 100 \
  --endpoint "/api/v1/chat/conversations"
```

Exit code 0 = pass. Exit code 1 = fail (p95 ≥ 100 ms or failures > 0). Exit code 2 = usage error (endpoint not found in CSV).

### Interpreting results

The stats CSV (`chat_sidebar_stats.csv`) has one row per endpoint label plus an `Aggregated` row. Columns to watch:

| Column | Meaning |
|---|---|
| `Request Count` | Total requests sent |
| `Failure Count` | Non-200 responses (must be 0 for the gate to pass) |
| `95%` | p95 latency in ms (must be < 100 for the gate to pass) |
| `Requests/s` | Throughput (healthy sign: stable and matching user count ÷ wait_time) |

The HTML report (`chat_sidebar_report.html`) shows charts over time — check for a latency spike during the first 30 s (ramp phase) that should settle once all 1 000 users are spawned.

### Reading GCS results from a staging build

After a staging Cloud Build run, results land at:

```
gs://{PROJECT_ID}-cicd-load-test-results/results-{TIMESTAMP}/
```

Download:

```bash
gsutil -m cp -r "gs://ken-e-staging-cicd-load-test-results/results-$(date +%Y%m%d)*" /tmp/load-test-results/
```

### What to do when the gate trips

If `check_p95_threshold.py` exits 1, investigate in this order:

1. **Cloud Run scaling** — check that `kene-api-staging` is not hitting `max_instances`. In the Cloud Console → Cloud Run → kene-api-staging, look at the "Instances" graph during the test window. If the instance count was capped, temporarily raise `--max-instances` and re-run. Tuning note: 1 000 users × 10 req/min ≈ 167 RPS; a single `e2-standard-2` instance at 80 concurrent requests handles ~160 RPS — two instances are the safe baseline.

2. **Firestore composite-index health** — the query relies on four composite indexes from CH-PRD-01 §4.3 (particularly `(user_id ASC, deleted_at ASC, updated_at DESC)`). In the Firestore console, check that all four indexes are `Enabled` (not `Building`). A building index causes collection-group scans that inflate p95 by 10×.

3. **Recent commits to `api/src/kene_api/chat/search.py` or `api/src/kene_api/chat/side_table.py`** — these files own the list-sessions query path. Use `git log --oneline api/src/kene_api/chat/search.py api/src/kene_api/chat/side_table.py` to find recent changes and check for unintended query fan-out.

4. **Failures (non-200 responses)** — if `Failure Count > 0`, the likely cause is a 401 (authentication issue with the load-test token) or a 404 (endpoint or account not found). Check `chat_sidebar_failures.csv` for the first failing URL and response body.

### Known limitations

- **One shared ID token** — all 1 000 simulated users authenticate as `chat-loadtest@ken-e-loadtest.local`. This is correct for a read-only polling test but would not work for per-user write-path scenarios.
- **`query` filter not exercised** — the scenario does not set the `?query=` parameter, so the post-Firestore casefold substring filter (documented in CH-PRD-02 §5.4) is not under load. A separate scenario for the `query` branch is a future follow-up.
- **200-session seed** — the seeded account has 200 sessions, capped at `limit=20` per page by the endpoint. Latency is dominated by composite-index lookup cost, not row count; a 1 000+-row stress variant is a future follow-up.
- **5-minute steady-state** — the 6-minute total run (30 s ramp + 5 min steady + 30 s drain) covers warm-cache and cold-cache phases. Longer-running soak tests are not automated.

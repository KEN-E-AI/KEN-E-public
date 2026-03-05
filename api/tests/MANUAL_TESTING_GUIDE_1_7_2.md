# Manual Testing Guide: Story 1.7.2 - Latency Metrics

## Prerequisites

- API server running locally:
  ```bash
  cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
  ```
- App URL: http://localhost:8000

## Test 1: Prometheus Metrics Endpoint Exposes Latency Histogram (AC1)

**Steps:**
1. Start the API server locally
2. Make a few requests to generate metrics data:
   ```bash
   curl http://localhost:8000/api/v1/chat/health
   curl http://localhost:8000/api/v1/health
   ```
3. Open the Prometheus metrics endpoint:
   ```bash
   curl http://localhost:8000/api/monitoring/metrics
   ```
4. Search the output for `http_request_duration_seconds`

**Expected Results:**
- [ ] The output contains `http_request_duration_seconds_bucket` entries
- [ ] Bucket boundaries include: `0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0`
- [ ] Each bucket entry has labels: `method`, `route`, `status_code`
- [ ] The `route` label uses the route pattern (e.g., `/api/v1/chat/health`) not the concrete path
- [ ] `http_request_duration_seconds_count` and `http_request_duration_seconds_sum` are present
- [ ] Histogram data allows computing p50, p95, and p99 (via Prometheus quantile functions)

## Test 2: Per-Endpoint Latency Tracking (AC1)

**Steps:**
1. Make requests to different endpoints:
   ```bash
   curl http://localhost:8000/api/v1/chat/health
   curl http://localhost:8000/api/v1/health
   curl -X POST http://localhost:8000/api/v1/firestore/health
   ```
2. Fetch Prometheus metrics:
   ```bash
   curl http://localhost:8000/api/monitoring/metrics | grep http_request_duration_seconds_bucket
   ```

**Expected Results:**
- [ ] Different routes appear as separate label values in the histogram
- [ ] Each route has its own set of bucket entries
- [ ] `method` label correctly shows GET, POST, etc.
- [ ] `status_code` label correctly shows 200, 404, etc. as appropriate

## Test 3: Slow Request Logging (AC3 - Drill-Down Support)

**Steps:**
1. Identify or create a request that takes > 1 second (e.g., a chat completion request)
2. Check the API server logs in the terminal

**Expected Results:**
- [ ] Slow requests (> 1s) produce a WARNING-level structured log entry
- [ ] Log entry contains: `component: "http"`, `action: "request"`
- [ ] Log entry contains: `duration_ms` (in milliseconds), `method`, `route`, `status_code`
- [ ] These structured logs can be filtered in Cloud Logging by time range and endpoint

## Test 4: Route Normalization (AC1, AC3)

**Steps:**
1. Make requests to parameterized endpoints with different IDs:
   ```bash
   curl http://localhost:8000/api/v1/firestore/accounts/acc_001/documents
   curl http://localhost:8000/api/v1/firestore/accounts/acc_002/documents
   ```
2. Fetch Prometheus metrics:
   ```bash
   curl http://localhost:8000/api/monitoring/metrics | grep http_request_duration_seconds_bucket
   ```

**Expected Results:**
- [ ] Both requests are tracked under the same route pattern (e.g., `/api/v1/firestore/accounts/{account_id}/documents`), NOT separate concrete paths
- [ ] This keeps label cardinality bounded and allows meaningful per-endpoint aggregation

## Test 5: Cloud Monitoring Integration (AC1, AC2, AC3)

> This test requires a deployed staging/production environment.

**Steps:**
1. Deploy the API to the staging Cloud Run instance
2. Generate traffic by using the frontend or sending API requests
3. Open Google Cloud Console > Monitoring > Metrics Explorer
4. Search for `http_request_duration_seconds` or the custom metric name
5. Check Alerting policies for p95 > 5s threshold

**Expected Results:**
- [ ] Latency histogram metrics appear in Cloud Monitoring
- [ ] Metrics are available in near real-time (< 30s delay)
- [ ] Dashboard allows filtering by endpoint (route label) and time range
- [ ] An alerting policy exists for p95 latency > 5 seconds per endpoint (AC2)
- [ ] Alert configuration includes the affected endpoint and current latency values (AC2)

## Verification Checklist Summary

| Test | What It Validates | AC |
|------|-------------------|----|
| Test 1 | Prometheus histogram exposes p50/p95/p99 latency data | AC1 |
| Test 2 | Per-endpoint tracking with method/route/status labels | AC1 |
| Test 3 | Structured logging of slow requests for drill-down | AC3 |
| Test 4 | Route normalization keeps cardinality bounded | AC1, AC3 |
| Test 5 | Cloud Monitoring dashboard, alerting, drill-down | AC1, AC2, AC3 |

# Apache Superset Integration

This document describes the integration between the Kene API and Apache Superset for metric synchronization.

## Overview

The Kene API now automatically synchronizes metric operations (create, update, delete) with Apache Superset. When you perform metric operations through the API, the corresponding changes are also applied to Superset datasets.

## Configuration

Add the following environment variables to your `.env` file:

```bash
# Apache Superset Configuration
SUPERSET_BASE_URL=https://your-superset-instance.com
SUPERSET_USERNAME=your_username
SUPERSET_PASSWORD=your_password
```

## How It Works

### Metric Creation

When creating a metric via `POST /api/v1/metrics/`:

1. **Neo4j**: Creates the metric node with relationships
2. **Superset**: If `related_dataset_id` is provided, creates the metric in the corresponding Superset dataset
3. **Response**: Returns both the Neo4j metric ID and Superset metric ID (if created)

Example request:
```json
{
    "account_id": "account_123",
    "metric_name": "total_revenue",
    "verbose_name": "Total Revenue",
    "expression": "SUM(revenue)",
    "description": "Sum of all revenue",
    "d3_format": "$,.2f",
    "related_dataset_id": 42
}
```

Example response:
```json
{
    "success": true,
    "data": {
        "metric_id": "uuid-generated-id"
    },
    "message": "Metric created successfully"
}
```

### Metric Updates

When updating a metric via `PUT /api/v1/metrics/`:

1. **Neo4j**: Updates the metric properties
2. **Superset**: If the metric has a `superset_metric_id`, synchronizes the changes
3. **Response**: Indicates whether Superset sync was successful

Example response with successful sync:
```json
{
    "success": true,
    "data": null,
    "message": "Metric updated successfully (synced with Superset)"
}
```

### Metric Deletion

When deleting a metric via `DELETE /api/v1/metrics/`:

1. **Neo4j**: Removes the metric node and relationships
2. **Superset**: If the metric has a `superset_metric_id`, deletes it from Superset
3. **Response**: Indicates whether Superset deletion was successful

## Error Handling

The integration is designed to be resilient:

- **Superset Unavailable**: If Superset is unavailable during operations, the Neo4j operations continue and warnings are logged
- **Authentication Failures**: The system will attempt to re-authenticate automatically
- **Partial Failures**: If Superset operations fail, the response message will indicate the failure while Neo4j operations succeed

## Data Model Changes

### Neo4j Schema Enhancement

The `CALCULATED_FROM` relationship between Metric and Dataset nodes now stores the Superset metric ID:

```cypher
CREATE (metric:Metric {
    metric_id: "uuid",
    // ... other metric properties
})
CREATE (dataset:Dataset {
    dataset_id: 42,
    // ... other dataset properties  
})
CREATE (metric)-[:CALCULATED_FROM {superset_metric_id: 123}]->(dataset)
```

This approach provides better data modeling by:
- Keeping the Superset ID with the relationship that represents the connection to Superset
- Avoiding unnecessary exposure of Superset IDs in API responses
- Maintaining clean separation between Neo4j graph structure and external system references

## API Endpoints

All existing metric endpoints have been enhanced with Superset integration:

- `GET /api/v1/metrics/` - Returns metrics with Superset IDs
- `POST /api/v1/metrics/` - Creates metrics in both systems
- `PUT /api/v1/metrics/` - Updates metrics in both systems  
- `DELETE /api/v1/metrics/` - Deletes metrics from both systems

## Monitoring and Logging

The integration logs important events:

- **Success**: Metric operations and Superset synchronization
- **Warnings**: Superset failures that don't prevent Neo4j operations
- **Errors**: Critical failures that prevent operations

Check application logs for messages like:
```
INFO: Successfully created metric test_metric in dataset 42
WARNING: Failed to update metric in Superset: Authentication failed
```

## Prerequisites

1. **Superset Instance**: You need access to a running Apache Superset instance
2. **API Access**: Your Superset instance must have API access enabled
3. **Credentials**: Valid username/password for Superset authentication
4. **Datasets**: The datasets referenced by `related_dataset_id` must exist in Superset

## Limitations

1. **Dataset Dependency**: Metrics can only be created in Superset if they reference an existing dataset
2. **Authentication**: Uses username/password authentication (not API tokens)
3. **Error Recovery**: If Superset operations fail, manual reconciliation may be needed
4. **Metric Types**: Currently creates metrics with type "count" in Superset

## Testing

Run the integration test to verify everything is working:

```bash
cd /path/to/api
python check_superset_integration.py
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify `SUPERSET_USERNAME` and `SUPERSET_PASSWORD` are correct
   - Check if the Superset user has necessary permissions

2. **Dataset Not Found**
   - Ensure the `related_dataset_id` exists in Superset
   - Verify the dataset is accessible to the authenticated user

3. **Connection Issues**
   - Check `SUPERSET_BASE_URL` is correct and accessible
   - Verify network connectivity to Superset instance

4. **Missing Superset Metric ID**
   - Older metrics may not have `superset_metric_id`
   - These will not sync with Superset until manually updated

### Manual Reconciliation

If metrics get out of sync between Neo4j and Superset:

1. Use the Superset API to find metrics by name
2. Update Neo4j metric nodes with the correct `superset_metric_id`
3. Test the sync by performing an update operation

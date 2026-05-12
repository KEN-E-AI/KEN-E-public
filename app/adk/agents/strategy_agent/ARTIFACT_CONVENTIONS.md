# Artifact Naming Conventions for Strategy Agent System

## Overview
This document describes the artifact naming conventions used in the KEN-E Strategy Agent System for managing uploaded documents and generated strategy artifacts.

## Artifact Prefixes

### Uploaded Strategy Documents
**Prefix**: `input_strategy_`

Uploaded business strategy documents from the account creation form are stored as artifacts with this prefix. This allows agents to easily identify and load existing strategy documents that should inform their analysis.

**Examples**:
- `input_strategy_business_plan_2024.pdf`
- `input_strategy_marketing_strategy.docx`
- `input_strategy_competitive_analysis.pdf`

**Usage in Agents**:
```python
# List all artifacts
artifacts = context.list_artifacts()

# Filter for uploaded strategy documents
strategy_docs = [a for a in artifacts if a.filename.startswith('input_strategy_')]

# Load each document
for doc in strategy_docs:
    content = context.load_artifact(doc.filename)
    # Process content...
```

### Generated Strategy Documents
Generated strategy documents are stored in Firestore collections with the naming pattern:
- Collection: `accounts/{account_id}/strategy_docs`
- Document IDs:
  - `business_strategy`
  - `competitive_strategy`
  - `customer_strategy`
  - `marketing_strategy`
  - `brand_guidelines`

## Artifact Storage

### GCS Bucket Structure
```
gs://ken-e-{environment}-files-{region}/
  accounts/{account_id}/
    artifacts/           # ADK artifacts namespace
      input_strategy_*   # Uploaded strategy documents
    strategy_inputs/     # Original uploaded files
      {filename1}.pdf
      {filename2}.docx
```

### Environment-Based Buckets
- **Development**: `ken-e-development-files-us` / `ken-e-development-files-eu`
- **Staging**: `ken-e-staging-files-us` / `ken-e-staging-files-eu`
- **Production**: `ken-e-production-files-us` / `ken-e-production-files-eu`

## Artifact Service Configuration

### GcsArtifactService
When uploaded documents are present:
```python
artifact_service = GcsArtifactService(
    bucket_name=bucket_name,
    namespace=f"accounts/{account_id}/artifacts"
)
```

### InMemoryArtifactService
When no documents are uploaded or as fallback:
```python
artifact_service = InMemoryArtifactService()
```

## Data Flow

1. **Upload**: Files uploaded through account creation form → GCS bucket
2. **Convert**: GCS files downloaded and converted to ADK artifacts
3. **Prefix**: Artifacts saved with `input_strategy_` prefix
4. **Access**: Agents list and load artifacts by prefix
5. **Analyze**: Agents extract insights from uploaded documents
6. **Generate**: New strategy documents created with alignment to uploaded content

## Best Practices

1. **Consistent Naming**: Always use the `input_strategy_` prefix for uploaded documents
2. **Error Handling**: Fall back to InMemoryArtifactService if GCS fails
3. **Logging**: Log artifact operations for debugging
4. **Testing**: Mock artifact services in unit tests
5. **Documentation**: Include artifact access examples in agent instructions

## Implementation Files

- **Artifact Utilities**: `app/adk/agents/strategy_agent/artifact_utils.py`
- **Orchestrator**: `app/adk/agents/strategy_agent/orchestrator.py`
- **Agent Instructions**: `app/adk/agents/strategy_agent/agents.py`
- **Account Service**: `api/src/kene_api/services/account_creation_service.py`

## Testing

Artifacts can be mocked in tests:
```python
mock_artifact_service = Mock()
mock_artifact_service.list_artifacts.return_value = [
    {"filename": "input_strategy_test.pdf", "version": 1}
]
mock_artifact_service.load_artifact.return_value = Part.from_text("Test content")
```

## Migration Notes

When refactoring from inline code to utility functions:
1. Preserve the `input_strategy_` prefix
2. Maintain backward compatibility with existing artifacts
3. Ensure namespace structure remains consistent
4. Test with both GCS and InMemory services
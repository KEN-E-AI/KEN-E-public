# Industry Keywords Backend Implementation Plan

## Overview

This document outlines the plan to implement backend API endpoints for managing industry keywords in the KEN-E platform. These endpoints will support the admin functionality for configuring default keywords for each industry.

## API Endpoints

### 1. GET /api/v1/industry-keywords

**Purpose**: Retrieve all industry keywords

**Response Format**:

```json
[
  {
    "industry": "Technology",
    "keywords": [
      "software",
      "AI",
      "cloud computing",
      "cybersecurity",
      "blockchain"
    ]
  },
  {
    "industry": "Healthcare",
    "keywords": [
      "telemedicine",
      "patient care",
      "medical devices",
      "pharmaceuticals"
    ]
  }
]
```

**Implementation Details**:

- No authentication required for reading (public data)
- Returns array of IndustryKeyword objects
- Empty array if no keywords exist

### 2. PUT /api/v1/industry-keywords/{industry}

**Purpose**: Create or update keywords for a specific industry

**Request Body**:

```json
{
  "keywords": ["keyword1", "keyword2", "keyword3"]
}
```

**Response**: 200 OK with updated industry keywords

```json
{
  "industry": "Technology",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}
```

**Implementation Details**:

- Requires super admin authentication (check for @ken-e.ai email)
- Creates new industry entry if doesn't exist
- Replaces all keywords if industry exists
- Validates keywords (alphanumeric, spaces, hyphens, dots, ampersands)
- Maximum 50 keywords per industry
- Maximum 100 characters per keyword

### 3. DELETE /api/v1/industry-keywords/{industry}

**Purpose**: Remove all keywords for a specific industry

**Response**: 204 No Content

**Implementation Details**:

- Requires super admin authentication
- Removes the entire industry entry
- Returns 404 if industry doesn't exist

## Database Schema

### Firestore Collection (Existing)

**Collection**: `industry_keywords` (in default database)

**Document Structure**:

```json
{
  "industry": "Technology",
  "keywords": ["software", "AI", "cloud computing"],
  "created_at": "2024-01-31T10:00:00Z",
  "updated_at": "2024-01-31T10:00:00Z",
  "updated_by": "user@ken-e.ai"
}
```

**Document ID**: Use industry name as document ID (normalized to lowercase, spaces replaced with hyphens)

- Example: "Technology" → document ID: "technology"
- Example: "Real Estate" → document ID: "real-estate"

**Collection Path**: `/industry_keywords/{industry_id}`

**Firestore Indexes**: No composite indexes required for this simple structure

## Implementation Steps

### Phase 1: Basic CRUD Operations

1. Create new router file: `api/src/kene_api/routers/industry_keywords.py`
2. Define Pydantic models:

   ```python
   from datetime import datetime
   from typing import List, Optional
   from pydantic import BaseModel, Field, validator

   class IndustryKeyword(BaseModel):
       industry: str
       keywords: List[str]
       created_at: Optional[datetime] = None
       updated_at: Optional[datetime] = None
       updated_by: Optional[str] = None

   class UpdateKeywordsRequest(BaseModel):
       keywords: List[str] = Field(..., max_items=50)

       @validator('keywords', each_item=True)
       def validate_keyword(cls, v):
           if len(v) > 100:
               raise ValueError('Keyword must be 100 characters or less')
           return v.strip()
   ```

3. Implement Firestore service methods:

   ```python
   from google.cloud import firestore

   db = firestore.Client()
   collection = db.collection('industry_keywords')
   ```

4. Implement GET endpoint to retrieve all keywords from Firestore
5. Implement PUT endpoint to create/update documents in Firestore
6. Implement DELETE endpoint to remove documents from Firestore
7. Add router to main application

### Phase 2: Authentication & Authorization

1. Add super admin check middleware
2. Verify user email ends with @ken-e.ai
3. Return 403 Forbidden for non-super admins on write operations

### Phase 3: Validation & Business Logic

1. Implement keyword validation:
   - Alphanumeric characters, spaces, hyphens, dots, ampersands
   - Maximum length: 100 characters
   - Trim whitespace
   - Remove duplicates (case-insensitive)
2. Implement industry name validation:
   - Required field
   - Maximum length: 50 characters
3. Add rate limiting for write operations

### Phase 4: Data Seeding

Create initial seed data for common industries:

- Technology
- Healthcare
- Finance
- Retail
- Manufacturing
- Education
- Real Estate
- Hospitality
- Transportation
- Energy

### Phase 5: Integration

1. Update frontend to remove "Backend Not Implemented" notice
2. Add error handling for specific API errors
3. Implement caching strategy for GET requests
4. Add audit logging for modifications

## Firestore Implementation Details

### Connection Configuration

```python
from google.cloud import firestore
import os

# Use the default database
db = firestore.Client(
    project=os.environ.get('GOOGLE_CLOUD_PROJECT_ID'),
    database='(default)'  # Explicitly use default database
)

# Reference to the existing collection
collection = db.collection('industry_keywords')
```

### Document ID Generation

```python
def normalize_industry_name(industry: str) -> str:
    """Convert industry name to document ID format"""
    return industry.lower().replace(" ", "-").replace("&", "and")
```

### GET All Keywords

```python
async def get_all_industry_keywords():
    docs = collection.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append(IndustryKeyword(
            industry=data.get('industry'),
            keywords=data.get('keywords', [])
        ))
    return results
```

### PUT Keywords

```python
async def update_industry_keywords(industry: str, keywords: List[str], user_email: str):
    doc_id = normalize_industry_name(industry)
    doc_ref = collection.document(doc_id)

    # Check if document exists
    doc = doc_ref.get()

    data = {
        'industry': industry,
        'keywords': list(set(keywords)),  # Remove duplicates
        'updated_at': firestore.SERVER_TIMESTAMP,
        'updated_by': user_email
    }

    if not doc.exists:
        data['created_at'] = firestore.SERVER_TIMESTAMP

    doc_ref.set(data, merge=True)
    return data
```

### DELETE Keywords

```python
async def delete_industry_keywords(industry: str):
    doc_id = normalize_industry_name(industry)
    doc_ref = collection.document(doc_id)

    # Check if exists
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Industry not found")

    doc_ref.delete()
```

## Testing Requirements

### Unit Tests

- Test keyword validation logic
- Test industry name normalization
- Test duplicate removal
- Test authorization checks

### Integration Tests

- Test full CRUD cycle
- Test concurrent updates
- Test error scenarios (invalid data, unauthorized access)
- Test with real Firestore/BigQuery connection

### E2E Tests

- Test admin user can view industry keywords
- Test admin user can add new industry
- Test admin user can update existing keywords
- Test non-admin user cannot modify keywords

## Security Considerations

1. **Authentication**: Require valid Firebase Auth token
2. **Authorization**: Check user email domain for super admin access
3. **Input Validation**: Sanitize all inputs to prevent injection attacks
4. **Rate Limiting**: Implement rate limits on write operations
5. **Audit Trail**: Log all modifications with user ID and timestamp

## Performance Considerations

1. **Caching**: Cache GET responses for 5 minutes using Redis or in-memory cache
2. **Pagination**: Not needed initially (limited number of industries, ~10-50 documents)
3. **Firestore Limits**:
   - Document size limit: 1MB (sufficient for keywords array)
   - Maximum 500 documents per batch write
   - 1 write per second per document (sufficient for admin operations)
4. **Query Optimization**:
   - Use `select()` to retrieve only needed fields if expanding schema
   - Consider using Firestore local cache for read operations

## Error Handling

Standard HTTP status codes:

- 200 OK: Successful GET/PUT
- 204 No Content: Successful DELETE
- 400 Bad Request: Invalid input data
- 401 Unauthorized: Missing or invalid auth token
- 403 Forbidden: Not a super admin
- 404 Not Found: Industry doesn't exist (for DELETE)
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Database or server error

## Future Enhancements

1. **Versioning**: Track keyword history/changes
2. **Bulk Operations**: Update multiple industries at once
3. **Import/Export**: CSV or JSON bulk import/export
4. **Suggestions**: AI-powered keyword suggestions based on industry
5. **Analytics**: Track which keywords are most used in actual accounts
6. **Localization**: Support keywords in multiple languages

## Implementation Priority

1. **High Priority** (MVP):

   - Basic CRUD endpoints
   - Super admin authentication
   - Input validation

2. **Medium Priority**:

   - Seed data
   - Caching
   - Audit logging

3. **Low Priority**:
   - Bulk operations
   - Import/export
   - Analytics

## Estimated Timeline

- Phase 1 (Basic CRUD): 2-3 days
- Phase 2 (Auth): 1 day
- Phase 3 (Validation): 1-2 days
- Phase 4 (Seeding): 1 day
- Phase 5 (Integration): 1-2 days
- Testing: 2-3 days

**Total: 8-12 days**

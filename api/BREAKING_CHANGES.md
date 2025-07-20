# Breaking Changes

## Version 2.0.0 (2025-01-20)

### Organization API Changes

#### company_size Field Now Optional

The `company_size` field in the Organization model is now optional. This is a breaking change that affects:

1. **POST /api/v1/organizations/** - Creating new organizations
   - `company_size` is no longer required in the request body
   - If not provided, it will be stored as an empty string in the database
   - The response will return an empty string for `company_size` when not set

2. **Organization Model**
   - Changed from `company_size: str` to `company_size: str | None`
   - When retrieved from the database, empty strings are returned as empty strings (not converted to None)

#### Migration Guide

**For API Consumers:**
- The `company_size` field can now be omitted when creating organizations
- Existing organizations with company_size values are not affected
- When querying organizations, be prepared to handle empty string values for `company_size`

**Example - Creating organization without company_size:**
```json
POST /api/v1/organizations/
{
  "organization_name": "My Company",
  "plan": "Professional",
  "website": "https://example.com",
  "agency": false,
  "subscription": { ... },
  "billing": { ... },
  "team": { ... }
}
```

**For Frontend Applications:**
- Remove any validation that requires company_size
- Handle empty string values in display logic
- Consider showing "Not specified" or similar placeholder text for empty company_size values

#### Rationale

This change was made to improve user experience by not forcing organizations to select a company size during onboarding, as this information may not be immediately available or relevant for all organization types.
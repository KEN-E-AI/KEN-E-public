# Firestore to Neo4j Organization Migration

This directory contains scripts to migrate organization data from Firestore to Neo4j.

## Scripts

### 1. `migrate_firestore_organizations_to_neo4j.py`

The main migration script that:
- Reads all organizations from Firestore
- Creates or updates corresponding nodes in Neo4j
- Preserves all organization properties (subscription, billing, team info)
- Creates PARENT_OF relationships for agency organizations
- Handles organizations that already exist in Neo4j
- Logs all operations and errors to both console and file

### 2. `test_firestore_neo4j_migration.py`

Test script to verify the migration setup:
- Tests Firestore connection and read capabilities
- Tests Neo4j connection and query capabilities
- Performs a sample migration with cleanup
- Provides detailed test results

### 3. `migrate_organizations_to_neo4j.py`

Legacy migration script that migrates hardcoded organization data from the frontend to Neo4j.

## Prerequisites

1. **Environment Variables**: Ensure the following are set in your `.env` file:
   ```
   # Firestore Configuration
   GOOGLE_CLOUD_PROJECT_ID=your-project-id
   FIRESTORE_DATABASE_ID=(default)
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   # OR for Cloud Run:
   USE_APPLICATION_DEFAULT_CREDENTIALS=true
   
   # Neo4j Configuration
   NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your-password
   NEO4J_DATABASE=neo4j
   ```

2. **Python Dependencies**: The scripts use the API's existing dependencies. From the `api/` directory:
   ```bash
   uv pip install -r requirements.txt
   ```

## Usage

### Running Tests First

Always run the test script first to verify your setup:

```bash
cd api/scripts
python test_firestore_neo4j_migration.py
```

This will:
- Test Firestore connectivity
- Test Neo4j connectivity
- Perform a sample migration and cleanup
- Report any issues

### Running the Migration

Once tests pass, run the main migration:

```bash
cd api/scripts
python migrate_firestore_organizations_to_neo4j.py
```

The migration will:
1. Initialize both database connections
2. Read all organizations from Firestore
3. For each organization:
   - Check if it exists in Neo4j
   - Create new or update existing organization
   - Preserve all properties (plan, subscription, billing, team)
4. Create PARENT_OF relationships for agencies
5. Verify the migration results
6. Generate a detailed log file

### Migration Features

- **Idempotent**: Can be run multiple times safely
- **Updates Existing Data**: If an organization exists, it updates rather than duplicates
- **Comprehensive Logging**: Creates timestamped log files for each run
- **Error Handling**: Continues on individual failures, logs all errors
- **Progress Tracking**: Shows real-time progress during migration
- **Verification**: Validates data after migration

### Log Files

Migration logs are saved as:
```
migration_YYYYMMDD_HHMMSS.log
```

Example log output:
```
2024-01-30 10:15:23 - INFO - Starting Firestore to Neo4j organization migration
2024-01-30 10:15:24 - INFO - Found 3 organizations in Firestore
2024-01-30 10:15:25 - INFO - Creating new organization: Healthway (healthway)
2024-01-30 10:15:26 - INFO - Organization already exists, updating: Open Lines (open-lines)
...
```

## Data Model

### Organization Node Properties

```cypher
(:Organization {
  organization_id: String,        // Unique identifier
  organization_name: String,      // Display name
  plan: String,                   // Subscription tier
  website: String,                // Company website
  company_size: String,           // Size category
  agency: Boolean,                // Is agency organization
  child_organizations: [String],  // List of child org IDs
  subscription: String,           // JSON string of subscription details
  billing: String,                // JSON string of billing info
  team: String,                   // JSON string of team info
  created_from_firestore: Boolean,      // Migration tracking
  migration_timestamp: DateTime,        // When first migrated
  updated_from_firestore: Boolean,      // Update tracking
  last_migration_timestamp: DateTime    // When last updated
})
```

### Relationships

```cypher
// Agency parent organizations have relationships to their children
(:Organization {agency: true})-[:PARENT_OF]->(:Organization)
```

## Troubleshooting

### Common Issues

1. **Firestore Connection Failed**
   - Check `GOOGLE_APPLICATION_CREDENTIALS` path exists
   - Verify service account has Firestore read permissions
   - For Cloud Run, ensure `USE_APPLICATION_DEFAULT_CREDENTIALS=true`

2. **Neo4j Connection Failed**
   - Verify Neo4j URI includes protocol (`neo4j+s://`)
   - Check username/password are correct
   - Ensure Neo4j instance is running and accessible

3. **Organization Missing ID**
   - The script handles both `id` and `organization_id` fields
   - Organizations without IDs are logged but skipped

4. **Duplicate Organizations**
   - The script uses MERGE operations to prevent duplicates
   - Existing organizations are updated, not recreated

### Verifying Results

After migration, verify in Neo4j Browser:

```cypher
// Count organizations
MATCH (org:Organization) 
RETURN count(org);

// List all organizations
MATCH (org:Organization)
RETURN org.organization_name, org.organization_id, org.plan;

// Check parent-child relationships
MATCH (parent:Organization)-[:PARENT_OF]->(child:Organization)
RETURN parent.organization_name, child.organization_name;

// Find organizations migrated from Firestore
MATCH (org:Organization)
WHERE org.created_from_firestore = true
RETURN org.organization_name, org.migration_timestamp;
```

## Safety Notes

- The migration is non-destructive to Firestore data
- Neo4j data is updated, not deleted (unless organization is removed from Firestore)
- Always backup Neo4j before major migrations
- Test with `test_firestore_neo4j_migration.py` first

## Future Enhancements

Consider adding:
- Dry-run mode to preview changes
- Selective organization migration by ID
- Automatic relationship validation
- Migration rollback capability
- Real-time sync service
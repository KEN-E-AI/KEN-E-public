# 🚨 CRITICAL SECURITY ALERT: Service Account Keys in Repository

## Issue
Service account credential files have been committed to the git repository:
- `api/ken-e-dev-sa.json` (old files)
- `api/ken-e-staging-sa.json` (old files)
- `api/ken-e-production-sa.json` (old files)

New files (also need to be kept out of git):
- `api/ken-e-dev.json`
- `api/ken-e-staging.json`
- `api/ken-e-production.json`

This is a **CRITICAL SECURITY VULNERABILITY** because:
1. Anyone with repository access can use these credentials
2. The keys are now in git history forever (even if deleted)
3. These keys provide access to your Google Cloud resources

## Immediate Actions Required

### 1. Revoke Compromised Keys (DO THIS FIRST!)
```bash
# For each service account, create new keys and delete the old ones
gcloud iam service-accounts keys list --iam-account=SERVICE_ACCOUNT_EMAIL
gcloud iam service-accounts keys delete KEY_ID --iam-account=SERVICE_ACCOUNT_EMAIL
```

### 2. Remove Files from Repository
```bash
# Remove the OLD files from tracking (if still present)
git rm --cached api/ken-e-dev-sa.json
git rm --cached api/ken-e-staging-sa.json
git rm --cached api/ken-e-production-sa.json

# Make sure NEW files are not tracked
git rm --cached api/ken-e-dev.json
git rm --cached api/ken-e-staging.json
git rm --cached api/ken-e-production.json

# Commit the removal
git commit -m "Remove service account keys from repository"

# Push the changes
git push
```

### 3. Clean Git History (Optional but Recommended)
Since the keys are in git history, they're still accessible. Options:

**Option A: Use BFG Repo-Cleaner (Easier)**
```bash
# Download BFG
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar

# Remove all .json files containing 'private_key'
java -jar bfg-1.14.0.jar --delete-files '*-sa.json' 

# Clean up
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

**Option B: Use git filter-branch (Built-in)**
```bash
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch api/ken-e-*-sa.json' \
  --prune-empty --tag-name-filter cat -- --all

git push --force --all
git push --force --tags
```

### 4. Create New Service Account Keys
```bash
# Create new keys
gcloud iam service-accounts keys create NEW-ken-e-staging-sa.json \
  --iam-account=YOUR_SERVICE_ACCOUNT_EMAIL

# Store them securely (NOT in the repository)
```

## Prevention Going Forward

### 1. Never Store Service Account Keys in Repository
Instead, use one of these approaches:

**Approach A: Environment Variables**
```bash
# Store the JSON as a base64-encoded environment variable
export SA_KEY_STAGING=$(base64 < ken-e-staging-sa.json)

# In your code, decode it
echo $SA_KEY_STAGING | base64 -d > /tmp/sa-key.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json
```

**Approach B: Google Secret Manager**
```bash
# Store the entire JSON in Secret Manager
gcloud secrets create ken-e-staging-sa-key \
  --data-file=ken-e-staging-sa.json

# Retrieve it when needed
gcloud secrets versions access latest \
  --secret=ken-e-staging-sa-key > /tmp/sa-key.json
```

**Approach C: Use Workload Identity (Best for GKE)**
- No keys needed at all
- Pods authenticate as service accounts directly

### 2. Add Pre-commit Hooks
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### 3. Update Documentation
Create clear documentation about credential management:
```markdown
# Credential Management

## DO NOT:
- Never commit service account keys
- Never commit API keys or passwords
- Never store credentials in code

## DO:
- Use environment variables
- Use Google Secret Manager
- Use workload identity when possible
```

## Verification Steps

After completing the cleanup:

1. **Verify keys are revoked**:
   ```bash
   # Try to use the old key - it should fail
   export GOOGLE_APPLICATION_CREDENTIALS=old-key.json
   gcloud auth application-default print-access-token
   ```

2. **Verify files are gone**:
   ```bash
   # Should return nothing
   git ls-files | grep sa.json
   ```

3. **Verify history is clean** (if you cleaned it):
   ```bash
   # Should return nothing
   git log --all --full-history -- "*-sa.json"
   ```

## Team Communication

Notify your team immediately:
1. Service account keys were exposed
2. Keys have been rotated
3. New procedures are in place
4. Anyone who pulled the repository has the old keys

## References
- [Google Cloud: Best practices for managing service account keys](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys)
- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
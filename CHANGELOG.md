# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-01-31

### Changed

#### Authentication Architecture Refactoring
- **Refactored user context handling** to prevent circular imports
  - Moved internal implementation to `_get_user_context_with_limiter` function
  - Lazy-loaded Redis connections to avoid initialization at module import time
  - Properly typed all dependencies with explicit type annotations
- **Added specialized rate limiter for polling endpoints**
  - New `progress_rate_limiter` allows 120 requests/minute (vs 60 for standard endpoints)
  - Created `get_user_context_for_polling` function in `auth/dependencies.py`
  - Suitable for progress tracking and long-running operation monitoring

#### Account Creation Improvements
- **Simplified progress tracking model**
  - Replaced complex multi-step progress tracking with simpler `AccountCreationStatus` model
  - Removed detailed step-by-step progress in favor of basic status reporting
- **API endpoint now properly documented for FormData**
  - Fixed misleading documentation that showed JSON examples for FormData endpoint
  - Added proper curl examples with multipart/form-data format
  - Clarified that array fields must be JSON-encoded strings
- **Added file upload support**
  - Account creation now supports uploading business strategy documents
  - Multiple files can be attached during account creation

#### Strategy Generation Fixes
- **Fixed Firestore project ID issues**
  - Added workaround for numeric project IDs causing Firestore errors
  - Forces project ID to "ken-e-dev" when numeric ID detected
- **Prevented malformed collection names**
  - Added validation to prevent invalid characters in Firestore collection names
- **Improved error handling**
  - Better timeout handling for long-running strategy generation
  - More informative error messages for failed operations

### Fixed
- Circular import issues in authentication module
- Redis initialization happening at module load time
- Account list refresh timeout after account creation
- Integration test import errors after refactoring
- Misleading API documentation for account creation endpoint

### Testing
- Updated integration tests to use correct import paths
- Fixed test imports for `get_user_context_for_polling`
- Marked deprecated tests with appropriate skip reasons

### Architecture Decisions

#### Why Simplify Progress Tracking?
The previous multi-step progress tracking system was complex and prone to race conditions. The simplified status model provides:
- Better reliability with fewer moving parts
- Easier debugging and maintenance
- Sufficient information for user feedback
- Reduced Redis cache complexity

#### Why Use FormData Instead of JSON?
FormData was chosen for the account creation endpoint to:
- Support file uploads alongside regular form fields
- Maintain compatibility with existing frontend implementation
- Allow for future expansion with additional file types
- Provide better browser compatibility for large file uploads

#### Firestore Project ID Workaround
The hardcoded project ID fix is a temporary workaround for an issue where:
- Numeric project IDs cause Firestore client initialization failures
- The root cause appears to be in the Google Cloud Python SDK
- This will be removed once the upstream issue is resolved

## Notes for Developers

### Breaking Changes
None - The frontend was already using FormData, so no breaking changes exist.

### Migration Guide
No migration needed as the changes maintain backward compatibility.

### Known Issues
- Firestore project ID workaround needs permanent fix
- Some progress tracking granularity lost with simplified model
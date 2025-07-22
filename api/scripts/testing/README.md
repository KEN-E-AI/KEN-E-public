# Testing Scripts

This directory contains utility scripts for testing and verifying various API components.

## Scripts

### verify_cli.py
Demonstrates and tests the Kene API CLI functionality programmatically.

Usage:
```bash
python scripts/testing/verify_cli.py
```

### verify_firestore.py
Verifies that Firestore integration is working correctly with proper authentication.

Usage:
```bash
python scripts/testing/verify_firestore.py
```

### verify_recaptcha.py
Tests reCAPTCHA configuration and functionality.

Usage:
```bash
python scripts/testing/verify_recaptcha.py
```

### verify_superset.py
Tests Apache Superset integration functionality.

Usage:
```bash
python scripts/testing/verify_superset.py
```

### simple_api_server.py
A simple FastAPI server for basic API testing. Runs on port 8001.

Usage:
```bash
python scripts/testing/simple_api_server.py
```

## Note
These are not unit tests but verification and utility scripts. Unit tests are located in the `tests/` directory.
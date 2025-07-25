#!/usr/bin/env python3
"""Check if Application Default Credentials are configured."""

import json
import os
import sys
from pathlib import Path


def check_adc():
    """Check if ADC is configured and valid."""
    # Check for ADC in standard locations
    adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    
    if not adc_path.exists():
        return False, "No ADC found"
    
    try:
        with open(adc_path, 'r') as f:
            creds = json.load(f)
            
        # Check if it's a user account (not service account)
        if creds.get('type') == 'authorized_user':
            # Could add more validation here (e.g., check expiry)
            return True, "ADC configured"
        else:
            return True, f"ADC configured ({creds.get('type', 'unknown')})"
            
    except Exception as e:
        return False, f"Invalid ADC: {e}"


if __name__ == "__main__":
    is_valid, message = check_adc()
    if is_valid:
        sys.exit(0)
    else:
        sys.exit(1)
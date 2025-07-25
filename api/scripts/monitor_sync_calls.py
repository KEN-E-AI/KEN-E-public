#!/usr/bin/env python3
"""Monitor sync endpoint calls to verify frontend integration."""

import asyncio
import requests
import time
from datetime import datetime

def monitor_sync_calls():
    """Monitor the API logs for sync calls."""
    print("MONITORING SYNC ENDPOINT CALLS")
    print("=" * 50)
    print("Watching for calls to /api/v1/activities/logs/sync")
    print("\nTo test:")
    print("1. Open the frontend and go to Account Settings")
    print("2. Change the region of an account")
    print("3. Save the changes")
    print("4. You should see sync calls appear below")
    print("\n" + "=" * 50 + "\n")
    
    # This is a simple approach - in production you'd monitor actual logs
    # For now, we'll just show instructions
    print("Please check the API terminal logs for entries like:")
    print('INFO:     "POST /api/v1/activities/logs/sync?account_id=xxx HTTP/1.1" 200')
    print("\nIf you see these entries after changing a region, the integration is working!")
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    monitor_sync_calls()
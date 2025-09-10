#!/usr/bin/env python3
"""
Clean up old reasoning engines in development environment.
Keeps only the two newly deployed engines.
"""

import os
import subprocess
import json
import time

# Initialize for development
PROJECT_ID = "ken-e-dev"
PROJECT_NUMBER = "525657242938"
LOCATION = "us-central1"

# Engines to keep (the two we just deployed)
ENGINES_TO_KEEP = {
    "6673424252135276544",  # KEN-E Agent deployed today
    "5238464820864352256"   # Strategy Supervisor deployed today
}

def get_access_token():
    """Get access token for authentication."""
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def list_reasoning_engines():
    """List all reasoning engines in the project."""
    token = get_access_token()
    
    cmd = [
        "curl", "-s",
        "-H", f"Authorization: Bearer {token}",
        f"https://us-central1-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error listing engines: {result.stderr}")
        return []
    
    try:
        data = json.loads(result.stdout)
        engines = data.get("reasoningEngines", [])
        return [e["name"].split("/")[-1] for e in engines]
    except json.JSONDecodeError:
        print("Error parsing response")
        return []

def delete_reasoning_engine(engine_id, max_retries=3):
    """Delete a reasoning engine with retry logic."""
    for attempt in range(max_retries):
        token = get_access_token()
        
        if attempt == 0:
            print(f"  Deleting engine: {engine_id}")
        else:
            print(f"  Retry {attempt}/{max_retries} for engine: {engine_id}")
        
        cmd = [
            "curl", "-s", "-X", "DELETE",
            "-H", f"Authorization: Bearer {token}",
            f"https://us-central1-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{engine_id}?force=true"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if deletion was successful or if engine is already gone
        if result.returncode == 0:
            response_text = result.stdout.strip()
            # Empty response or operation response means success
            if not response_text or "operation" in response_text.lower():
                print(f"  ✅ Successfully initiated deletion of {engine_id}")
                return True
        
        # Check if engine doesn't exist (already deleted)
        if "404" in result.stderr or "not found" in result.stderr.lower():
            print(f"  ✅ Engine {engine_id} already deleted or doesn't exist")
            return True
            
        # If not the last attempt, wait before retrying
        if attempt < max_retries - 1:
            print(f"  ⏳ Waiting 5 seconds before retry...")
            time.sleep(5)
    
    print(f"  ❌ Failed to delete {engine_id} after {max_retries} attempts")
    return False

def main():
    print(f"=== Cleaning up Reasoning Engines in {PROJECT_ID} ===")
    print(f"Project Number: {PROJECT_NUMBER}")
    print(f"Location: {LOCATION}")
    print(f"\nEngines to KEEP:")
    for engine_id in ENGINES_TO_KEEP:
        print(f"  - {engine_id}")
    
    print("\nListing all reasoning engines...")
    engines = list_reasoning_engines()
    
    if not engines:
        print("No reasoning engines found.")
        return
    
    print(f"\nFound {len(engines)} total reasoning engines")
    
    # Identify engines to delete
    engines_to_delete = []
    for engine_id in engines:
        if engine_id not in ENGINES_TO_KEEP:
            engines_to_delete.append(engine_id)
    
    if not engines_to_delete:
        print("\n✅ No engines to delete. Only the 2 specified engines exist.")
        return
    
    print(f"\nEngines to DELETE ({len(engines_to_delete)}):")
    for engine_id in engines_to_delete:
        print(f"  - {engine_id}")
    
    print("\nDeleting engines...")
    success_count = 0
    failed_engines = []
    
    # First pass: try to delete all engines
    for engine_id in engines_to_delete:
        if delete_reasoning_engine(engine_id):
            success_count += 1
        else:
            failed_engines.append(engine_id)
    
    # If there are failed engines, wait and retry
    if failed_engines:
        print(f"\n⏳ Waiting 10 seconds before retrying {len(failed_engines)} failed deletions...")
        time.sleep(10)
        
        print("\nRetrying failed deletions...")
        for engine_id in failed_engines[:]:  # Use slice to copy list
            if delete_reasoning_engine(engine_id, max_retries=5):
                success_count += 1
                failed_engines.remove(engine_id)
    
    print(f"\n=== Summary ===")
    print(f"Deleted: {success_count}/{len(engines_to_delete)} engines")
    print(f"Kept: {len(ENGINES_TO_KEEP)} engines")
    
    if failed_engines:
        print(f"\n⚠️ Failed to delete {len(failed_engines)} engines:")
        for engine_id in failed_engines:
            print(f"  - {engine_id}")
    
    # Verify final state
    print("\nVerifying final state...")
    final_engines = list_reasoning_engines()
    print(f"Remaining engines: {len(final_engines)}")
    
    expected_engines = []
    unexpected_engines = []
    
    for engine_id in final_engines:
        if engine_id in ENGINES_TO_KEEP:
            expected_engines.append(engine_id)
            print(f"  - {engine_id} ✅ KEPT (as expected)")
        else:
            unexpected_engines.append(engine_id)
            print(f"  - {engine_id} ⚠️ UNEXPECTED (should have been deleted)")
    
    if len(final_engines) == len(ENGINES_TO_KEEP) and not unexpected_engines:
        print("\n✅ SUCCESS: Only the specified 2 engines remain!")
    else:
        print(f"\n⚠️ WARNING: Expected {len(ENGINES_TO_KEEP)} engines, but found {len(final_engines)}")
        if unexpected_engines:
            print(f"   {len(unexpected_engines)} engines were not successfully deleted")

if __name__ == "__main__":
    main()
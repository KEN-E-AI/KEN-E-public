#!/usr/bin/env python3
"""
Clean up old reasoning engines in staging environment.
Keeps only the specified engines and deletes all others.
"""


from google.cloud import aiplatform

# Initialize Vertex AI
PROJECT_ID = "ken-e-staging"
LOCATION = "us-central1"

# Engines to keep (these are the active ones)
ENGINES_TO_KEEP = {
    "projects/391472102753/locations/us-central1/reasoningEngines/2500839197376512000",  # Strategy Supervisor (fixed)
    "projects/391472102753/locations/us-central1/reasoningEngines/6952647429032247296",  # KEN-E Agent
}


def list_reasoning_engines() -> list[str]:
    """List all reasoning engines in the project."""
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Try both 'global' and the specific location
    parents = [
        f"projects/{PROJECT_ID}/locations/global",
        f"projects/{PROJECT_ID}/locations/{LOCATION}",
    ]

    engine_names = []

    for parent in parents:
        try:
            # Use the aiplatform client to list reasoning engines
            from google.cloud.aiplatform_v1beta1 import ReasoningEngineServiceClient

            client = ReasoningEngineServiceClient()
            engines = client.list_reasoning_engines(parent=parent)

            for engine in engines:
                # Only add if it's in us-central1 location
                if f"/locations/{LOCATION}/" in engine.name:
                    engine_names.append(engine.name)
        except Exception as e:
            print(f"  Note: Could not list from {parent}: {e}")
            continue

    return engine_names


def delete_reasoning_engine(engine_name: str) -> bool:
    """Delete a reasoning engine."""
    try:
        from google.cloud.aiplatform_v1beta1 import ReasoningEngineServiceClient

        client = ReasoningEngineServiceClient()
        operation = client.delete_reasoning_engine(name=engine_name)

        print(f"  Deleting {engine_name}...")
        # Wait for the operation to complete
        result = operation.result(timeout=300)  # 5 minute timeout
        print("  ✅ Successfully deleted")
        return True
    except Exception as e:
        print(f"  ❌ Error deleting {engine_name}: {e}")
        return False


def main():
    print(f"=== Cleaning up Reasoning Engines in {PROJECT_ID} ===")
    print(f"Location: {LOCATION}")
    print("\nEngines to KEEP:")
    for engine in ENGINES_TO_KEEP:
        engine_id = engine.split("/")[-1]
        print(f"  - {engine_id}")

    print("\nListing all reasoning engines...")
    engines = list_reasoning_engines()

    if not engines:
        print("No reasoning engines found or unable to list them.")
        return

    print(f"\nFound {len(engines)} total reasoning engines")

    # Identify engines to delete
    engines_to_delete = []
    for engine in engines:
        if engine not in ENGINES_TO_KEEP:
            engines_to_delete.append(engine)

    if not engines_to_delete:
        print("\n✅ No engines to delete. Only keeping the specified engines.")
        return

    print(f"\nEngines to DELETE ({len(engines_to_delete)}):")
    for engine in engines_to_delete:
        engine_id = engine.split("/")[-1]
        print(f"  - {engine_id}")

    # Confirm deletion
    response = input("\n⚠️  Are you sure you want to delete these engines? (yes/no): ")
    if response.lower() != "yes":
        print("Deletion cancelled.")
        return

    print("\nDeleting engines...")
    success_count = 0
    for engine in engines_to_delete:
        if delete_reasoning_engine(engine):
            success_count += 1

    print("\n=== Summary ===")
    print(f"Deleted: {success_count}/{len(engines_to_delete)} engines")
    print(f"Kept: {len(ENGINES_TO_KEEP)} engines")


if __name__ == "__main__":
    main()

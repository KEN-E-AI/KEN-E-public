#!/usr/bin/env python3
"""Debug what BigQuery returns for different regions."""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def debug_regions():
    """Check what BigQuery returns for different regions."""
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from src.kene_api.bigquery import BigQueryService

    bigquery = BigQueryService()

    # Initialize BigQuery
    if not bigquery.initialize():
        print("Failed to initialize BigQuery")
        return

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    if not project_id:
        print("GOOGLE_CLOUD_PROJECT_ID not set")
        return

    # Test different regions
    regions_to_test = [["US"], ["JP"], ["AE"], ["AU"], ["GB"], ["CA"]]

    print("BIGQUERY HOLIDAY DATA BY REGION")
    print("=" * 50)

    for region_list in regions_to_test:
        region = region_list[0]
        print(f"\nRegion: {region}")
        print("-" * 30)

        try:
            holidays = bigquery.query_holiday_activities(project_id, region_list)
            print(f"Total holidays: {len(holidays)}")

            if len(holidays) > 0:
                print("First 5 holidays:")
                for holiday in holidays[:5]:
                    print(f"  - {holiday['description']} ({holiday['start_date']})")
            else:
                print("  (No holidays found)")

        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    debug_regions()

#!/usr/bin/env python3
"""
CLI Test Script - Demonstrates the Kene API CLI functionality
This script shows how to use the CLI programmatically for testing purposes.
"""

import sys
import time
from cli_manager import KeneAPIClient, console


def test_cli_functionality():
    """Test the CLI functionality with example operations."""
    console.print("[bold blue]Testing Kene API CLI Functionality[/bold blue]")

    # Initialize API client
    api_client = KeneAPIClient("http://localhost:8000")
    account_id = "a000001"

    try:
        # Test 1: Get activities
        console.print("\n[yellow]Test 1: Getting activities...[/yellow]")
        activities_response = api_client.get_activities(account_id)
        activities = activities_response.get("activities", [])
        console.print(f"✓ Found {len(activities)} activities")

        # Test 2: Get metrics
        console.print("\n[yellow]Test 2: Getting metrics...[/yellow]")
        metrics_response = api_client.get_metrics(account_id)
        metrics = metrics_response.get("metrics", [])
        console.print(f"✓ Found {len(metrics)} metrics")

        # Test 3: Get insights
        console.print("\n[yellow]Test 3: Getting insights...[/yellow]")
        insights_response = api_client.get_insights(account_id)
        insights = insights_response.get("insights", [])
        intuitions = insights_response.get("intuitions", [])
        console.print(
            f"✓ Found {len(insights)} insights and {len(intuitions)} intuitions"
        )

        # Display summary
        console.print("\n[green]✓ All API endpoints are accessible![/green]")
        console.print(f"Account {account_id} summary:")
        console.print(f"  - Activities: {len(activities)}")
        console.print(f"  - Metrics: {len(metrics)}")
        console.print(f"  - Insights: {len(insights)}")
        console.print(f"  - Intuitions: {len(intuitions)}")

        if activities:
            console.print(
                f"\nExample activity: {activities[0].get('activity_description', 'N/A')}"
            )

        if metrics:
            console.print(f"Example metric: {metrics[0].get('verbose_name', 'N/A')}")

        console.print("\n[bold green]🎉 CLI is ready for interactive use![/bold green]")
        console.print(
            "[dim]Run 'uv run python cli_manager.py' to start the interactive CLI[/dim]"
        )

        return True

    except Exception as e:
        console.print(f"[red]✗ Error testing CLI: {e}[/red]")
        return False


if __name__ == "__main__":
    success = test_cli_functionality()
    sys.exit(0 if success else 1)

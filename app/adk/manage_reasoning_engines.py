#!/usr/bin/env python
"""
Unified script to manage Vertex AI Reasoning Engines.

Usage:
    # List all engines
    python manage_reasoning_engines.py --list
    
    # Delete unused engines (interactive confirmation)
    python manage_reasoning_engines.py --delete
    
    # Delete unused engines (no confirmation)
    python manage_reasoning_engines.py --delete --yes
    
    # Keep a specific engine and delete others
    python manage_reasoning_engines.py --delete --keep-id 1824877040805871616
    
    # Dry run - show what would be deleted without actually deleting
    python manage_reasoning_engines.py --delete --dry-run
"""

import argparse
import json
import subprocess
import sys
import time
from typing import List, Dict, Optional
from datetime import datetime

# Default engine to keep (can be overridden with --keep-id)
DEFAULT_KEEP_ENGINE_ID = None

# Rate limiting configuration
REQUESTS_PER_MINUTE = 8
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE  # 7.5 seconds

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text: str, color: str = Colors.RESET, bold: bool = False):
    """Print colored text to terminal."""
    if bold:
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}")
    else:
        print(f"{color}{text}{Colors.RESET}")

def get_access_token() -> str:
    """Get GCP access token."""
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print_colored("Error: Failed to get GCP access token", Colors.RED)
        print_colored("Make sure you're authenticated with gcloud", Colors.YELLOW)
        sys.exit(1)
    return result.stdout.strip()

def get_current_project() -> str:
    """Get current GCP project ID."""
    result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        print_colored("Error: No GCP project configured", Colors.RED)
        print_colored("Run: gcloud config set project PROJECT_ID", Colors.YELLOW)
        sys.exit(1)
    return result.stdout.strip()

def list_reasoning_engines(project_id: str, location: str = "us-central1") -> List[Dict]:
    """List all reasoning engines in the project."""
    token = get_access_token()
    
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines"
    
    cmd = [
        "curl", "-s",
        "-H", f"Authorization: Bearer {token}",
        url
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print_colored(f"Error fetching engines: {result.stderr}", Colors.RED)
        return []
    
    try:
        data = json.loads(result.stdout)
        return data.get("reasoningEngines", [])
    except json.JSONDecodeError as e:
        print_colored(f"Error parsing response: {e}", Colors.RED)
        return []

def delete_reasoning_engine(
    engine_name: str, 
    project_id: str, 
    location: str = "us-central1",
    force: bool = True
) -> bool:
    """Delete a reasoning engine."""
    token = get_access_token()
    
    # Construct proper API path
    if engine_name.startswith("projects/"):
        api_path = engine_name
    else:
        api_path = f"projects/{project_id}/locations/{location}/reasoningEngines/{engine_name}"
    
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/{api_path}"
    if force:
        url += "?force=true"
    
    cmd = [
        "curl", "-s",
        "-X", "DELETE",
        "-H", f"Authorization: Bearer {token}",
        url
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        try:
            response = json.loads(result.stdout) if result.stdout else {}
            if "error" in response:
                error_msg = response['error'].get('message', 'Unknown error')
                if "Quota exceeded" in error_msg:
                    return None  # Signal rate limit
                return False
            return True
        except json.JSONDecodeError:
            return True
    return False

def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return timestamp_str

def display_engines(engines: List[Dict], keep_id: Optional[str] = None):
    """Display engines in a formatted table."""
    if not engines:
        print_colored("No reasoning engines found.", Colors.YELLOW)
        return
    
    print_colored("\n" + "=" * 100, Colors.CYAN)
    print_colored("REASONING ENGINES", Colors.CYAN, bold=True)
    print_colored("=" * 100, Colors.CYAN)
    
    for i, engine in enumerate(engines, 1):
        engine_id = engine["name"].split("/")[-1]
        is_keeper = engine_id == keep_id if keep_id else False
        
        # Color based on status
        if is_keeper:
            color = Colors.GREEN
            status = "✅ KEEP"
        else:
            color = Colors.YELLOW
            status = "📌 ACTIVE" if not keep_id else "❌ TO DELETE"
        
        print(f"\n{i}. ", end="")
        print_colored(f"{status}", color, bold=True)
        print(f"   ID: {engine_id}")
        print(f"   Name: {engine.get('displayName', 'N/A')}")
        print(f"   Created: {format_timestamp(engine.get('createTime', 'N/A'))}")
        if engine.get('updateTime'):
            print(f"   Updated: {format_timestamp(engine.get('updateTime'))}")
        if engine.get('description'):
            print(f"   Description: {engine.get('description')}")
    
    print_colored("\n" + "=" * 100, Colors.CYAN)
    print(f"Total engines: {len(engines)}")

def delete_engines_with_retry(
    engines_to_delete: List[Dict],
    project_id: str,
    location: str = "us-central1",
    dry_run: bool = False
) -> tuple[int, int]:
    """Delete engines with rate limiting and retry logic."""
    if dry_run:
        print_colored("\nDRY RUN - No engines will be deleted", Colors.YELLOW, bold=True)
        for engine in engines_to_delete:
            engine_id = engine["name"].split("/")[-1]
            print(f"Would delete: {engine_id} ({engine.get('displayName', 'N/A')})")
        return len(engines_to_delete), 0
    
    success_count = 0
    fail_count = 0
    retry_list = []
    
    print_colored(f"\nDeleting {len(engines_to_delete)} engines...", Colors.YELLOW)
    print(f"Rate limit: {REQUESTS_PER_MINUTE} requests per minute")
    print("-" * 100)
    
    for i, engine in enumerate(engines_to_delete, 1):
        engine_id = engine["name"].split("/")[-1]
        engine_name = engine.get('displayName', 'N/A')
        
        print(f"\n[{i}/{len(engines_to_delete)}] {engine_name}")
        print(f"  ID: {engine_id}")
        
        result = delete_reasoning_engine(engine["name"], project_id, location, force=True)
        
        if result is True:
            print_colored("  ✅ Delete operation started", Colors.GREEN)
            success_count += 1
        elif result is None:  # Rate limited
            print_colored("  ⏸️  Rate limited - will retry later", Colors.YELLOW)
            retry_list.append(engine)
        else:
            print_colored("  ❌ Failed to delete", Colors.RED)
            fail_count += 1
        
        # Rate limiting
        if i < len(engines_to_delete):
            print(f"  ⏱️  Waiting {DELAY_BETWEEN_REQUESTS:.1f} seconds...")
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Retry failed deletions
    if retry_list:
        print_colored(f"\n\nRetrying {len(retry_list)} rate-limited deletions...", Colors.YELLOW, bold=True)
        print("Waiting 60 seconds for rate limit reset...")
        time.sleep(60)
        
        for i, engine in enumerate(retry_list, 1):
            engine_id = engine["name"].split("/")[-1]
            print(f"\n[Retry {i}/{len(retry_list)}] ID: {engine_id}")
            
            result = delete_reasoning_engine(engine["name"], project_id, location, force=True)
            
            if result is True:
                print_colored("  ✅ Delete operation started", Colors.GREEN)
                success_count += 1
            else:
                print_colored("  ❌ Failed to delete", Colors.RED)
                fail_count += 1
            
            if i < len(retry_list):
                time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return success_count, fail_count

def main():
    parser = argparse.ArgumentParser(
        description="Manage Vertex AI Reasoning Engines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                          List all engines
  %(prog)s --delete --keep-id 12345        Delete all except engine 12345
  %(prog)s --delete --yes                  Delete without confirmation
  %(prog)s --delete --dry-run              Show what would be deleted
  %(prog)s --project my-project --list     List engines in specific project
        """
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all reasoning engines"
    )
    
    parser.add_argument(
        "--delete", "-d",
        action="store_true",
        help="Delete unused reasoning engines"
    )
    
    parser.add_argument(
        "--keep-id", "-k",
        type=str,
        default=DEFAULT_KEEP_ENGINE_ID,
        help="Engine ID to keep (all others will be deleted)"
    )
    
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    parser.add_argument(
        "--project", "-p",
        type=str,
        help="GCP project ID (defaults to current gcloud config)"
    )
    
    parser.add_argument(
        "--location",
        type=str,
        default="us-central1",
        help="GCP location/region (default: us-central1)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.list and not args.delete:
        parser.print_help()
        sys.exit(1)
    
    if args.delete and not args.keep_id and not args.yes and not args.dry_run:
        print_colored("Warning: No --keep-id specified. This will delete ALL engines!", Colors.RED, bold=True)
        print_colored("Use --keep-id to specify which engine to keep", Colors.YELLOW)
        sys.exit(1)
    
    # Get project ID
    project_id = args.project or get_current_project()
    
    print_colored(f"\nProject: {project_id}", Colors.BLUE, bold=True)
    print_colored(f"Location: {args.location}", Colors.BLUE)
    
    # List engines
    engines = list_reasoning_engines(project_id, args.location)
    
    if not engines:
        print_colored("\nNo reasoning engines found.", Colors.YELLOW)
        sys.exit(0)
    
    # Display engines
    if args.list:
        display_engines(engines, args.keep_id)
    
    # Delete engines
    if args.delete:
        if not args.keep_id:
            engines_to_delete = engines
            print_colored("\n⚠️  WARNING: Deleting ALL engines!", Colors.RED, bold=True)
        else:
            # Find engine to keep
            engine_to_keep = None
            engines_to_delete = []
            
            for engine in engines:
                engine_id = engine["name"].split("/")[-1]
                if engine_id == args.keep_id:
                    engine_to_keep = engine
                else:
                    engines_to_delete.append(engine)
            
            if not engine_to_keep:
                print_colored(f"\n⚠️  Warning: Engine {args.keep_id} not found!", Colors.YELLOW)
                print_colored("Proceeding to delete all engines...", Colors.YELLOW)
                engines_to_delete = engines
            else:
                print_colored(f"\n✅ Keeping engine: {args.keep_id}", Colors.GREEN, bold=True)
                print(f"   Name: {engine_to_keep.get('displayName', 'N/A')}")
        
        if not engines_to_delete:
            print_colored("\n✅ No engines to delete.", Colors.GREEN)
            sys.exit(0)
        
        print_colored(f"\n❌ Engines to delete: {len(engines_to_delete)}", Colors.RED)
        
        # Confirm deletion
        if not args.yes and not args.dry_run:
            try:
                response = input(f"\n⚠️  Delete {len(engines_to_delete)} engine(s)? (yes/no): ").strip().lower()
                if response != "yes":
                    print_colored("Deletion cancelled.", Colors.YELLOW)
                    sys.exit(0)
            except (KeyboardInterrupt, EOFError):
                print_colored("\nDeletion cancelled.", Colors.YELLOW)
                sys.exit(0)
        
        # Perform deletion
        success, failed = delete_engines_with_retry(
            engines_to_delete, 
            project_id, 
            args.location,
            args.dry_run
        )
        
        # Summary
        if not args.dry_run:
            print_colored("\n" + "=" * 100, Colors.CYAN)
            print_colored("DELETION SUMMARY", Colors.CYAN, bold=True)
            print_colored("=" * 100, Colors.CYAN)
            
            if success > 0:
                print_colored(f"✅ Successfully deleted: {success} engine(s)", Colors.GREEN)
            if failed > 0:
                print_colored(f"❌ Failed to delete: {failed} engine(s)", Colors.RED)
            if args.keep_id and engine_to_keep:
                print_colored(f"✅ Kept: 1 engine (ID: {args.keep_id})", Colors.GREEN)
            
            # Verify final state
            print("\nVerifying final state...")
            remaining = list_reasoning_engines(project_id, args.location)
            
            if args.keep_id:
                if len(remaining) == 1:
                    remaining_id = remaining[0]["name"].split("/")[-1]
                    if remaining_id == args.keep_id:
                        print_colored("✅ SUCCESS: Only the specified engine remains!", Colors.GREEN, bold=True)
                    else:
                        print_colored(f"⚠️  WARNING: Unexpected engine remains: {remaining_id}", Colors.YELLOW)
                elif len(remaining) > 1:
                    print_colored(f"⚠️  WARNING: {len(remaining)} engines still remain", Colors.YELLOW)
                else:
                    print_colored("⚠️  WARNING: No engines remain (including the one to keep)", Colors.YELLOW)
            else:
                if len(remaining) == 0:
                    print_colored("✅ SUCCESS: All engines deleted!", Colors.GREEN, bold=True)
                else:
                    print_colored(f"⚠️  WARNING: {len(remaining)} engines still remain", Colors.YELLOW)

if __name__ == "__main__":
    main()
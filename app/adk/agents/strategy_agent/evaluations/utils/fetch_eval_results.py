"""
Fetch and analyze evaluation results from W&B Weave.

Usage:
    python -m strategy_agent.utils.fetch_eval_results --eval_name company_overview_full_eval
"""

import argparse
import weave
from strategy_agent.env_loader import load_env


def fetch_evaluation_results(eval_call_id: str) -> None:
    """
    Fetch and display evaluation results from Weave.

    Args:
        eval_call_id: The call ID of the evaluation to analyze
    """
    load_env()
    client = weave.init(project_name="ken-e/ken-e-strategy-agent")

    # Get the evaluation call
    call = client.get_call(eval_call_id)

    print(f"\n{'='*80}")
    print(f"Evaluation: {call.op_name}")
    print(f"Call ID: {eval_call_id}")
    print(f"{'='*80}\n")

    # Get output/results
    output = call.output

    if output:
        print("Results Summary:")
        print("-" * 80)

        if isinstance(output, dict):
            for key, value in output.items():
                print(f"{key}: {value}")
        else:
            print(output)

    # Get child calls (individual scorer results)
    print("\n\nScorer Results:")
    print("-" * 80)

    for child in call.children():
        print(f"\n{child.op_name}:")
        if child.output:
            print(f"  Output: {child.output}")
        if hasattr(child, 'summary') and child.summary:
            print(f"  Summary: {child.summary}")


def list_recent_evaluations(limit: int = 10) -> None:
    """
    List recent evaluation runs.

    Args:
        limit: Number of recent evaluations to show
    """
    load_env()
    client = weave.init(project_name="ken-e/ken-e-strategy-agent")

    # Get calls for Evaluation operations using the correct API
    calls_iter = client.get_calls()

    print(f"\n{'='*80}")
    print(f"Recent Evaluations (last {limit})")
    print(f"{'='*80}\n")

    count = 0
    for call in calls_iter:
        # Filter for evaluation-related calls
        if 'eval' in call.op_name.lower() or call.op_name == 'weave:///Evaluation/evaluate':
            print(f"Name: {call.op_name}")
            print(f"Call ID: {call.id}")
            print(f"Started: {call.started_at}")
            if hasattr(call, 'display_name') and call.display_name:
                print(f"Display Name: {call.display_name}")
            print("-" * 80)

            count += 1
            if count >= limit:
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Fetch and analyze evaluation results from W&B Weave'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Fetch specific evaluation
    fetch_parser = subparsers.add_parser('fetch', help='Fetch specific evaluation results')
    fetch_parser.add_argument(
        '--eval_call_id',
        type=str,
        required=True,
        help='Call ID of the evaluation to fetch'
    )

    # List recent evaluations
    list_parser = subparsers.add_parser('list', help='List recent evaluations')
    list_parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of recent evaluations to list'
    )

    args = parser.parse_args()

    if args.command == 'fetch':
        fetch_evaluation_results(args.eval_call_id)
    elif args.command == 'list':
        list_recent_evaluations(args.limit)
    else:
        parser.print_help()

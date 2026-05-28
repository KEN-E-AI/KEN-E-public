"""
Company Overview Evaluation - Full Implementation

Evaluates company_overview_summary against all 6 criteria:
1. Character length (800-4000)
2. Product/service description
3. Founding date/age
4. Mission statement
5. Brand identity
6. Target customers

Original evaluation script template by Yafet Tamene (@fafz1234)
Adapted with local scorer implementations and updated requirements.

Usage:
    cd app/adk/agents
    python -m strategy_agent.evaluations.company_overview_eval --dataset llm_judge_alignment_set:v26 --eval_name my_eval
"""

import argparse
import asyncio
from typing import Any

import weave
from strategy_agent.evaluations.core.dataset_extractors import extract_company_overview
from strategy_agent.evaluations.env_loader import load_env
from strategy_agent.evaluations.scorers.company_overview_scorers import (
    BrandIdentityScorer,
    CompanyOverviewLengthScorer,
    CompleteThoughtsScorer,
    FoundingDateScorer,
    MissionStatementScorer,
    ProductServiceDescriptionScorer,
    TargetCustomerScorer,
)


class CompanyOverviewModel(weave.Model):
    """
    Model that extracts company_overview_summary for scoring.

    This is NOT regenerating outputs - it's extracting from
    pre-existing dataset rows for evaluation.
    """

    client: Any  # Weave client for reference

    @weave.op()
    def predict(self, company_overview_summary: str) -> dict:
        """
        Extract company_overview_summary from dataset row.

        Weave matches parameter names to dataset columns via preprocess_model_input.

        Args:
            company_overview_summary: Extracted from dataset via preprocess

        Returns:
            dict with company_overview_summary (matches scorer signature)
        """
        # Scorers expect: output.get('company_overview_summary')
        return {"company_overview_summary": str(company_overview_summary)}


async def run_company_overview_eval(
    dataset_name: str,
    eval_name: str,
    enabled_scorers: list[str] | None = None,
):
    """
    Run comprehensive company overview evaluation.

    Args:
        dataset_name: Weave dataset reference (e.g., "llm_judge_alignment_set:v26")
        enabled_scorers: Optional list of scorer class names to enable.
                        If None, runs all scorers.
    """
    # Load environment
    load_env()

    # Initialize Weave
    client = weave.init(project_name="ken-e/ken-e-strategy-agent")

    # Load dataset
    dataset = weave.ref(dataset_name).get()
    print(f"Dataset: {dataset_name} ({len(dataset.rows)} rows)")

    # Create model
    model = CompanyOverviewModel(client=client)

    # Preprocessing function using smart extractor
    def preprocess_model_input(row):
        """Extract company_overview_summary with fallback to trace traversal."""
        summary = extract_company_overview(client, row)
        return {"company_overview_summary": summary}

    # Use local scorer implementations
    print("\nInitializing scorers:")

    all_scorers = {
        "CompanyOverviewLengthScorer": CompanyOverviewLengthScorer(),
        "ProductServiceDescriptionScorer": ProductServiceDescriptionScorer(),
        "FoundingDateScorer": FoundingDateScorer(),
        "MissionStatementScorer": MissionStatementScorer(),
        "BrandIdentityScorer": BrandIdentityScorer(),
        "TargetCustomerScorer": TargetCustomerScorer(),
        "CompleteThoughtsScorer": CompleteThoughtsScorer(),
    }

    # Filter to enabled scorers if specified
    if enabled_scorers:
        scorers = [
            scorer for name, scorer in all_scorers.items() if name in enabled_scorers
        ]
    else:
        scorers = list(all_scorers.values())

    for name in all_scorers.keys():
        if not enabled_scorers or name in enabled_scorers:
            print(f"  ✓ {name}")

    print(f"\nScorers ready: {len(scorers)}")

    # Create evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=scorers,
        preprocess_model_input=preprocess_model_input,
        name=eval_name,
        # company_overview_full_eval, company_overview_full_eval_test
    )

    # Run evaluation
    print(f"\nRunning evaluation: {eval_name}\n")

    try:
        results = await evaluation.evaluate(model)

        print("\nEvaluation complete!")
        print("View results at: https://wandb.ai/ken-e/ken-e-strategy-agent/weave")

        return results

    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run company overview evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Weave dataset name (e.g., llm_judge_alignment_set:v26)",
    )
    parser.add_argument(
        "--scorers",
        nargs="+",
        default=None,
        help="Scorers to enable (space-separated). If omitted, runs all. Example: FoundingDateScorer MissionStatementScorer",
    )
    parser.add_argument(
        "--eval_name", type=str, required=True, help="Weave Evaluation name"
    )

    args = parser.parse_args()

    asyncio.run(
        run_company_overview_eval(
            dataset_name=args.dataset,
            eval_name=args.eval_name,
            enabled_scorers=args.scorers,
        )
    )

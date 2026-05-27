"""
Product Portfolio Evaluation

Evaluates product category descriptions against 2 criteria:
1. Category-level description (not single product)
2. Character length (200-1000)

Original evaluation script template by Yafet Tamene (@fafz1234)
Adapted with local scorer implementations.

Usage:
    cd app/adk/agents
    python -m strategy_agent.evaluations.product_portfolio_eval --dataset dataset_product_portfolio_exploded_v0:v0 --eval_name my_eval
"""

import argparse
import asyncio
from typing import Any

import weave
from strategy_agent.evaluations.env_loader import load_env
from strategy_agent.evaluations.scorers.product_portfolio_scorers import (
    ProductCategoryDescriptionScorer,
    ProductCategoryLengthScorer,
)


class ProductPortfolioModel(weave.Model):
    """
    Model that extracts category_description for scoring.

    This is NOT regenerating outputs - it's extracting from
    pre-existing dataset rows for evaluation.
    """

    client: Any

    @weave.op()
    def predict(self, category_description: str) -> dict:
        """
        Return category description for scoring.

        Args:
            category_description: Extracted from dataset via preprocess

        Returns:
            dict with description key that scorers expect
        """
        return {"description": str(category_description)}


async def run_product_portfolio_eval(dataset_name: str, eval_name: str):
    """
    Run product portfolio category evaluation.

    Args:
        dataset_name: Weave dataset reference (e.g., "dataset_product_portfolio_exploded_v0:v0")
        eval_name: Evaluation name
    """
    load_env()
    client = weave.init(project_name="ken-e/ken-e-strategy-agent")

    # Load dataset
    dataset = weave.ref(dataset_name).get()
    print(f"Dataset: {dataset_name} ({len(dataset.rows)} categories)")

    # Create model
    model = ProductPortfolioModel(client=client)

    # Preprocessing
    def preprocess_model_input(row):
        """Extract category_description from dataset row"""
        return {"category_description": row.get("category_description", "")}

    # Use local scorer implementations
    print("\nInitializing scorers:")

    scorers = [
        ProductCategoryLengthScorer(),
        ProductCategoryDescriptionScorer(),
    ]

    print("  ✓ ProductCategoryLengthScorer")
    print("  ✓ ProductCategoryDescriptionScorer")
    print(f"\nScorers ready: {len(scorers)}")

    # Create evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=scorers,
        preprocess_model_input=preprocess_model_input,
        name=eval_name,
    )

    # Run
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
    parser = argparse.ArgumentParser(description="Run product portfolio evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        default="dataset_product_portfolio_exploded_v0:v0",
        help="Weave dataset name (exploded product portfolio dataset)",
    )
    parser.add_argument(
        "--eval_name",
        type=str,
        required=True,
        help="Evaluation name (e.g., product_portfolio_category_eval)",
    )

    args = parser.parse_args()

    asyncio.run(
        run_product_portfolio_eval(dataset_name=args.dataset, eval_name=args.eval_name)
    )

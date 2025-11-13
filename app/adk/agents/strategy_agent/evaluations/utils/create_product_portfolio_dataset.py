"""
Create exploded product portfolio dataset for category-level evaluation.

Takes base dataset and expands each trace's product_portfolio array into
separate rows (one per category).

Original author: Yafet Tamene (@fafz1234)

Usage:
    cd app/adk/agents
    python -m strategy_agent.evaluations.utils.create_product_portfolio_dataset --dataset llm_judge_alignment_set:v28 --output_name dataset_product_portfolio_exploded_v0
"""

import argparse
import weave
from strategy_agent.evaluations.env_loader import load_env
from strategy_agent.evaluations.core.dataset_extractors import extract_product_portfolio

load_env()

# Parse arguments
parser = argparse.ArgumentParser(description='Create exploded product portfolio dataset')
parser.add_argument(
    '--dataset',
    type=str,
    required=True,
)
parser.add_argument(
    '--output_name',
    type=str,
    required=True,
)

args = parser.parse_args()

# Initialize Weave
client = weave.init(project_name="ken-e/ken-e-strategy-agent")

# Load base dataset
base_dataset = weave.ref(args.dataset).get()

print(f"Base dataset: {args.dataset} ({len(base_dataset.rows)} rows)")

# Explode dataset by product categories
expanded_rows = []

for row in base_dataset.rows:
    # Extract trace ID - handle both Call objects and WeaveDict
    trace_ref = row['trace']
    if hasattr(trace_ref, 'id'):
        trace_id = trace_ref.id
    elif isinstance(trace_ref, dict) and 'id' in trace_ref:
        trace_id = trace_ref['id']
    else:
        # Use a placeholder if we can't get ID
        trace_id = str(trace_ref)[:50]

    # Extract product portfolio (smart extractor handles both dev and test datasets)
    portfolio = extract_product_portfolio(client, row)

    if not portfolio:
        continue

    # Create one row per category
    for category_index, category in enumerate(portfolio):
        expanded_rows.append({
            'trace_id': trace_id,
            'category_index': category_index,
            'category_id': category.get('id', ''),
            'category_name': category.get('category_name', ''),
            'category_description': category.get('description', '')
        })

# Create expanded dataset
exploded_dataset = weave.Dataset(
    rows=expanded_rows,
    name=args.output_name
)

# Publish
weave.publish(exploded_dataset)

print(f"Exploded dataset: {len(expanded_rows)} rows")
print(f"  Published as: {args.output_name}")
print(f"  Expansion ratio: {len(expanded_rows) / len(base_dataset.rows):.1f}x")

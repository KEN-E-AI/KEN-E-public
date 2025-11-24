"""
Dataset Extractors

Smart extraction utilities for agent outputs from dataset rows.
Handles both pre-extracted columns and trace traversal fallback.

Original author: Yafet Tamene (@fafz1234)
"""

from weave.trace.vals import WeaveDict


def extract_company_overview(client, row) -> str:
    """
    Extract company_overview_summary from dataset row.

    Tries direct column access first, falls back to trace traversal.

    Args:
        client: Weave client instance
        row: Dataset row

    Returns:
        str: company_overview_summary or empty string if not found
    """
    # Try direct column access (fast path for dev dataset)
    summary = row.get('business_strategy.company_overview_summary', '')

    if summary:
        return str(summary)

    # Fallback: Traverse trace children (for test dataset)
    if 'trace' not in row:
        return ''

    trace_ref = row['trace']

    # Handle both Call objects and WeaveDict references
    if hasattr(trace_ref, 'id'):
        trace_id = trace_ref.id
    elif isinstance(trace_ref, WeaveDict) and 'id' in trace_ref:
        trace_id = trace_ref['id']
    else:
        # trace_ref might be the call itself
        call = trace_ref
        trace_id = None

    if trace_id:
        call = client.get_call(trace_id)
    elif not hasattr(trace_ref, 'children'):
        return ''
    else:
        call = trace_ref

    for child in call.children():
        output = child.output

        if output and isinstance(output, WeaveDict):
            if 'company_overview_summary' in output:
                return str(output['company_overview_summary'])

    return ''


def extract_product_portfolio(client, row) -> list:
    """
    Extract product_portfolio from dataset row.

    Tries direct column access first, falls back to trace traversal.

    Args:
        client: Weave client instance
        row: Dataset row

    Returns:
        list: product_portfolio array or empty list if not found
    """
    # Try direct column access
    portfolio = row.get('business_strategy.product_portfolio', [])

    if portfolio:
        return list(portfolio)

    # Fallback: Traverse trace children
    if 'trace' not in row:
        return []

    trace_ref = row['trace']

    # Handle both Call objects and WeaveDict references
    if hasattr(trace_ref, 'id'):
        trace_id = trace_ref.id
    elif isinstance(trace_ref, WeaveDict) and 'id' in trace_ref:
        trace_id = trace_ref['id']
    else:
        # trace_ref might be the call itself
        call = trace_ref
        trace_id = None

    if trace_id:
        call = client.get_call(trace_id)
    elif not hasattr(trace_ref, 'children'):
        return []
    else:
        call = trace_ref

    for child in call.children():
        output = child.output

        if output and isinstance(output, WeaveDict):
            if 'product_portfolio' in output:
                return list(output['product_portfolio'])

    return []

#!/usr/bin/env python3
"""
Refactored Strategy Agent Orchestrator - Improved modularity and testability.
This refactored version splits complex functions into smaller, testable components.
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from google.adk.agents import Agent, SequentialAgent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content

# Import strategy components
try:
    from agents.strategy_agent.models import StrategyContext
    from agents.strategy_agent.agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent,
    )
    from agents.strategy_agent.firestore import (
        FirestoreClient,
        save_strategy_document_sync,
    )
except ImportError:
    from .models import StrategyContext
    from .agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent,
    )
    from .firestore import FirestoreClient, save_strategy_document_sync

logger = logging.getLogger(__name__)

# Document key mapping remains the same
DOCUMENT_KEY_MAPPING = {
    "business_strategy_doc": "business_strategy",
    "competitive_strategy_doc": "competitive_strategy",
    "customer_strategy_doc": "customer_strategy",
    "marketing_strategy_doc": "marketing_strategy",
    "brand_guidelines_doc": "brand_guidelines",
}


# ============================================================================
# REFACTORED FUNCTIONS - Smaller, single-responsibility functions
# ============================================================================


def initialize_observability(project_name: str = "ken-e-strategy-agent") -> bool:
    """
    Initialize W&B observability if available.

    Args:
        project_name: Name of the W&B project

    Returns:
        True if initialized successfully, False otherwise
    """
    try:
        import weave

        weave.init(project_name=project_name)
        logger.info("W&B observability initialized")
        return True
    except Exception as e:
        logger.warning(f"W&B initialization skipped: {e}")
        return False


def create_strategy_context(
    company_name: str,
    industry: str,
    websites: str,
    customer_regions: str,
    annual_ad_budget: Optional[float] = None,
    account_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> StrategyContext:
    """
    Create a StrategyContext from input parameters.

    Args:
        company_name: Name of the company
        industry: Industry of the company
        websites: Comma-separated list of websites
        customer_regions: Comma-separated list of regions
        annual_ad_budget: Annual advertising budget
        account_id: Account identifier
        tenant_id: Tenant identifier

    Returns:
        StrategyContext instance
    """
    websites_list = [w.strip() for w in websites.split(",") if w.strip()]
    regions_list = [r.strip() for r in customer_regions.split(",") if r.strip()]

    return StrategyContext(
        company_name=company_name,
        websites=websites_list,
        industry=industry,
        customer_regions=regions_list,
        annual_ad_budget=annual_ad_budget,
        account_id=account_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
    )


def create_all_strategy_agents(context: StrategyContext) -> List[Agent]:
    """
    Create all 5 strategy agents in the correct order.

    Args:
        context: StrategyContext with company information

    Returns:
        List of agents in execution order
    """
    logger.info(f"Creating all strategy agents for {context.company_name}")

    agents = [
        create_business_strategy_agent(context),
        create_competitive_strategy_agent(context),
        create_customer_strategy_agent(context),
        create_marketing_strategy_agent(context),
        create_brand_guidelines_agent(context),
    ]

    logger.info(f"Created {len(agents)} strategy agents")
    return agents


def create_sequential_agent(agents: List[Agent]) -> SequentialAgent:
    """
    Create a SequentialAgent from a list of sub-agents.

    Args:
        agents: List of agents to chain together

    Returns:
        SequentialAgent instance
    """
    return SequentialAgent(
        name="strategy_generator",
        sub_agents=agents,
        description="Generates all 5 strategy documents in sequence",
    )


def create_runner_with_session(
    agent: SequentialAgent, app_name: str = "strategy-generator"
) -> Tuple[Runner, Any]:
    """
    Create a Runner with session management.

    Args:
        agent: The sequential agent to run
        app_name: Application name for the runner

    Returns:
        Tuple of (Runner, session)
    """
    session_service = InMemorySessionService()
    session = session_service.create_session_sync()

    runner = Runner(agent=agent, session_service=session_service, app_name=app_name)

    logger.info(f"Created runner with session for {app_name}")
    return runner, session


def execute_runner(
    runner: Runner, session: Any, user_message: str, user_id: str
) -> List[Any]:
    """
    Execute the runner and return events.

    Args:
        runner: The Runner instance
        session: Session object
        user_message: Message to send to the agent
        user_id: User identifier

    Returns:
        List of events from the execution
    """
    logger.info(f"Starting strategy generation for user {user_id}")

    events = runner.run(
        user_id=user_id,
        session_id=session.id,
        new_message=Content(parts=[user_message]),
    )

    logger.info(f"Runner execution completed with {len(list(events))} events")
    return list(events)


def extract_document_from_event(event: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Extract document and type from a single event.

    Args:
        event: Event from runner execution

    Returns:
        Tuple of (doc_type, document) or None if no document found
    """
    if not hasattr(event, "output") or not event.output:
        return None

    # Check each possible output key
    for output_key, doc_type in DOCUMENT_KEY_MAPPING.items():
        if output_key in event.output:
            doc_content = event.output[output_key]

            # Parse JSON if string
            if isinstance(doc_content, str):
                try:
                    doc_content = json.loads(doc_content)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON for {doc_type}")
                    continue

            return doc_type, doc_content

    return None


def process_events_to_documents(events: List[Any]) -> Dict[str, Dict[str, Any]]:
    """
    Process events and extract all documents.

    Args:
        events: List of events from runner execution

    Returns:
        Dictionary mapping doc_type to document content
    """
    documents = {}

    for event in events:
        result = extract_document_from_event(event)
        if result:
            doc_type, doc_content = result
            documents[doc_type] = doc_content
            logger.info(f"Extracted {doc_type} document")

    logger.info(f"Processed {len(documents)} documents from events")
    return documents


def save_single_document(
    doc_type: str,
    document: Dict[str, Any],
    account_id: str,
    user_id: str,
    firestore_client: FirestoreClient,
) -> bool:
    """
    Save a single document to Firestore.

    Args:
        doc_type: Type of document
        document: Document content
        account_id: Account identifier
        user_id: User identifier
        firestore_client: Firestore client instance

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        success = save_strategy_document_sync(
            account_id=account_id,
            doc_type=doc_type,
            document=document,
            user_id=user_id,
            firestore_client=firestore_client,
        )

        if success:
            logger.info(f"Saved {doc_type} to Firestore")
        else:
            logger.warning(f"Failed to save {doc_type} to Firestore")

        return success
    except Exception as e:
        logger.error(f"Error saving {doc_type}: {e}")
        return False


def save_all_documents(
    documents: Dict[str, Dict[str, Any]],
    account_id: str,
    user_id: str,
    firestore_client: FirestoreClient,
) -> Dict[str, bool]:
    """
    Save all documents to Firestore.

    Args:
        documents: Dictionary of documents to save
        account_id: Account identifier
        user_id: User identifier
        firestore_client: Firestore client instance

    Returns:
        Dictionary mapping doc_type to save success status
    """
    save_results = {}

    for doc_type, document in documents.items():
        success = save_single_document(
            doc_type=doc_type,
            document=document,
            account_id=account_id,
            user_id=user_id,
            firestore_client=firestore_client,
        )
        save_results[doc_type] = success

    successful_saves = sum(1 for success in save_results.values() if success)
    logger.info(f"Successfully saved {successful_saves}/{len(documents)} documents")

    return save_results


def format_success_message(
    documents: Dict[str, Dict[str, Any]],
    company_name: str,
    save_results: Optional[Dict[str, bool]] = None,
) -> str:
    """
    Format a success message for the user.

    Args:
        documents: Generated documents
        company_name: Name of the company
        save_results: Optional save results

    Returns:
        Formatted success message
    """
    num_docs = len(documents)

    if save_results:
        num_saved = sum(1 for success in save_results.values() if success)
        message = (
            f"Successfully generated {num_docs} strategy documents for {company_name}. "
        )
        message += f"{num_saved} documents saved to Firestore."
    else:
        message = (
            f"Successfully generated {num_docs} strategy documents for {company_name}."
        )

    if documents:
        message += "\n\nGenerated documents:\n"
        for doc_type in documents:
            message += f"- {doc_type.replace('_', ' ').title()}\n"

    return message


def format_error_message(error: Exception, company_name: str) -> str:
    """
    Format an error message for the user.

    Args:
        error: The exception that occurred
        company_name: Name of the company

    Returns:
        Formatted error message
    """
    return f"Failed to generate strategy documents for {company_name}: {str(error)}"


# ============================================================================
# MAIN ORCHESTRATION FUNCTION - Now much simpler and clearer
# ============================================================================


def execute_strategy_generation(
    company_name: str,
    industry: str,
    websites: str,
    customer_regions: str,
    annual_ad_budget: Optional[float] = None,
    account_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    firestore_client: Optional[FirestoreClient] = None,
) -> str:
    """
    Execute the strategy generation process (refactored version).

    This function orchestrates the entire strategy generation process by
    coordinating smaller, focused functions.

    Args:
        company_name: Name of the company
        industry: Industry of the company
        websites: Comma-separated list of websites
        customer_regions: Comma-separated list of regions
        annual_ad_budget: Annual advertising budget
        account_id: Account identifier
        tenant_id: Tenant identifier
        user_id: User identifier
        project_id: GCP project ID for Firestore
        firestore_client: Optional injected Firestore client

    Returns:
        Success or error message
    """
    try:
        # Step 1: Initialize observability
        initialize_observability()

        # Step 2: Create or use Firestore client
        if not firestore_client:
            firestore_client = FirestoreClient(project_id=project_id)

        # Step 3: Create context
        context = create_strategy_context(
            company_name=company_name,
            industry=industry,
            websites=websites,
            customer_regions=customer_regions,
            annual_ad_budget=annual_ad_budget,
            account_id=account_id,
            tenant_id=tenant_id,
        )

        # Step 4: Create agents
        agents = create_all_strategy_agents(context)
        sequential_agent = create_sequential_agent(agents)

        # Step 5: Create runner with session
        runner, session = create_runner_with_session(sequential_agent)

        # Step 6: Execute runner
        user_message = f"Generate strategy documents for {company_name}"
        events = execute_runner(
            runner=runner,
            session=session,
            user_message=user_message,
            user_id=user_id or "default_user",
        )

        # Step 7: Process events to extract documents
        documents = process_events_to_documents(events)

        # Step 8: Save documents to Firestore
        save_results = {}
        if documents and account_id:
            save_results = save_all_documents(
                documents=documents,
                account_id=account_id,
                user_id=user_id or "default_user",
                firestore_client=firestore_client,
            )

        # Step 9: Format and return success message
        return format_success_message(
            documents=documents, company_name=company_name, save_results=save_results
        )

    except Exception as e:
        logger.error(f"Strategy generation failed: {e}", exc_info=True)
        return format_error_message(e, company_name)


# ============================================================================
# BACKWARDS COMPATIBILITY - Maintain existing function signature
# ============================================================================


def create_strategy_sequential_agent(context: StrategyContext) -> SequentialAgent:
    """
    Create the sequential agent with all 5 strategy sub-agents.
    Maintained for backwards compatibility.

    Args:
        context: StrategyContext with company information

    Returns:
        SequentialAgent that runs all 5 strategy agents in sequence
    """
    agents = create_all_strategy_agents(context)
    return create_sequential_agent(agents)


def process_and_save_documents(
    events: List[Any],
    account_id: str,
    tenant_id: str,
    firestore_client: Optional[FirestoreClient] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Process events and save documents to Firestore.
    Maintained for backwards compatibility.

    Args:
        events: List of events from runner execution
        account_id: Account identifier
        tenant_id: Tenant identifier (unused but kept for compatibility)
        firestore_client: Optional Firestore client

    Returns:
        Dictionary of processed documents
    """
    documents = process_events_to_documents(events)

    if documents and account_id and firestore_client:
        save_all_documents(
            documents=documents,
            account_id=account_id,
            user_id="legacy_user",
            firestore_client=firestore_client,
        )

    return documents

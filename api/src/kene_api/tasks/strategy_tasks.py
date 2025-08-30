"""
Background tasks for strategy document generation.
Handles asynchronous strategy generation after account creation.
"""

import asyncio
import json
import logging
from typing import Any

from google.cloud import firestore

from ..routers.accounts import AccountCreationProgress, ProgressStep
from ..services.progress_cache import progress_cache

logger = logging.getLogger(__name__)


def update_strategy_progress(
    account_id: str, message: str, percentage: int = 60
) -> None:
    """Update the account creation progress during strategy generation.

    Args:
        account_id: Account ID being created
        message: Progress message to display
        percentage: Progress percentage (0-100)
    """
    try:
        # Create progress data using the proper model for consistency
        progress = AccountCreationProgress(
            status="processing",
            percentage=percentage,
            current_step=3,
            total_steps=5,
            message=message,
            steps=[
                ProgressStep(name="Creating account", status="completed"),
                ProgressStep(name="Setting up database", status="completed"),
                ProgressStep(name="Generating strategy", status="processing"),
                ProgressStep(name="Syncing activities", status="pending"),
                ProgressStep(name="Finalizing setup", status="pending"),
            ],
        )

        cache_key = f"account_creation:{account_id}"
        progress_cache.set(cache_key, progress.model_dump(), ttl_seconds=3600)
        logger.info(
            f"[PROGRESS UPDATE] Strategy generation for {account_id}: {message} ({percentage}%)"
        )
    except ImportError as e:
        logger.error(f"Failed to import progress cache for {account_id}: {e}")
    except (AttributeError, TypeError) as e:
        logger.error(f"Failed to update progress for {account_id}: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error updating progress for {account_id}: {e}")


async def trigger_strategy_generation(
    account_id: str,
    company_name: str,
    websites: list[str],
    industry: str,
    customer_regions: list[str],
    user_id: str,
    annual_ad_budget: float | None = None,
    user_context: Any | None = None,  # Allow passing existing UserContext for chat-triggered calls
) -> None:
    """
    Trigger strategy document generation for a new account.
    This runs asynchronously in the background.

    Args:
        account_id: Account ID
        company_name: Company name
        websites: List of company websites
        industry: Industry category
        customer_regions: Customer regions
        user_id: User ID who created the account
        annual_ad_budget: Optional annual ad budget
    """
    try:
        print(f"[STRATEGY_GENERATION] Starting for account {account_id}")
        logger.info(f"Starting strategy generation for account {account_id}")

        # Update progress to show strategy generation is starting
        update_strategy_progress(account_id, "Preparing strategy generation...", 45)

        # Update account status to processing
        await update_account_setup_status(account_id, "processing")

        # Call the strategy agent directly via the Agent Engine
        # This is an internal system call, so we can use the AgentEngineClient directly
        import os

        from ..routers.chat import AgentEngineClient

        # Get project ID from environment
        project_id = os.getenv(
            "VERTEX_AI_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        )

        # Format the information for the strategy agent
        new_information = f"""Project ID: {project_id}
Account ID: {account_id}
Company to analyze: {company_name}
Company websites: {websites}
Industry: {industry}
Customer regions: {", ".join(customer_regions)}"""

        if annual_ad_budget:
            new_information += f"\nAnnual advertising budget: ${annual_ad_budget:,.0f}"

        # Prepare the message for the strategy agent
        # The supervisor agent routes to create_update_strategy tool
        message = f"""Generate all 5 strategy documents for {company_name}

Please execute strategy generation with these parameters:
- company_name: {company_name}
- industry: {industry}
- websites: {",".join(websites)}
- customer_regions: {",".join(customer_regions)}
- account_id: {account_id}
- user_id: {user_id}
- annual_ad_budget: {annual_ad_budget or 0}
- project_id: {project_id}"""

        # Call the strategy agent directly
        logger.info(f"Invoking strategy agent for {company_name} via Agent Engine")

        # Update progress to show we're calling the AI agent
        update_strategy_progress(
            account_id, "Analyzing business and generating strategy documents...", 50
        )

        try:
            # Two paths for calling the strategy agent:
            # 1. If user_context provided (chat-triggered): Use existing authenticated context
            # 2. If no user_context (system-triggered from account creation): Call directly via Vertex AI

            if user_context:
                # Path 1: User-triggered from chat - use existing authentication
                logger.info(f"User-triggered strategy generation for {company_name}")

                # Initialize the Agent Engine client
                agent_client = AgentEngineClient()

                # Call the agent with the existing user context
                response_content, session_id = await agent_client.chat_completion(
                    messages=[{"role": "user", "content": message}],
                    user_context=user_context,
                    session_id=f"strategy_{account_id}",
                    conversation_name=f"Strategy Generation - {company_name}",
                )

                if response_content:
                    logger.info(f"Strategy generation completed for {company_name}")
                    result = response_content
                else:
                    logger.error(
                        f"Strategy generation returned empty response for {company_name}"
                    )
                    result = "Empty response from strategy agent"

            else:
                # Path 2: System-triggered from account creation - call Vertex AI directly
                logger.info(f"System-triggered strategy generation for {company_name}")

                # Import Vertex AI libraries
                import vertexai
                from vertexai import agent_engines

                # Get environment variables
                project_id = os.getenv(
                    "VERTEX_AI_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT_ID")
                )
                location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
                agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")

                if not agent_engine_id:
                    raise ValueError("VERTEX_AI_AGENT_ENGINE_ID not configured")

                # Initialize Vertex AI
                vertexai.init(project=project_id, location=location)

                # Get the agent engine
                agent_engine = agent_engines.get(agent_engine_id)

                # Call the agent directly
                print(f"[AGENT_ENGINE] Calling with message: {len(message)} chars")
                logger.info(
                    f"Calling agent engine with message length: {len(message)} chars"
                )
                logger.info(f"Message preview: {message[:200]}...")
                logger.info(f"Agent Engine ID: {agent_engine_id}")
                logger.info(f"Project: {project_id}, Location: {location}")

                try:
                    logger.info("About to call agent_engine.stream_query...")
                    response = agent_engine.stream_query(
                        message=message, user_id=user_id
                    )
                    logger.info("stream_query call initiated successfully")
                except Exception as e:
                    logger.error(f"Failed to call stream_query: {e}", exc_info=True)
                    raise

                # Collect response
                response_parts = []
                chunk_count = 0
                logger.info("Starting to collect response chunks...")

                for chunk in response:
                    chunk_count += 1
                    logger.info(f"Processing chunk {chunk_count}...")

                    if isinstance(chunk, dict):
                        logger.info(
                            f"Chunk {chunk_count} is dict with keys: {list(chunk.keys())[:10]}"
                        )

                        # Log the full chunk for debugging
                        import json

                        try:
                            logger.debug(
                                f"Full chunk {chunk_count}: {json.dumps(chunk, default=str)[:500]}"
                            )
                        except Exception:
                            logger.debug(
                                f"Chunk {chunk_count} (non-serializable): {str(chunk)[:500]}"
                            )

                        # Handle nested response structure
                        if "content" in chunk and isinstance(chunk["content"], dict):
                            content = chunk["content"]
                            if "parts" in content and isinstance(
                                content["parts"], list
                            ):
                                for part in content["parts"]:
                                    if isinstance(part, dict) and "text" in part:
                                        response_parts.append(part["text"])
                                        logger.info(
                                            f"  Added text part from chunk {chunk_count}: {len(part['text'])} chars"
                                        )
                                        logger.debug(
                                            f"  Text preview: {part['text'][:200]}..."
                                        )
                        else:
                            response_parts.append(str(chunk))
                            logger.info(
                                f"  Added chunk {chunk_count} as string: {len(str(chunk))} chars"
                            )
                    else:
                        response_parts.append(str(chunk))
                        logger.info(
                            f"Chunk {chunk_count} type: {type(chunk).__name__}, size: {len(str(chunk))}"
                        )

                logger.info(f"✅ Received total {chunk_count} chunks from agent engine")

                result = "".join(response_parts).strip()
                if result:
                    logger.info(
                        f"Strategy generation completed for {company_name}: {len(result)} chars"
                    )

                    # The strategy agent saves documents internally during execution
                    # We just need to verify they were created
                    await verify_strategy_documents_created(account_id)
                else:
                    logger.error(
                        f"Strategy generation returned empty response for {company_name}"
                    )
                    result = "Empty response from strategy agent"

        except Exception as e:
            logger.error(f"Failed to call strategy agent: {e}")
            result = f"Error calling strategy agent: {e}"

        logger.info(
            f"Strategy generation result preview: {result[:500] if result else 'Empty'}..."
        )

        # Update progress to show strategy generation is complete
        update_strategy_progress(
            account_id, "Strategy documents generated successfully!", 75
        )

        # Update account status to ready
        await update_account_setup_status(account_id, "ready", completed=True)

        # Final progress update - mark as complete
        final_progress = AccountCreationProgress(
            status="completed",
            percentage=100,
            current_step=5,
            total_steps=5,
            message="Account setup complete!",
            steps=[
                ProgressStep(name="Creating account", status="completed"),
                ProgressStep(name="Setting up database", status="completed"),
                ProgressStep(name="Generating strategy", status="completed"),
                ProgressStep(name="Syncing activities", status="completed"),
                ProgressStep(name="Finalizing setup", status="completed"),
            ],
        )
        cache_key = f"account_creation:{account_id}"
        progress_cache.set(
            cache_key, final_progress.model_dump(), ttl_seconds=300
        )  # Keep for 5 minutes after completion

        logger.info(
            f"Successfully completed strategy generation for account {account_id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to generate strategy documents for account {account_id}: {e}"
        )
        # Don't update status to ready if generation failed
        # Keep it in processing so it can be retried


async def update_account_setup_status(
    account_id: str, status: str, completed: bool = False
) -> None:
    """
    Update the setup status of an account in Neo4j.

    Args:
        account_id: Account ID
        status: New status (pending, processing, ready)
        completed: Whether setup is completed
    """
    try:
        from ..database import get_neo4j_service

        db = await get_neo4j_service()

        # Build the update query
        if status == "processing" and not completed:
            # Starting processing
            query = """
            MATCH (a:Account {account_id: $account_id})
            SET a.setup_status = $status,
                a.setup_started_at = datetime()
            RETURN a
            """
            params = {"account_id": account_id, "status": status}
        elif completed:
            # Completed processing
            query = """
            MATCH (a:Account {account_id: $account_id})
            SET a.setup_status = $status,
                a.setup_completed_at = datetime()
            RETURN a
            """
            params = {"account_id": account_id, "status": status}
        else:
            # Just update status
            query = """
            MATCH (a:Account {account_id: $account_id})
            SET a.setup_status = $status
            RETURN a
            """
            params = {"account_id": account_id, "status": status}

        await db.execute_write_query(query, params)
        logger.info(f"Updated setup_status to '{status}' for account {account_id}")

    except Exception as e:
        logger.error(f"Failed to update setup_status for account {account_id}: {e}")


async def verify_strategy_documents_created(account_id: str) -> bool:
    """
    Verify that strategy documents were created by the agent.

    The strategy agent saves documents directly to Firestore collections
    named strategy_docs_{account_id} with documents for each strategy type.

    Args:
        account_id: Account ID to check

    Returns:
        True if documents exist, False otherwise
    """
    try:
        db = firestore.Client()
        collection_name = f"strategy_docs_{account_id}"

        logger.info(f"Verifying strategy documents in collection: {collection_name}")

        # Check for expected strategy documents
        expected_docs = [
            "business_strategy",
            "competitive_strategy",
            "customer_strategy",
            "marketing_strategy",
            "brand_guidelines",
        ]

        found_docs = []
        doc_quality = {}

        for doc_type in expected_docs:
            doc_ref = db.collection(collection_name).document(doc_type)
            doc = doc_ref.get()
            if doc.exists:
                found_docs.append(doc_type)
                doc_data = doc.to_dict()

                # Check document quality
                content = doc_data.get("content", {})
                if isinstance(content, dict):
                    content_size = len(json.dumps(content))
                    has_keys = len(content.keys())
                    doc_quality[doc_type] = {
                        "size": content_size,
                        "keys": has_keys,
                        "status": doc_data.get("status", "unknown"),
                        "version": doc_data.get("version", 0),
                    }
                    logger.info(
                        f"Found {doc_type} document - size: {content_size} bytes, keys: {has_keys}, status: {doc_data.get('status', 'unknown')}"
                    )
                else:
                    logger.warning(
                        f"Found {doc_type} but content is not a dict: {type(content).__name__}"
                    )

        # Log summary
        if doc_quality:
            logger.info(f"Document quality summary for {account_id}:")
            for doc_type, quality in doc_quality.items():
                logger.info(
                    f"  - {doc_type}: {quality['size']} bytes, {quality['keys']} keys, v{quality['version']}"
                )

        if len(found_docs) == len(expected_docs):
            logger.info(
                f"✅ All {len(expected_docs)} strategy documents found for account {account_id}"
            )
            return True
        elif len(found_docs) > 0:
            logger.warning(
                f"⚠️ Only {len(found_docs)}/{len(expected_docs)} strategy documents found for account {account_id}"
            )
            logger.warning(f"  Found: {found_docs}")
            logger.warning(
                f"  Missing: {[d for d in expected_docs if d not in found_docs]}"
            )
            return True  # Partial success
        else:
            logger.error(f"❌ No strategy documents found for account {account_id}")
            return False

    except Exception as e:
        logger.error(
            f"Failed to verify strategy documents for account {account_id}: {e}"
        )
        return False


def trigger_strategy_generation_sync(
    account_id: str,
    company_name: str,
    websites: list[str],
    industry: str,
    customer_regions: list[str],
    user_id: str,
    annual_ad_budget: float | None = None,
    user_context: Any | None = None,
) -> None:
    """
    Synchronous wrapper for triggering strategy generation.
    Creates a new event loop if needed.
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule the coroutine to run in the background
            _ = asyncio.create_task(
                trigger_strategy_generation(
                    account_id=account_id,
                    company_name=company_name,
                    websites=websites,
                    industry=industry,
                    customer_regions=customer_regions,
                    user_id=user_id,
                    annual_ad_budget=annual_ad_budget,
                    user_context=user_context,
                )
            )
        else:
            # Run in the existing loop
            loop.run_until_complete(
                trigger_strategy_generation(
                    account_id=account_id,
                    company_name=company_name,
                    websites=websites,
                    industry=industry,
                    customer_regions=customer_regions,
                    user_id=user_id,
                    annual_ad_budget=annual_ad_budget,
                    user_context=user_context,
                )
            )
    except RuntimeError:
        # No event loop, create a new one
        asyncio.run(
            trigger_strategy_generation(
                account_id=account_id,
                company_name=company_name,
                websites=websites,
                industry=industry,
                customer_regions=customer_regions,
                user_id=user_id,
                annual_ad_budget=annual_ad_budget,
                user_context=user_context,
            )
        )

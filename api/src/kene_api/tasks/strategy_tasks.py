"""
Background tasks for strategy document generation.
Handles asynchronous strategy generation after account creation.
"""

import asyncio
import json
import logging
import time
from typing import Any

import backoff
from google.api_core import exceptions as google_exceptions
from google.cloud import firestore

# Removed progress tracking imports - simplified progress tracking

logger = logging.getLogger(__name__)


# Removed update_strategy_progress function - simplified progress tracking


async def trigger_strategy_generation(
    account_id: str,
    company_name: str,
    websites: list[str],
    industry: str,
    customer_regions: list[str],
    user_id: str,
    annual_ad_budget: float | None = None,
    uploaded_document_urls: list[str] | None = None,
    user_context: Any
    | None = None,  # Allow passing existing UserContext for chat-triggered calls
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
        uploaded_document_urls: Optional list of GCS URLs for uploaded strategy documents
    """
    try:
        print(f"[STRATEGY_GENERATION] Starting for account {account_id}")
        logger.info(f"Starting strategy generation for account {account_id}")

        # Log strategy generation is starting (progress tracking simplified)
        logger.info(f"Setting up database structures for account {account_id}")

        # Update account status to processing
        await update_account_setup_status(account_id, "processing")

        # Call the strategy agent directly via the Agent Engine
        # This is an internal system call, so we can use the AgentEngineClient directly
        import os

        from ..routers.chat import AgentEngineClient
        from ..utils.secrets import get_env_or_secret

        # Get project ID based on environment
        environment = os.getenv("ENVIRONMENT", "development").lower()

        # Map environment to project ID
        project_mapping = {
            "development": "ken-e-dev",
            "staging": "ken-e-staging",
            "production": "ken-e-production",
        }

        # Get the appropriate project ID for the environment
        project_id = project_mapping.get(environment, "ken-e-dev")

        # Log the project being used
        logger.info(f"Using project ID '{project_id}' for environment '{environment}'")

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
        # The supervisor agent routes to create_strategy tool
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

        if uploaded_document_urls:
            message += f"\n- uploaded_documents: {','.join(uploaded_document_urls)}"
            logger.info(
                f"Including {len(uploaded_document_urls)} uploaded documents in strategy generation request"
            )

        # Call the strategy agent directly
        logger.info(f"Invoking strategy agent for {company_name} via Agent Engine")

        # Log we're starting research (progress tracking simplified)
        logger.info(f"Researching business for account {account_id}")

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

                    # IMPORTANT: Wait for documents to be created, same as system-triggered path
                    max_wait_time = 1800  # 30 minutes max wait for documents
                    poll_interval = 60  # Check every 60 seconds
                    elapsed_time = 0
                    all_docs_complete = False

                    logger.info(
                        f"[User-triggered] Waiting for all strategy documents to be complete for account {account_id}..."
                    )

                    while elapsed_time < max_wait_time:
                        all_docs_complete = await verify_strategy_documents_created(
                            account_id, require_all=True
                        )

                        if all_docs_complete:
                            logger.info(
                                f"✅ [User-triggered] All strategy documents are complete for account {account_id}"
                            )
                            break

                        logger.info(
                            f"[User-triggered] Documents not yet complete, waiting {poll_interval} seconds... (elapsed: {elapsed_time}s)"
                        )
                        await asyncio.sleep(poll_interval)
                        elapsed_time += poll_interval

                    if not all_docs_complete:
                        logger.error(
                            f"❌ [User-triggered] Strategy documents not all complete after {max_wait_time} seconds for account {account_id}"
                        )
                        await update_account_setup_status(
                            account_id, "failed", completed=False
                        )
                        logger.error(
                            f"[User-triggered] Account {account_id} marked as failed due to incomplete strategy documents"
                        )
                        return  # Exit early without marking as completed
                else:
                    logger.error(
                        f"Strategy generation returned empty response for {company_name}"
                    )
                    result = "Empty response from strategy agent"
                    # Mark account as failed if no response from agent
                    await update_account_setup_status(
                        account_id,
                        "failed",
                        completed=False,
                        error_message="Strategy generation failed - no response from agent. Please try again.",
                    )
                    logger.error(
                        f"Account {account_id} marked as failed due to empty agent response"
                    )
                    return  # Exit early

            else:
                # Path 2: System-triggered from account creation - call Vertex AI directly
                logger.info(f"System-triggered strategy generation for {company_name}")

                # Import Vertex AI libraries
                import vertexai
                from vertexai import agent_engines

                # Get environment variables and map to correct project
                environment = os.getenv("ENVIRONMENT", "development").lower()

                # Map environment to project ID
                project_mapping = {
                    "development": "ken-e-dev",
                    "staging": "ken-e-staging",
                    "production": "ken-e-production",
                }

                # Use environment-specific project or fall back to env vars
                default_project = os.getenv(
                    "VERTEX_AI_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT_ID")
                )
                project_id = project_mapping.get(
                    environment, default_project or "ken-e-dev"
                )

                location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

                # Use STRATEGY_SUPERVISOR_ENGINE_ID for strategy generation, fall back to old env var
                agent_engine_id = get_env_or_secret(
                    "STRATEGY_SUPERVISOR_ENGINE_ID"
                ) or get_env_or_secret("VERTEX_AI_AGENT_ENGINE_ID")

                if not agent_engine_id:
                    raise ValueError(
                        "STRATEGY_SUPERVISOR_ENGINE_ID or VERTEX_AI_AGENT_ENGINE_ID not configured"
                    )

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
                logger.info(f"Agent engine object: {agent_engine}")
                logger.info(f"Agent engine type: {type(agent_engine)}")

                try:
                    logger.info("About to call agent_engine.stream_query with retry logic...")
                    
                    # Define retry decorator for ServiceUnavailable errors
                    @backoff.on_exception(
                        backoff.expo,
                        google_exceptions.ServiceUnavailable,
                        max_tries=3,
                        max_time=60,  # Max 60 seconds of retry attempts
                        on_backoff=lambda details: logger.warning(
                            f"ServiceUnavailable error, retrying... (attempt {details['tries']}/{3})"
                        )
                    )
                    def stream_query_with_retry():
                        return agent_engine.stream_query(
                            message=message, user_id=user_id
                        )
                    
                    response = stream_query_with_retry()
                    logger.info("stream_query call initiated successfully")
                    logger.info(f"Response type: {type(response)}")

                    # Try to check if response is iterable
                    try:
                        # Check if it has __iter__ method
                        if hasattr(response, "__iter__"):
                            logger.info("Response is iterable")
                        else:
                            logger.warning("Response is NOT iterable")
                    except Exception as check_error:
                        logger.error(f"Error checking response type: {check_error}")

                except Exception as e:
                    logger.error(f"Failed to call stream_query: {e}", exc_info=True)
                    raise

                # Collect response with timeout
                response_parts = []
                chunk_count = 0
                logger.info("Starting to collect response chunks...")

                # Set a timeout for collecting chunks (25 minutes max for agent response)
                agent_timeout = 1500  # 25 minutes
                start_time = time.time()

                # Retry logic for chunk iteration
                max_chunk_retries = 3
                chunk_retry_count = 0
                
                while chunk_retry_count < max_chunk_retries:
                    try:
                        logger.info(f"Agent response object type: {type(response)}")
                        # Add a flag to track if we got any response
                        got_response = False

                        for chunk in response:
                            got_response = True
                            # Check if we've exceeded the timeout
                            elapsed = time.time() - start_time
                            if elapsed > agent_timeout:
                                logger.error(
                                    f"Agent engine timeout after {elapsed:.1f} seconds, {chunk_count} chunks received"
                                )
                                break

                            chunk_count += 1
                            logger.info(f"Processing chunk {chunk_count}...")

                        # Log progress for debugging (progress tracking simplified)
                        # TODO: Progress logs are failing
                        if chunk_count == 5:
                            logger.info(
                                f"Researching competitors for account {account_id}"
                            )
                        elif chunk_count == 10:
                            logger.info(
                                f"Researching customers for account {account_id}"
                            )
                        elif chunk_count == 15:
                            logger.info(
                                f"Inferring marketing strategy for account {account_id}"
                            )
                        elif chunk_count == 20:
                            logger.info(
                                f"Reviewing brand styles for account {account_id}"
                            )

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
                            if "content" in chunk and isinstance(
                                chunk["content"], dict
                            ):
                                content = chunk["content"]
                                if "parts" in content and isinstance(
                                    content["parts"], list
                                ):
                                    for part in content["parts"]:
                                        if isinstance(part, dict):
                                            # Handle text parts
                                            if "text" in part:
                                                response_parts.append(part["text"])
                                                logger.info(
                                                    f"  Added text part from chunk {chunk_count}: {len(part['text'])} chars"
                                                )
                                                logger.debug(
                                                    f"  Text preview: {part['text'][:200]}..."
                                                )
                                            # Handle function_call parts (likely contains strategy documents)
                                            elif "function_call" in part:
                                                function_call = part["function_call"]
                                                logger.info(
                                                    f"  Found function_call in chunk {chunk_count}: {type(function_call)}"
                                                )
                                                # Extract the function call content
                                                if isinstance(function_call, dict):
                                                    # Log the function name if available
                                                    if "name" in function_call:
                                                        logger.info(
                                                            f"    Function: {function_call['name']}"
                                                        )
                                                    # Extract arguments/response
                                                    if "response" in function_call:
                                                        response_parts.append(
                                                            str(
                                                                function_call[
                                                                    "response"
                                                                ]
                                                            )
                                                        )
                                                        logger.info(
                                                            f"    Added function response: {len(str(function_call['response']))} chars"
                                                        )
                                                    elif "output" in function_call:
                                                        response_parts.append(
                                                            str(function_call["output"])
                                                        )
                                                        logger.info(
                                                            f"    Added function output: {len(str(function_call['output']))} chars"
                                                        )
                                                    elif "args" in function_call:
                                                        response_parts.append(
                                                            str(function_call["args"])
                                                        )
                                                        logger.info(
                                                            f"    Added function args: {len(str(function_call['args']))} chars"
                                                        )
                                                    else:
                                                        # Just append the whole function_call as string
                                                        response_parts.append(
                                                            str(function_call)
                                                        )
                                                        logger.info(
                                                            f"    Added entire function_call: {len(str(function_call))} chars"
                                                        )
                                                else:
                                                    response_parts.append(
                                                        str(function_call)
                                                    )
                                                    logger.info(
                                                        f"    Added function_call as string: {len(str(function_call))} chars"
                                                    )
                                            # Log other part types for debugging
                                            elif "thought_signature" in part:
                                                logger.info(
                                                    f"  Found thought_signature in chunk {chunk_count} (skipping)"
                                                )
                                            else:
                                                logger.info(
                                                    f"  Unknown part type in chunk {chunk_count}: {list(part.keys())}"
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
                        
                        # Successfully processed all chunks, break retry loop
                        break
                        
                    except google_exceptions.ServiceUnavailable as e:
                        chunk_retry_count += 1
                        if chunk_retry_count >= max_chunk_retries:
                            logger.error(
                                f"ServiceUnavailable error after {max_chunk_retries} retries during chunk iteration: {e}"
                            )
                            # Mark account as failed with retry message
                            await update_account_setup_status(
                                account_id,
                                "failed",
                                completed=False,
                                error_message="Service temporarily unavailable. Please try again in a few minutes.",
                            )
                            return  # Exit early
                        else:
                            wait_time = 2 ** chunk_retry_count  # Exponential backoff: 2, 4, 8 seconds
                            logger.warning(
                                f"ServiceUnavailable during chunk iteration, retrying in {wait_time}s... (attempt {chunk_retry_count}/{max_chunk_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            # Recreate the response stream
                            response = stream_query_with_retry()
                            chunk_count = 0  # Reset chunk count for new stream
                            response_parts = []  # Reset response parts
                            
                    except Exception as e:
                        # Non-retryable error
                        logger.error(
                            f"Error iterating over agent response chunks: {e}",
                            exc_info=True,
                        )
                        logger.error(f"Only received {chunk_count} chunks before error")
                        break  # Exit retry loop for non-retryable errors

                # Check if we actually got a response
                if not got_response:
                    logger.error(
                        "No response received from agent engine - response iterator was empty or failed"
                    )
                    result = ""
                else:
                    logger.info(
                        f"✅ Received total {chunk_count} chunks from agent engine"
                    )
                    result = "".join(response_parts).strip()
                    logger.info(f"Total response length: {len(result)} chars")

                # Log first 500 chars of result for debugging
                if result:
                    logger.info(f"Response preview: {result[:500]}...")
                    logger.info(
                        f"Strategy generation completed for {company_name}: {len(result)} chars"
                    )
                else:
                    logger.warning("Agent returned empty response!")

                # Only proceed with document verification if we got a valid response
                if result and got_response:
                    # Wait for all documents to be fully created before marking as complete
                    # Poll for document completion with timeout
                    max_wait_time = 1800  # 30 minutes max wait for documents
                    poll_interval = 15  # Check every 15 seconds
                    elapsed_time = 0
                    all_docs_complete = False

                    logger.info(
                        f"Waiting for all strategy documents to be complete for account {account_id}..."
                    )

                    while elapsed_time < max_wait_time:
                        # Check if all documents are complete (strict mode)
                        all_docs_complete = await verify_strategy_documents_created(
                            account_id, require_all=True
                        )

                        if all_docs_complete:
                            logger.info(
                                f"✅ All strategy documents are complete for account {account_id}"
                            )
                            break

                        # Wait before checking again
                        logger.info(
                            f"Documents not yet complete, waiting {poll_interval} seconds... (elapsed: {elapsed_time}s)"
                        )
                        await asyncio.sleep(poll_interval)
                        elapsed_time += poll_interval

                    if not all_docs_complete:
                        logger.error(
                            f"❌ Strategy documents not all complete after {max_wait_time} seconds for account {account_id}"
                        )
                        # DO NOT mark as completed if documents are not ready
                        # Mark as failed instead
                        await update_account_setup_status(
                            account_id,
                            "failed",
                            completed=False,
                            error_message="Strategy document generation timed out. Please try again.",
                        )
                        logger.error(
                            f"Account {account_id} marked as failed due to incomplete strategy documents"
                        )
                        return  # Exit early without marking as completed
                else:
                    logger.error(
                        f"Strategy generation returned empty response for {company_name}"
                    )
                    # Mark as failed if no response from agent
                    await update_account_setup_status(
                        account_id,
                        "failed",
                        completed=False,
                        error_message="Strategy generation returned no content. Please try again.",
                    )
                    logger.error(
                        f"Account {account_id} marked as failed due to empty agent response"
                    )
                    return  # Exit early without marking as completed

        except Exception as e:
            logger.error(f"Failed to call strategy agent: {e}")
            # Mark as failed on exception
            await update_account_setup_status(
                account_id,
                "failed",
                completed=False,
                error_message=f"Strategy generation failed: {str(e)[:200]}",
            )
            logger.error(
                f"Account {account_id} marked as failed due to agent error: {e}"
            )
            return  # Exit early without marking as completed

        # Only reach here if everything succeeded
        logger.info(
            f"✅ Successfully completed strategy generation for account {account_id}"
        )

        # Update account status to completed
        await update_account_setup_status(account_id, "completed", completed=True)

        # Send email notification
        try:
            from ..email_service import get_email_service
            from google.cloud import firestore

            # Get user email from Firestore
            db = firestore.Client()
            user_doc = db.collection('users').document(user_id).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_email = user_data.get('profile', {}).get('email')

                if user_email:
                    email_service = get_email_service()
                    email_sent = email_service.send_account_ready_email(
                        to_email=user_email,
                        company_name=company_name,
                        account_id=account_id
                    )
                    if email_sent:
                        logger.info(f"✅ Sent account ready email to {user_email}")
                    else:
                        logger.warning(f"Failed to send email to {user_email}")
                else:
                    logger.warning(f"No email found for user {user_id}")
            else:
                logger.warning(f"User {user_id} not found in Firestore")
        except Exception as email_error:
            # Don't fail the whole process if email fails
            logger.warning(f"Failed to send completion email: {email_error}")

    except Exception as e:
        logger.error(
            f"Failed to generate strategy documents for account {account_id}: {e}"
        )
        # Don't update status to ready if generation failed
        # Keep it in processing so it can be retried


async def update_account_setup_status(
    account_id: str, status: str, completed: bool = False, error_message: str = None
) -> None:
    """
    Update the setup status of an account in Neo4j.

    Args:
        account_id: Account ID
        status: New status (pending, processing, ready, failed)
        completed: Whether setup is completed
        error_message: Optional error message when status is "failed"
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
        elif status == "failed":
            # Failed processing
            query = """
            MATCH (a:Account {account_id: $account_id})
            SET a.setup_status = $status,
                a.setup_error = $error_message,
                a.setup_failed_at = datetime()
            RETURN a
            """
            params = {
                "account_id": account_id,
                "status": status,
                "error_message": error_message or "Strategy generation failed",
            }
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


async def verify_strategy_documents_created(
    account_id: str, require_all: bool = True
) -> bool:
    """
    Verify that strategy documents were created by the agent.

    The strategy agent saves documents directly to Firestore collections
    named strategy_docs_{account_id} with documents for each strategy type.

    Args:
        account_id: Account ID to check
        require_all: If True, all 4 documents must exist and be complete. If False, partial success is allowed.

    Returns:
        True if documents meet the requirement, False otherwise
    """
    try:
        db = firestore.Client()
        collection_name = f"strategy_docs_{account_id}"

        logger.info(f"Verifying strategy documents in collection: {collection_name}")

        # Check for expected strategy documents (removed customer_strategy)
        expected_docs = [
            "business_strategy",
            "competitive_strategy",
            "marketing_strategy",
            "brand_guidelines",
        ]

        found_docs = []
        complete_docs = []
        doc_quality = {}

        for doc_type in expected_docs:
            doc_ref = db.collection(collection_name).document(doc_type)
            doc = doc_ref.get()
            if doc.exists:
                found_docs.append(doc_type)
                doc_data = doc.to_dict()

                # Check document quality and completeness
                content = doc_data.get("content", {})
                status = doc_data.get("status", "")  # May not have status field

                if isinstance(content, dict):
                    content_size = len(json.dumps(content))
                    has_keys = len(content.keys())

                    # Consider document complete based primarily on content size and structure
                    # Status field is optional - many docs don't have it
                    is_complete = content_size > 1000 and has_keys > 3

                    # If status field exists and indicates not ready, override
                    if status and status.lower() in [
                        "draft",
                        "in_progress",
                        "pending",
                        "generating",
                    ]:
                        is_complete = False
                        logger.info(
                            f"Document {doc_type} marked incomplete due to status: {status}"
                        )

                    if is_complete:
                        complete_docs.append(doc_type)

                    doc_quality[doc_type] = {
                        "size": content_size,
                        "keys": has_keys,
                        "status": status,
                        "version": doc_data.get("version", 0),
                        "complete": is_complete,
                    }
                    logger.info(
                        f"Found {doc_type} document - size: {content_size} bytes, keys: {has_keys}, status: {status}, complete: {is_complete}"
                    )
                else:
                    logger.warning(
                        f"Found {doc_type} but content is not a dict: {type(content).__name__}"
                    )

        # Log detailed summary
        logger.info(f"Document verification summary for {account_id}:")
        logger.info(f"  Expected documents: {expected_docs}")
        logger.info(
            f"  Found documents: {found_docs} ({len(found_docs)}/{len(expected_docs)})"
        )
        logger.info(
            f"  Complete documents: {complete_docs} ({len(complete_docs)}/{len(expected_docs)})"
        )

        if doc_quality:
            logger.info(f"Document quality details:")
            for doc_type, quality in doc_quality.items():
                logger.info(
                    f"  - {doc_type}: {quality['size']} bytes, {quality['keys']} keys, status: '{quality['status']}', complete: {quality['complete']}"
                )

        if require_all:
            # Strict mode: all 5 documents must be complete
            if len(complete_docs) == len(expected_docs):
                logger.info(
                    f"✅ All {len(expected_docs)} strategy documents are complete for account {account_id}"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ Only {len(complete_docs)}/{len(expected_docs)} strategy documents are complete for account {account_id}"
                )
                logger.warning(f"  Complete: {complete_docs}")
                logger.warning(
                    f"  Incomplete: {[d for d in expected_docs if d not in complete_docs]}"
                )
                return False
        else:
            # Lenient mode: partial success is acceptable
            if len(found_docs) > 0:
                logger.info(
                    f"✅ {len(found_docs)}/{len(expected_docs)} strategy documents found for account {account_id}"
                )
                return True
            else:
                logger.error(f"❌ No strategy documents found for account {account_id}")
                return False

    except Exception as e:
        logger.error(
            f"Failed to verify strategy documents for account {account_id}: {e}",
            exc_info=True,
        )
        # Return False in strict mode, True in lenient mode if error occurs
        # This prevents account from being stuck if Firestore is temporarily unavailable
        return not require_all


def trigger_strategy_generation_sync(
    account_id: str,
    company_name: str,
    websites: list[str],
    industry: str,
    customer_regions: list[str],
    user_id: str,
    annual_ad_budget: float | None = None,
    uploaded_document_urls: list[str] | None = None,
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
                    uploaded_document_urls=uploaded_document_urls,
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
                    uploaded_document_urls=uploaded_document_urls,
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
                uploaded_document_urls=uploaded_document_urls,
                user_context=user_context,
            )
        )

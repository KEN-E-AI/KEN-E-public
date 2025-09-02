#!/usr/bin/env python3
"""
Strategy Agent Orchestrator - Manages execution and persistence of strategy documents.
"""

import json
import logging
import uuid
from typing import Any

from google.adk import Runner
from google.adk.agents import Agent, SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content
from vertexai.preview import reasoning_engines

# Import strategy components
try:
    # Absolute imports for deployment
    from agents.strategy_agent.agents import (
        create_brand_guidelines_agent,
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
    )
    from agents.strategy_agent.artifact_utils import (
        load_uploaded_documents_as_artifacts,
    )
    from agents.strategy_agent.firestore import (
        FirestoreClient,
        get_strategy_document,
        save_strategy_document_sync,
        update_strategy_document,
    )
    from agents.strategy_agent.models import StrategyContext
except ImportError:
    # Relative imports for local testing
    from .agents import (
        create_brand_guidelines_agent,
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
    )
    from .artifact_utils import load_uploaded_documents_as_artifacts
    from .firestore import (
        FirestoreClient,
    )
    from .models import StrategyContext

logger = logging.getLogger(__name__)

# Initialize W&B observability if available
try:
    import weave

    weave.init(project_name="ken-e-strategy-agent")
    logger.info("W&B observability initialized")
except Exception as e:
    logger.warning(f"W&B initialization skipped: {e}")


# Define the mapping of output keys to document types
DOCUMENT_KEY_MAPPING = {
    "business_strategy_doc": "business_strategy",
    "competitive_strategy_doc": "competitive_strategy",
    "customer_strategy_doc": "customer_strategy",
    "marketing_strategy_doc": "marketing_strategy",
    "brand_guidelines_doc": "brand_guidelines",
}


def create_strategy_sequential_agent(context: StrategyContext) -> SequentialAgent:
    """
    Create the sequential agent with all 5 strategy sub-agents.

    Args:
        context: StrategyContext with company information

    Returns:
        SequentialAgent that runs all 5 strategy agents in sequence
    """
    logger.info(f"Creating Sequential Agent for {context.company_name}")

    # Create all 5 strategy agents in order
    logger.info("[AGENT CREATION] Creating business_strategy_agent")
    business_agent = create_business_strategy_agent(context)
    logger.info("[AGENT CREATION] Creating competitive_strategy_agent")
    competitive_agent = create_competitive_strategy_agent(context)
    logger.info("[AGENT CREATION] Creating customer_strategy_agent")
    customer_agent = create_customer_strategy_agent(context)
    logger.info("[AGENT CREATION] Creating marketing_strategy_agent")
    marketing_agent = create_marketing_strategy_agent(context)
    logger.info("[AGENT CREATION] Creating brand_guidelines_agent")
    brand_agent = create_brand_guidelines_agent(context)
    logger.info("[AGENT CREATION] All 5 agents created successfully")

    # Chain them together in a SequentialAgent
    strategy_sequential_agent = SequentialAgent(
        name="strategy_generator",
        sub_agents=[
            business_agent,
            competitive_agent,
            customer_agent,
            marketing_agent,
            brand_agent,
        ],
        description="Generates all 5 strategy documents in sequence",
    )

    logger.info(
        f"✅ Sequential Agent created with 5 strategy agents for {context.company_name}"
    )
    return strategy_sequential_agent


def execute_strategy_generation(
    company_name: str,
    industry: str,
    websites: str,
    customer_regions: str,
    account_id: str,
    user_id: str,
    annual_ad_budget: float = 0.0,
    project_id: str | None = None,
    uploaded_documents: list[str] | None = None,
    firestore_client: FirestoreClient | None = None,
) -> str:
    """
    Execute the complete strategy generation process.

    This function:
    1. Creates the strategy context
    2. Initializes the sequential agent
    3. Runs the agent pipeline
    4. Monitors execution and captures documents
    5. Saves documents to Firestore as they're generated

    Args:
        company_name: Name of the company
        industry: Industry sector
        websites: Comma-separated list of websites
        customer_regions: Comma-separated list of regions
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        annual_ad_budget: Annual advertising budget
        project_id: Optional GCP project ID

    Returns:
        Status message indicating success or failure
    """
    try:
        logger.info(f"[EXECUTION] Starting strategy generation for {company_name}")

        # Use provided client or create new one
        client = firestore_client or FirestoreClient(project_id=project_id)

        # Create context from inputs
        context = StrategyContext(
            account_id=account_id,
            user_id=user_id,
            company_name=company_name,
            websites=websites.split(",") if websites else [],
            industry=industry,
            customer_regions=customer_regions.split(",") if customer_regions else [],
            annual_ad_budget=annual_ad_budget,
        )

        # Create the sequential agent with all 5 strategy agents
        strategy_sequential_agent = create_strategy_sequential_agent(context)

        # Set up session management
        session_service = InMemorySessionService()
        app_name = f"strategy_gen_{account_id}"
        session_user_id = user_id or "system"
        session_id = f"session_{account_id}_{uuid.uuid4().hex[:8]}"

        # Initialize state with empty uploaded documents
        initial_state = {"uploaded_strategy_documents": {}}
        
        # Create session with initial state
        session = session_service.create_session_sync(
            app_name=app_name, user_id=session_user_id, session_id=session_id, state=initial_state
        )
        logger.info(f"[EXECUTION] Created session: {session_id}")

        # Set up artifact service using the extracted utility function
        # This simplifies the function and improves testability
        artifact_service = load_uploaded_documents_as_artifacts(
            uploaded_documents=uploaded_documents,
            account_id=account_id,
            session_user_id=session_user_id,
            session_id=session_id,
            project_id=project_id,
        )

        # Verify artifact loading if documents were uploaded
        if uploaded_documents:
            logger.info(
                f"[ARTIFACT_VERIFICATION] Verifying {len(uploaded_documents)} uploaded documents"
            )
            loaded_count = 0

            try:
                # List artifact keys to verify they were loaded
                # Check if we have a GcsArtifactService with sync methods
                if hasattr(artifact_service, '_list_artifact_keys'):
                    # Use the synchronous private method directly
                    artifact_keys = artifact_service._list_artifact_keys(
                        app_name,
                        session_user_id,
                        session_id
                    )
                else:
                    # For InMemoryArtifactService or other async-only services
                    import asyncio
                    
                    async def list_keys():
                        return await artifact_service.list_artifact_keys(
                            app_name=app_name,
                            user_id=session_user_id,
                            session_id=session_id
                        )
                    
                    # Try to handle async properly
                    try:
                        loop = asyncio.get_running_loop()
                        # If there's a running loop, use nest_asyncio
                        import nest_asyncio
                        nest_asyncio.apply()
                        artifact_keys = asyncio.run(list_keys())
                    except RuntimeError:
                        # No running loop, safe to use asyncio.run
                        artifact_keys = asyncio.run(list_keys())

                # Check for input_strategy_ prefixed artifacts
                strategy_artifacts = [
                    key for key in artifact_keys
                    if key.startswith("input_strategy_")
                ]
                loaded_count = len(strategy_artifacts)

                logger.info(
                    f"[ARTIFACT_VERIFICATION] Found {loaded_count}/{len(uploaded_documents)} strategy artifacts"
                )
                for artifact_key in strategy_artifacts:
                    logger.info(f"  ✓ Loaded: {artifact_key}")

                # Log any missing documents
                if loaded_count < len(uploaded_documents):
                    logger.warning(
                        "[ARTIFACT_VERIFICATION] Some documents may not have loaded successfully"
                    )

            except Exception as e:
                logger.error(f"[ARTIFACT_VERIFICATION] Failed to verify artifacts: {e}")
        
        # Load uploaded documents into session state for agents to access
        loaded_docs = {}  # Initialize outside the if block so it's available later
        logger.info(f"[DOCUMENT_CHECK] Uploaded documents parameter: {uploaded_documents}")
        logger.info(f"[DOCUMENT_CHECK] Type of uploaded_documents: {type(uploaded_documents)}")
        
        # Handle uploaded documents - can be either GCS URLs or artifact keys
        if uploaded_documents:
            # Check if these are GCS URLs (start with gs://) or artifact keys
            if isinstance(uploaded_documents, str):
                # Parse comma-separated string of URLs
                uploaded_documents = [url.strip() for url in uploaded_documents.split(',') if url.strip()]
            
            logger.info(f"[DOCUMENT_CHECK] Processing {len(uploaded_documents)} documents")
            
            # Check if these are GCS URLs
            if uploaded_documents and uploaded_documents[0].startswith('gs://'):
                logger.info("[DOCUMENT_LOADING] Loading documents from GCS URLs")
                from google.cloud import storage
                storage_client = storage.Client(project=project_id)
                
                for gcs_url in uploaded_documents:
                    try:
                        # Parse GCS URL: gs://bucket/path/to/file
                        if gcs_url.startswith('gs://'):
                            parts = gcs_url[5:].split('/', 1)
                            if len(parts) == 2:
                                bucket_name, blob_path = parts
                                bucket = storage_client.bucket(bucket_name)
                                blob = bucket.blob(blob_path)
                                
                                # Download the content
                                content = None
                                
                                # Check if it's a PDF file
                                if blob_path.lower().endswith('.pdf'):
                                    logger.info(f"[DOCUMENT_LOADING] Detected PDF file: {blob_path}")
                                    try:
                                        # Download as bytes for PDF processing
                                        content_bytes = blob.download_as_bytes()
                                        
                                        # Try to extract text from PDF
                                        try:
                                            import PyPDF2
                                            import io
                                            
                                            pdf_file = io.BytesIO(content_bytes)
                                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                                            
                                            extracted_text = []
                                            for page_num in range(len(pdf_reader.pages)):
                                                page = pdf_reader.pages[page_num]
                                                text = page.extract_text()
                                                if text:
                                                    extracted_text.append(text)
                                            
                                            content = "\n".join(extracted_text)
                                            logger.info(f"[DOCUMENT_LOADING] Extracted {len(content)} chars from PDF")
                                        except ImportError:
                                            logger.warning("[DOCUMENT_LOADING] PyPDF2 not available, returning placeholder")
                                            content = f"[PDF document - {len(content_bytes)} bytes - text extraction requires PyPDF2]"
                                        except Exception as pdf_error:
                                            logger.error(f"[DOCUMENT_LOADING] PDF extraction failed: {pdf_error}")
                                            content = f"[PDF document - {len(content_bytes)} bytes - extraction failed]"
                                    except Exception as download_error:
                                        logger.error(f"[DOCUMENT_LOADING] Failed to download PDF: {download_error}")
                                else:
                                    # Try downloading as text for non-PDF files
                                    try:
                                        content = blob.download_as_text()
                                    except Exception as download_error:
                                        # Try downloading as bytes if text fails
                                        logger.info(f"[DOCUMENT_LOADING] Text download failed, trying as bytes: {download_error}")
                                        content_bytes = blob.download_as_bytes()
                                        content = f"[Binary document - {len(content_bytes)} bytes]"
                                        logger.warning(f"[DOCUMENT_LOADING] Downloaded binary file {blob_path}")
                                
                                # Extract filename from path
                                filename = blob_path.split('/')[-1]
                                doc_key = f"input_strategy_{filename}"
                                
                                if content:
                                    loaded_docs[doc_key] = content
                                    logger.info(f"[DOCUMENT_LOADING] Loaded {doc_key} from GCS - {len(content) if content else 0} chars")
                                else:
                                    logger.error(f"[DOCUMENT_LOADING] No content retrieved for {doc_key}")
                    except Exception as e:
                        logger.error(f"[DOCUMENT_LOADING] Failed to load {gcs_url}: {e}")
            
        # Also try loading from artifact service if available
        if uploaded_documents and hasattr(artifact_service, '_load_artifact') and not loaded_docs:
            logger.info(f"[STATE_LOADING] Loading {len(uploaded_documents)} uploaded documents into session state")
            
            try:
                # Get list of artifact keys
                if hasattr(artifact_service, '_list_artifact_keys'):
                    logger.info(f"[ARTIFACT_KEYS] Calling _list_artifact_keys with app={app_name}, user={session_user_id}, session={session_id}")
                    artifact_keys = artifact_service._list_artifact_keys(
                        app_name,
                        session_user_id,
                        session_id
                    )
                    logger.info(f"[ARTIFACT_KEYS] Found {len(artifact_keys)} total artifact keys: {artifact_keys}")
                    
                    # Filter for strategy documents
                    strategy_artifacts = [
                        key for key in artifact_keys
                        if key.startswith("input_strategy_")
                    ]
                    logger.info(f"[ARTIFACT_KEYS] Filtered to {len(strategy_artifacts)} strategy artifacts: {strategy_artifacts}")
                    
                    # Load each document
                    for artifact_key in strategy_artifacts:
                        try:
                            # Load the artifact content
                            artifact_content = artifact_service._load_artifact(
                                app_name,
                                session_user_id,
                                session_id,
                                artifact_key,
                                None  # version
                            )
                            
                            if artifact_content:
                                # Extract text content from the Part object
                                if hasattr(artifact_content, 'text'):
                                    doc_text = artifact_content.text
                                elif hasattr(artifact_content, 'data'):
                                    # Try to decode binary data
                                    try:
                                        doc_text = artifact_content.data.decode('utf-8', errors='ignore')
                                    except:
                                        doc_text = str(artifact_content.data)
                                else:
                                    doc_text = str(artifact_content)
                                
                                # Store in loaded_docs dictionary
                                loaded_docs[artifact_key] = doc_text
                                logger.info(f"[STATE_LOADING] Loaded {artifact_key} - {len(doc_text)} chars")
                        
                        except Exception as e:
                            logger.error(f"[STATE_LOADING] Failed to load {artifact_key}: {e}")
                    
                    # Update session state with loaded documents
                    if loaded_docs:
                        session.state["uploaded_strategy_documents"] = loaded_docs
                        # Note: InMemorySessionService doesn't have update_session_sync
                        # The state is already updated by reference
                        logger.info(f"[STATE_LOADING] Added {len(loaded_docs)} documents to session state")
                        for doc_name in loaded_docs:
                            doc_content = loaded_docs[doc_name]
                            logger.info(f"  ✓ {doc_name}: {len(doc_content) if doc_content else 0} chars")
                    
            except Exception as e:
                logger.error(f"[STATE_LOADING] Failed to load documents into state: {e}")

        # Create runner with artifact service
        runner = Runner(
            agent=strategy_sequential_agent,
            app_name=app_name,
            session_service=session_service,
            artifact_service=artifact_service,
        )

        # Prepare execution message with uploaded documents
        execution_input = f"Generate all 5 strategy documents for {company_name} in the {industry} industry."
        
        # Add uploaded documents to the initial message if they exist
        if loaded_docs:
            logger.info(f"[MESSAGE_PREP] Adding {len(loaded_docs)} uploaded documents to initial message")
            execution_input += "\n\n=== UPLOADED STRATEGY DOCUMENTS ===\n"
            execution_input += "The following strategy documents have been uploaded and should be used as the primary source for your analysis:\n\n"
            for doc_name, doc_content in loaded_docs.items():
                execution_input += f"--- Document: {doc_name} ---\n"
                execution_input += f"{doc_content}\n\n"
                logger.info(f"[MESSAGE_PREP] Added {doc_name} to message - {len(doc_content)} chars")
            execution_input += "=== END OF UPLOADED DOCUMENTS ===\n"
            execution_input += "\nIMPORTANT: Prioritize information from these uploaded documents over web searches. Only search for information not found in these documents."
        else:
            logger.info("[MESSAGE_PREP] No uploaded documents to add to initial message")
        
        message_content = Content(role="user", parts=[{"text": execution_input}])

        # Run the agent pipeline
        logger.info("[EXECUTION] Starting runner with 5 sequential agents")
        events = runner.run(
            user_id=session_user_id, session_id=session_id, new_message=message_content
        )

        # Process events and save documents
        logger.info("[EXECUTION] Processing events from agent execution")
        generated_documents = process_and_save_documents(
            events, account_id, user_id, client
        )
        logger.info(
            f"[EXECUTION] Document processing complete - found {len(generated_documents)} documents"
        )

        logger.info(f"[EXECUTION] Completed strategy generation for {company_name}")
        logger.info(
            f"[EXECUTION] Generated documents: {list(generated_documents.keys())}"
        )

        return f"Successfully generated {len(generated_documents)} strategy documents for {company_name}: {', '.join(generated_documents.keys())}"

    except Exception as e:
        error_msg = f"Failed to generate strategy documents: {e}"
        logger.error(error_msg)
        return error_msg


def process_and_save_documents(
    events, account_id: str, user_id: str, firestore_client: FirestoreClient
) -> dict[str, Any]:
    """
    Process execution events and save documents to Firestore.

    This function monitors the event stream from the agent execution,
    captures documents as they're generated, and saves them to Firestore.
    Now handles unique output keys for each document type.

    Args:
        events: Generator of execution events from Runner
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        firestore_client: Firestore client for saving documents

    Returns:
        Dictionary of generated documents
    """
    generated_documents = {}
    event_count = 0

    for event in events:
        event_count += 1

        # Log event details
        event_info = f"[EVENT #{event_count}]"
        if hasattr(event, "author"):
            event_info += f" author='{event.author}'"

            # Log specific agent transitions
            if "business_strategy_agent" in str(event.author):
                logger.info(
                    f"[BUSINESS AGENT] Event from business agent: {event.author}"
                )
            elif "competitive_strategy_agent" in str(event.author):
                logger.info(
                    f"[COMPETITIVE AGENT] Event from competitive agent: {event.author}"
                )
            elif "customer_strategy_agent" in str(event.author):
                logger.info(
                    f"[CUSTOMER AGENT] Event from customer agent: {event.author}"
                )
            elif "marketing_strategy_agent" in str(event.author):
                logger.info(
                    f"[MARKETING AGENT] Event from marketing agent: {event.author}"
                )
            elif "brand_" in str(event.author):
                logger.info(f"[BRAND AGENT] Event from brand agent: {event.author}")

        logger.info(event_info)

        # Check for documents in state delta
        if hasattr(event, "actions") and event.actions:
            if hasattr(event.actions, "state_delta") and event.actions.state_delta:
                state_delta = event.actions.state_delta

                # Log all keys in state_delta for debugging
                if state_delta:
                    logger.info(
                        f"[STATE_DELTA] Keys present: {list(state_delta.keys())[:10]}"
                    )  # Limit to first 10 keys

                # Check for each document type's unique key
                for doc_key, doc_type in DOCUMENT_KEY_MAPPING.items():
                    if doc_key in state_delta:
                        doc_content = state_delta[doc_key]
                        logger.info(
                            f"[DOCUMENT] Found {doc_key} in state_delta for {doc_type}"
                        )

                        # Parse the document
                        parsed_doc = parse_document_content(doc_content)

                        if parsed_doc:
                            # Save to memory
                            generated_documents[doc_type] = parsed_doc
                            logger.info(
                                f"[DOCUMENT] Captured {doc_type} from key {doc_key} - {len(json.dumps(parsed_doc))} bytes"
                            )

                            # Save to Firestore immediately
                            try:
                                result = firestore_client.save_strategy_document_sync(
                                    account_id=account_id,
                                    doc_type=doc_type,
                                    content=parsed_doc,
                                    user_id=user_id,
                                )

                                if result:
                                    logger.info(
                                        f"[FIRESTORE] Successfully saved {doc_type}"
                                    )
                                else:
                                    logger.error(
                                        f"[FIRESTORE] Failed to save {doc_type}"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"[FIRESTORE] Error saving {doc_type}: {e}"
                                )
                        else:
                            logger.error(
                                f"[DOCUMENT] Failed to parse content for {doc_type} from key {doc_key}"
                            )

    # Log final summary
    logger.info(f"[EXECUTION SUMMARY] Total events processed: {event_count}")
    logger.info(
        f"[EXECUTION SUMMARY] Documents generated: {list(generated_documents.keys())}"
    )
    expected_docs = [
        "business_strategy",
        "competitive_strategy",
        "customer_strategy",
        "marketing_strategy",
        "brand_guidelines",
    ]
    missing_docs = [doc for doc in expected_docs if doc not in generated_documents]
    if missing_docs:
        logger.warning(f"[EXECUTION SUMMARY] Missing documents: {missing_docs}")

    return generated_documents


def parse_document_content(doc_content: Any) -> dict | None:
    """
    Parse document content from JSON string or dict.

    Args:
        doc_content: Raw document content (may be JSON string or dict)

    Returns:
        Parsed document dictionary or None if parsing fails
    """
    # If already a dict, return it
    if isinstance(doc_content, dict):
        return doc_content

    # If string, try to parse as JSON
    if isinstance(doc_content, str):
        doc_content = clean_json_string(doc_content)

        try:
            return json.loads(doc_content)
        except json.JSONDecodeError as e:
            logger.error(f"[DOCUMENT] Failed to parse JSON: {e}")
            return None

    # Unknown type
    logger.warning(f"[DOCUMENT] Unknown content type: {type(doc_content)}")
    return None


def clean_json_string(content: str) -> str:
    """
    Clean JSON string by removing markdown code blocks and fixing escape sequences.

    Args:
        content: Raw JSON string that may contain markdown or invalid escapes

    Returns:
        Cleaned JSON string
    """
    import re

    # Remove markdown code blocks if present
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]  # Remove ```json
    if content.endswith("```"):
        content = content[:-3]  # Remove ```

    # Fix common JSON issues
    # Replace single backslashes that aren't part of valid escape sequences
    # Valid escapes are: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", content.strip())

    return cleaned


# Create the main strategy agent for deployment
def create_strategy_agent_for_deployment():
    """
    Create a wrapper agent for deployment that handles strategy generation requests.
    """
    return Agent(
        name="strategy_orchestrator",
        model="gemini-2.0-flash",
        instruction="""You coordinate strategy document generation.
        
When you receive a request to generate strategy documents, you MUST use the execute_strategy_generation tool.

Look for messages that contain parameters like:
- company_name
- industry
- websites
- customer_regions
- account_id
- user_id
- annual_ad_budget
- project_id

Extract these parameters from the message and call execute_strategy_generation with them.

For example, if you receive:
"Please execute strategy generation with these parameters:
- company_name: Example Corp
- industry: Technology
- websites: example.com
- customer_regions: USA,Europe
- account_id: acc_123
- user_id: user_456
- annual_ad_budget: 100000
- project_id: ken-e-dev"

You should call execute_strategy_generation(
    company_name="Example Corp",
    industry="Technology", 
    websites="example.com",
    customer_regions="USA,Europe",
    account_id="acc_123",
    user_id="user_456",
    annual_ad_budget=100000.0,
    project_id="ken-e-dev"
)

ALWAYS use the execute_strategy_generation tool when asked to generate strategies.
Do NOT just respond with text - actually execute the tool.""",
        tools=[execute_strategy_generation],
    )


# Create the agent and app for deployment
strategy_agent = create_strategy_agent_for_deployment()

try:
    # Wrap with AdkApp for deployment
    app = reasoning_engines.AdkApp(agent=strategy_agent, enable_tracing=True)
    logger.info("✅ Strategy Agent ready for deployment")
except Exception as e:
    logger.error(f"Failed to create Strategy Agent app: {e}")
    app = None


__all__ = [
    "app",
    "create_strategy_sequential_agent",
    "execute_strategy_generation",
    "strategy_agent",
]

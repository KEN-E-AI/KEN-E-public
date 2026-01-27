"""
Chat API endpoints for Vertex AI Agent Engine integration.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import vertexai
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.adk.sessions import VertexAiSessionService
from pydantic import BaseModel, Field

from ..auth.models import UserContext
from ..auth.user_context import get_current_user_context
from ..database import get_neo4j_service
from ..firestore import get_firestore_service
from ..services.ga_credential_helper import GACredentialHelper

# Add project root to path for app module imports
_project_root = Path(__file__).parent.parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import structured logging and Sprint 2 context utilities
# Note: These imports are after sys.path modification (E402) - required for app module access
from app.adk.agents.utils.context_loader import (  # noqa: E402
    CAMPAIGN_KEYWORDS,
    inject_campaign_context,
    load_campaign_context,
    should_load_campaigns,
)
from app.adk.agents.utils.context_loader import (  # noqa: E402
    inject_organization_context,
)
from app.adk.agents.utils.structured_logging import (  # noqa: E402
    get_structured_logger,
    log_context,
)

logger = get_structured_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


async def load_organization_context_from_neo4j(account_id: str) -> str | None:
    """Load organization context from Neo4j using API's Neo4j service.

    Loads Account info and Brand Voice/Tone, formats as markdown.

    Args:
        account_id: Account identifier

    Returns:
        Formatted markdown context string, or None if loading fails
    """
    query = """
    MATCH (acc:Account {account_id: $account_id})

    // Brand Guidelines
    OPTIONAL MATCH (acc)-[:FOLLOWS_THESE_BRAND_GUIDELINES]->(brand:BrandIdentity)
    OPTIONAL MATCH (brand)-[:USES_COMMUNICATION_STYLE]->(voice:VoiceAndTone)
    OPTIONAL MATCH (brand)-[:HAS_TRAITS_AND_CHARACTERISTICS]->(personality:BrandPersonality)
    OPTIONAL MATCH (brand)-[:HAS_MISSION]->(mission:MissionAndValues)

    RETURN {
      account: {
        account_id: acc.account_id,
        company_name: acc.company_name,
        company_overview: acc.company_overview,
        industry: acc.industry,
        websites: acc.websites,
        customer_regions: acc.customer_regions
      },
      brand: {
        voice_tone_description: voice.description,
        personality_description: personality.description,
        mission_description: mission.description
      }
    } as context
    """

    try:
        neo4j_service = await get_neo4j_service()
        result = await neo4j_service.execute_query(query, {"account_id": account_id})

        if not result or not result[0]:
            logger.warning(
                "No organization context found",
                extra=log_context(
                    component="organization_context",
                    action="load",
                    account_id=account_id,
                    success=False,
                    error_message="No Neo4j results",
                ),
            )
            return None

        context_data = result[0]["context"]

        # Format as markdown
        account = context_data.get("account", {})
        brand = context_data.get("brand", {})

        markdown_parts = ["---"]
        if account.get("account_id"):
            markdown_parts.append(f"account_id: {account['account_id']}")
        if account.get("company_name"):
            markdown_parts.append(f"company: {account['company_name']}")
        if account.get("industry"):
            markdown_parts.append(f"industry: {account['industry']}")
        markdown_parts.append("---\n")

        markdown_parts.append("# Company Context\n")
        if account.get("company_overview"):
            markdown_parts.append(f"{account['company_overview']}\n")

        # Brand guidelines section
        has_brand_guidelines = False
        if brand and any(brand.values()):
            has_brand_guidelines = True
            markdown_parts.append("\n## Brand Voice & Communication Style\n")

            if brand.get("voice_tone_description"):
                markdown_parts.append(f"\n**Voice & Tone:**\n{brand['voice_tone_description']}\n")

            if brand.get("personality_description"):
                markdown_parts.append(f"\n**Brand Personality:**\n{brand['personality_description']}\n")

            if brand.get("mission_description"):
                markdown_parts.append(f"\n**Mission & Values:**\n{brand['mission_description']}\n")

        context_str = "".join(markdown_parts)

        # Structured logging for production visibility
        logger.info(
            "Organization context loaded",
            extra=log_context(
                component="organization_context",
                action="load",
                account_id=account_id,
                success=True,
                extra={
                    "company_name": account.get("company_name", "unknown"),
                    "has_brand_guidelines": has_brand_guidelines,
                    "context_length": len(context_str),
                },
            ),
        )

        return context_str

    except Exception as e:
        logger.error(
            "Failed to load organization context",
            extra=log_context(
                component="organization_context",
                action="load",
                account_id=account_id,
                success=False,
                error_message=str(e),
            ),
        )
        return None


async def inject_context_into_message(
    formatted_input: str,
    user_input: str,
    account_id: str | None,
    session_id: str,
    streaming: bool = False,
) -> str:
    """Inject organization and campaign context into the user message.

    This helper function consolidates context injection logic used by both
    streaming and non-streaming chat endpoints.

    Args:
        formatted_input: The formatted user message (may include conversation history)
        user_input: The raw user input (for keyword detection)
        account_id: Account ID for context loading
        session_id: Session ID for logging
        streaming: Whether this is called from a streaming endpoint (for log messages)

    Returns:
        The formatted_input with context injected
    """
    if not account_id:
        return formatted_input

    suffix = " (streaming)" if streaming else ""

    # Always inject organization context (Level 1 - always loaded per design doc)
    # This ensures brand voice, tone, and company info are available to all agents
    try:
        org_context = await load_organization_context_from_neo4j(account_id)
        if org_context:
            formatted_input = inject_organization_context(formatted_input, org_context)
            logger.info(
                f"Organization context injected{suffix}",
                extra=log_context(
                    component="organization_context",
                    action="inject",
                    account_id=account_id,
                    session_id=session_id,
                    success=True,
                    extra={"context_length": len(org_context)},
                ),
            )
    except Exception as e:
        logger.warning(
            f"Failed to inject organization context{suffix}",
            extra=log_context(
                component="organization_context",
                action="inject",
                success=False,
                error_message=str(e),
            ),
        )
        # Continue without org context - graceful degradation

    # Check if user message mentions campaigns and load campaign context on-demand
    if should_load_campaigns(user_input):
        try:
            campaign_context = load_campaign_context(account_id)
            if campaign_context:
                formatted_input = inject_campaign_context(formatted_input, campaign_context)
                logger.info(
                    f"Campaign context injected{suffix}",
                    extra=log_context(
                        component="campaign_context",
                        action="inject",
                        account_id=account_id,
                        session_id=session_id,
                        success=True,
                        extra={
                            "context_length": len(campaign_context),
                            "trigger_keywords": [
                                kw for kw in CAMPAIGN_KEYWORDS if kw in user_input.lower()
                            ][:3],
                        },
                    ),
                )
        except Exception as e:
            logger.warning(
                f"Failed to load campaign context{suffix}",
                extra=log_context(
                    component="campaign_context",
                    action="inject",
                    success=False,
                    error_message=str(e),
                ),
            )
            # Continue without campaign context - graceful degradation

    return formatted_input


class ChatMessage(BaseModel):
    """A chat message."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: str | None = Field(None, description="Message timestamp")


class ChatRequest(BaseModel):
    """Request for chat completion."""

    messages: list[ChatMessage] = Field(..., description="List of chat messages")
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: str | None = Field(
        None, description="Session ID for conversation tracking"
    )
    conversation_name: str | None = Field(
        None, description="Optional name for the conversation"
    )
    account_id: str | None = Field(
        None,
        description="Account ID for the selected account context",
        min_length=10,
        max_length=100,
    )


class ChatResponse(BaseModel):
    """Response from chat completion."""

    role: str = Field(default="assistant", description="Response role")
    content: str = Field(..., description="Response content")
    session_id: str = Field(..., description="Session ID")
    conversation_name: str | None = Field(
        None, description="Conversation name if provided"
    )


class ConversationInfo(BaseModel):
    """Information about a conversation/session."""

    session_id: str = Field(..., description="Session ID")
    conversation_name: str | None = Field(
        None, description="User-assigned conversation name"
    )
    created_at: datetime = Field(..., description="When the conversation was created")
    last_updated: datetime = Field(
        ..., description="When the conversation was last updated"
    )
    message_count: int = Field(
        ..., description="Number of messages in the conversation"
    )


class ConversationListResponse(BaseModel):
    """Response for listing conversations."""

    conversations: list[ConversationInfo] = Field(
        ..., description="List of user conversations"
    )
    total_count: int = Field(..., description="Total number of conversations")


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    conversation_name: str | None = Field(
        None, description="Optional name for the conversation"
    )
    account_id: str | None = Field(
        None,
        description="Account ID for the conversation context",
        min_length=10,
        max_length=100,
    )


class UpdateConversationRequest(BaseModel):
    """Request to update conversation metadata."""

    conversation_name: str | None = Field(
        None, description="New name for the conversation"
    )


class AgentEngineClient:
    """Client for interacting with Vertex AI Agent Engine using agent_engines API with ADK session management."""

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

        # Use KEN_E_ENGINE_ID if available, fall back to VERTEX_AI_AGENT_ENGINE_ID for backward compatibility
        # Use get_env_or_secret to resolve Secret Manager paths
        from shared.secrets import get_env_or_secret
        engine_id_full = get_env_or_secret("KEN_E_ENGINE_ID") or get_env_or_secret(
            "VERTEX_AI_AGENT_ENGINE_ID"
        )

        if not engine_id_full:
            print("[CHAT INIT] KEN_E_ENGINE_ID or VERTEX_AI_AGENT_ENGINE_ID not set")
            logger.warning(
                "KEN_E_ENGINE_ID or VERTEX_AI_AGENT_ENGINE_ID not set. Chat functionality will be limited."
            )
            self.agent_engine_id_full = None
            self.agent_engine_id = None
        else:
            # Strip any whitespace/newlines from Secret Manager values
            engine_id_full = engine_id_full.strip()

            # Store the full resource path for logging
            self.agent_engine_id_full = engine_id_full
            # Extract just the numeric ID from the resource path for API calls
            # Handles both formats: "projects/.../reasoningEngines/12345" and "12345"
            self.agent_engine_id = engine_id_full.split("/")[-1]
            print(f"[CHAT INIT] Full engine ID: {engine_id_full}")
            print(f"[CHAT INIT] Extracted numeric ID: {self.agent_engine_id}")
            logger.info(f"Resolved Agent Engine ID: {self.agent_engine_id} (from {engine_id_full})")

        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)

        self._agent_engine: Any = None
        self._session_service: VertexAiSessionService | None = None
        self._user_sessions = {}  # Cache for user session metadata

    @property
    def agent_engine(self):
        """Lazy-load the agent engine using agent_engines.get()."""
        if self._agent_engine is None and self.agent_engine_id:
            try:
                print("[AGENT_ENGINE] About to call agent_engines.get()")
                print(f"[AGENT_ENGINE] agent_engine_id_full: {self.agent_engine_id_full}")
                print(f"[AGENT_ENGINE] agent_engine_id (numeric): {self.agent_engine_id}")
                logger.info(
                    f"Attempting to connect to Agent Engine: {self.agent_engine_id_full or self.agent_engine_id}"
                )
                logger.info(
                    f"Using project: {self.project_id}, location: {self.location}"
                )

                # Use vertexai.Client to get the deployed agent engine
                # The correct API requires using a Client instance
                resource_name = self.agent_engine_id_full
                print(f"[AGENT_ENGINE] Creating vertexai.Client with project={self.project_id}, location={self.location}")
                print(f"[AGENT_ENGINE] Calling client.agent_engines.get(name={resource_name})")
                logger.info(f"Calling agent_engines.get with name parameter: {resource_name}")

                client = vertexai.Client(project=self.project_id, location=self.location)
                self._agent_engine = client.agent_engines.get(name=resource_name)

                # Log the available methods for debugging
                available_methods = [
                    method
                    for method in dir(self._agent_engine)
                    if not method.startswith("_")
                ]
                logger.info(f"Available methods on agent engine: {available_methods}")

                logger.info(
                    f"Successfully connected to Agent Engine: {self.agent_engine_id_full or self.agent_engine_id}"
                )
            except Exception as e:
                logger.error(f"Failed to connect to Agent Engine: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Agent Engine is currently unavailable: {e!s}",
                )
        return self._agent_engine

    @property
    def session_service(self) -> VertexAiSessionService:
        """Lazy-load the ADK session service."""
        if self._session_service is None:
            try:
                logger.info("Initializing ADK VertexAiSessionService")
                self._session_service = VertexAiSessionService(
                    project=self.project_id,
                    location=self.location,
                    agent_engine_id=self.agent_engine_id,  # Already extracted in __init__
                )
                logger.info("Successfully initialized VertexAiSessionService")
            except Exception as e:
                logger.error(f"Failed to initialize VertexAiSessionService: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Session service is currently unavailable: {e!s}",
                )
        return self._session_service

    async def create_conversation(
        self,
        user_id: str,
        user_context: UserContext | None = None,
        conversation_name: str | None = None,
        account_id: str | None = None,
    ) -> str:
        """Create a new conversation using ADK session service with initial state.

        Args:
            user_id: User identifier
            user_context: User context containing account access and credentials (optional)
            conversation_name: Optional name for the conversation

        Returns:
            Session ID for the created conversation
        """
        try:
            logger.info(f"Creating new conversation for user {user_id}")

            # Prepare initial session state
            initial_state: dict[str, Any] = {}

            # Add account context if user_context provided
            if user_context and user_context.accessible_accounts:
                # Use provided account_id if given, otherwise use first accessible account
                if account_id:
                    # SECURITY: Validate user has access to requested account
                    if not user_context.has_account_access(account_id):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied to account {account_id}",
                        )
                    selected_account_id = account_id
                else:
                    selected_account_id = user_context.accessible_accounts[0]

                initial_state["account_id"] = selected_account_id
                initial_state["accessible_accounts"] = user_context.accessible_accounts
                logger.info(
                    f"Setting session state with account_id: {selected_account_id}"
                )

                # Load organization context from Neo4j (API has access)
                # NOTE: Organization context may be None if:
                # - Account doesn't have brand guidelines configured yet
                # - Neo4j query fails (connection issues)
                # - Account has incomplete data (missing brand nodes)
                # Agents will function without org context, just without brand voice/tone
                try:
                    logger.info(f"Loading organization context for account: {initial_state['account_id']}")
                    org_context = await load_organization_context_from_neo4j(
                        account_id=initial_state["account_id"]
                    )
                    if org_context:
                        initial_state["organization_context"] = org_context
                        logger.info(f"Loaded organization context: {len(org_context)} chars")
                    else:
                        logger.warning(f"No organization context found for account: {initial_state['account_id']}")
                except Exception as e:
                    logger.error(f"Failed to load organization context: {e}")
                    # Continue without org context - graceful degradation

                # Prefetch GA credentials for the selected account
                try:
                    firestore_service = get_firestore_service()
                    db = firestore_service.get_client()
                    ga_helper = GACredentialHelper(db)

                    # Use the selected account directly
                    logger.info(f"Loading GA credentials for account: {selected_account_id}")
                    ga_creds = await ga_helper.get_and_format_credentials(selected_account_id)

                    if ga_creds:
                        # Get raw credentials for storage in state
                        raw_creds = await ga_helper.get_oauth_credentials(selected_account_id)
                        if raw_creds:
                            raw_creds = await ga_helper.refresh_if_expired(
                                selected_account_id, raw_creds
                            )

                        # Store in session state (NOT in message)
                        property_ids_to_store = ga_creds.get("selected_property_ids", [])

                        initial_state["ga_credentials"] = {
                            "access_token": raw_creds.get("access_token")
                            if raw_creds
                            else None,
                            "refresh_token": raw_creds.get("refresh_token")
                            if raw_creds
                            else None,
                            "tenant_id": ga_creds["tenant_id"],
                            "selected_property_ids": property_ids_to_store,
                            "selected_properties": ga_creds.get(
                                "selected_properties", []
                            ),
                            "expires_at": raw_creds.get("expires_at")
                            if raw_creds
                            else None,
                        }
                        logger.info(
                            f"Stored GA credentials with {len(property_ids_to_store)} properties for account: {selected_account_id}"
                        )
                    else:
                        logger.warning(f"No GA credentials found for account: {selected_account_id}")
                except Exception as e:
                    logger.error(f"Failed to prefetch GA credentials: {e}")
                    # Continue without GA credentials

            # Create ADK session
            try:
                logger.info(f"Attempting to create ADK session for user: {user_id}")
                logger.info(
                    f"Session service initialized: {self._session_service is not None}"
                )
                logger.info(f"Agent engine ID: {self.agent_engine_id}")
                if initial_state:
                    logger.info(
                        f"Initial state keys: {list(initial_state.keys())}"
                    )

                logger.info(f"Creating session with state keys: {list(initial_state.keys())}")
                session_result = await self.session_service.create_session(
                    app_name="ken_e_chatbot", user_id=user_id, state=initial_state
                )
                session_id = (
                    session_result.id
                    if hasattr(session_result, "id")
                    else str(session_result)
                )
                logger.info(f"Successfully created ADK session: {session_id} for user: {user_id}")
            except Exception as async_error:
                logger.error(
                    f"Failed to create ADK session for user {user_id}: {async_error}"
                )
                logger.error(f"Error type: {type(async_error).__name__}")
                logger.error(
                    f"Session service status: {self._session_service is not None}"
                )
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
                session_id = f"manual_{uuid4()}"
                logger.warning(f"Created fallback manual session ID: {session_id}")

            # Store conversation metadata
            conversation_info = {
                "session_id": session_id,
                "user_id": user_id,
                "conversation_name": conversation_name,
                "created_at": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc),
                "message_count": 0,
            }

            self._user_sessions[f"{user_id}:{session_id}"] = conversation_info
            logger.info(
                f"Created conversation with session {session_id} for user {user_id}"
            )

            return session_id

        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            # Fallback to generating a UUID
            fallback_session_id = f"fallback_{uuid4()}"
            conversation_info = {
                "session_id": fallback_session_id,
                "user_id": user_id,
                "conversation_name": conversation_name,
                "created_at": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc),
                "message_count": 0,
            }
            self._user_sessions[f"{user_id}:{fallback_session_id}"] = conversation_info
            return fallback_session_id

    async def get_or_create_session(
        self,
        user_id: str,
        user_context: UserContext | None = None,
        session_id: str | None = None,
        conversation_name: str | None = None,
        account_id: str | None = None,
    ) -> str:
        """Get an existing session or create a new one.

        Args:
            user_id: User identifier
            user_context: User context for initializing new sessions
            session_id: Existing session ID (optional)
            conversation_name: Name for new conversation (optional)

        Returns:
            Session ID (existing or newly created)
        """
        if session_id:
            session_key = f"{user_id}:{session_id}"

            # First check in-memory cache
            if session_key in self._user_sessions:
                logger.info(
                    f"Using existing session {session_id} from cache for user {user_id}"
                )
                return session_id
            else:
                # Cache miss - check if this is a valid ADK session format before querying ADK
                # Skip ADK validation for frontend-generated or fallback session IDs
                is_adk_session = not (
                    session_id.startswith("chat_")
                    or session_id.startswith("fallback_")
                    or session_id.startswith("manual_")
                )

                if is_adk_session:
                    logger.info(
                        f"Session {session_id} not in cache, checking ADK for user {user_id}"
                    )
                    try:
                        session_data = await self.session_service.get_session(
                            app_name="ken_e_chatbot",
                            user_id=user_id,
                            session_id=session_id,
                        )
                        if session_data:
                            logger.info(
                                f"Found existing ADK session {session_id} for user {user_id}"
                            )
                            # Restore session info to cache
                            conversation_info = {
                                "session_id": session_id,
                                "user_id": user_id,
                                "conversation_name": conversation_name,
                                "created_at": getattr(
                                    session_data,
                                    "create_time",
                                    datetime.now(timezone.utc),
                                ),
                                "last_updated": getattr(
                                    session_data,
                                    "update_time",
                                    datetime.now(timezone.utc),
                                ),
                                "message_count": len(
                                    getattr(session_data, "events", [])
                                ),
                            }
                            self._user_sessions[session_key] = conversation_info
                            return session_id
                        else:
                            logger.warning(
                                f"ADK session {session_id} not found for user {user_id}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error checking ADK session {session_id} for user {user_id}: {e}"
                        )
                else:
                    logger.info(
                        f"Session {session_id} has non-ADK format, skipping ADK validation"
                    )

                logger.info(
                    f"Creating new conversation for user {user_id} (original session {session_id} not found or invalid)"
                )
        # Create new conversation with user_context and account_id
        return await self.create_conversation(user_id, user_context, conversation_name, account_id)

    def update_conversation_metadata(
        self, user_id: str, session_id: str, conversation_name: str | None = None
    ) -> bool:
        """Update conversation metadata."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            if conversation_name is not None:
                self._user_sessions[session_key]["conversation_name"] = (
                    conversation_name
                )
            self._user_sessions[session_key]["last_updated"] = datetime.now(
                timezone.utc
            )
            return True
        return False

    async def get_user_conversations(self, user_id: str) -> list[ConversationInfo]:
        """Get all conversations for a user from ADK session service."""
        conversations = []

        try:
            logger.info(f"Getting conversations for user: {user_id}")
            logger.info(
                f"Cache keys: {list(self._user_sessions.keys())[:5]}..."
            )  # Show first 5 cache keys

            # Get sessions from ADK session service
            sessions = await self.session_service.list_sessions(
                app_name="ken_e_chatbot", user_id=user_id
            )

            # Handle ListSessionsResponse - it might have a sessions attribute
            session_list = (
                sessions.sessions if hasattr(sessions, "sessions") else sessions
            )

            for session in session_list:
                # Try to get metadata from our cache first, fallback to session data
                session_id = getattr(session, "id", None) or getattr(
                    session, "session_id", str(session)
                )
                session_key = f"{user_id}:{session_id}"
                cached_info = self._user_sessions.get(session_key, {})

                conversations.append(
                    ConversationInfo(
                        session_id=session_id,
                        conversation_name=cached_info.get("conversation_name")
                        or f"Chat {session_id[-8:]}",
                        created_at=getattr(session, "create_time", None)
                        or cached_info.get("created_at", datetime.now(timezone.utc)),
                        last_updated=getattr(session, "update_time", None)
                        or cached_info.get("last_updated", datetime.now(timezone.utc)),
                        message_count=cached_info.get("message_count", 0),
                    )
                )

        except Exception as e:
            logger.error(f"Failed to get sessions from ADK service: {e}")
            # Fallback to cached sessions if ADK service fails
            for session_key, info in self._user_sessions.items():
                if session_key.startswith(f"{user_id}:"):
                    conversations.append(
                        ConversationInfo(
                            session_id=info["session_id"],
                            conversation_name=info.get("conversation_name"),
                            created_at=info["created_at"],
                            last_updated=info["last_updated"],
                            message_count=info["message_count"],
                        )
                    )

        # Sort by last updated (most recent first)
        conversations.sort(key=lambda x: x.last_updated, reverse=True)
        return conversations

    async def delete_conversation(self, user_id: str, session_id: str) -> bool:
        """Delete a conversation and its session."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            try:
                # Try to delete the ADK session
                await self.session_service.delete_session(
                    app_name="ken_e_chatbot", user_id=user_id, session_id=session_id
                )
                logger.info(f"Deleted ADK session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to delete ADK session {session_id}: {e}")

            # Remove from our cache
            del self._user_sessions[session_key]
            logger.info(f"Deleted conversation {session_id} for user {user_id}")
            return True
        return False

    def increment_message_count(self, user_id: str, session_id: str) -> None:
        """Increment the message count for a conversation."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            self._user_sessions[session_key]["message_count"] += 1
            self._user_sessions[session_key]["last_updated"] = datetime.now(
                timezone.utc
            )

    def generate_conversation_name(self, user_message: str) -> str:
        """Generate a meaningful conversation name from the user's message (1-2 words max)."""
        try:
            # Simple keyword extraction - look for key marketing/business terms
            message_lower = user_message.lower()

            # Marketing/business keywords to prioritize
            marketing_keywords = {
                "seo": "SEO",
                "social media": "Social Media",
                "facebook": "Facebook",
                "instagram": "Instagram",
                "linkedin": "LinkedIn",
                "twitter": "Twitter",
                "google ads": "Google Ads",
                "ppc": "PPC",
                "email marketing": "Email",
                "content marketing": "Content",
                "analytics": "Analytics",
                "conversion": "Conversion",
                "roi": "ROI",
                "revenue": "Revenue",
                "sales": "Sales",
                "lead generation": "Leads",
                "campaign": "Campaign",
                "brand": "Brand",
                "strategy": "Strategy",
                "competitor": "Competitor",
                "market research": "Research",
                "customer": "Customer",
                "retention": "Retention",
                "acquisition": "Acquisition",
                "funnel": "Funnel",
                "dashboard": "Dashboard",
                "metrics": "Metrics",
                "kpi": "KPI",
                "performance": "Performance",
                "budget": "Budget",
                "optimize": "Optimization",
                "report": "Report",
            }

            # Look for marketing keywords first
            for keyword, name in marketing_keywords.items():
                if keyword in message_lower:
                    return name

            # Fallback: extract first meaningful words (skip common words)
            import re

            words = re.findall(r"\b[a-zA-Z]{3,}\b", user_message)
            stop_words = {
                "the",
                "and",
                "for",
                "are",
                "but",
                "not",
                "you",
                "all",
                "can",
                "her",
                "was",
                "one",
                "our",
                "had",
                "what",
                "help",
                "with",
                "how",
                "need",
                "want",
                "about",
                "this",
                "that",
                "have",
                "will",
                "would",
                "could",
                "should",
            }

            meaningful_words = [
                word.title() for word in words[:5] if word.lower() not in stop_words
            ]

            if meaningful_words:
                # Take first 1-2 meaningful words
                if len(meaningful_words) >= 2:
                    return f"{meaningful_words[0]} {meaningful_words[1]}"
                else:
                    return meaningful_words[0]

            # Final fallback
            return "Marketing Chat"

        except Exception as e:
            logger.warning(f"Failed to generate conversation name: {e}")
            return "Marketing Chat"

    async def get_conversation_history(
        self, user_id: str, session_id: str
    ) -> dict[str, Any] | None:
        """Get conversation history from ADK session service and format it for frontend consumption."""
        try:
            logger.info(
                f"Getting conversation history for user: {user_id}, session: {session_id}"
            )

            session_data = await self.session_service.get_session(
                app_name="ken_e_chatbot", user_id=user_id, session_id=session_id
            )

            if session_data and hasattr(session_data, "events"):
                # Convert ADK session events to a frontend-friendly format
                formatted_history = {"session_id": session_id, "events": []}

                # Process each event in the session
                for event in session_data.events:
                    formatted_event = {
                        "content": {},
                        "role": "assistant",
                        "timestamp": getattr(event, "timestamp", None),
                    }

                    # Extract content and role from the event
                    if hasattr(event, "content") and event.content:
                        content_obj = event.content

                        # Extract role
                        if hasattr(content_obj, "role"):
                            formatted_event["role"] = content_obj.role
                        elif hasattr(event, "author"):
                            formatted_event["role"] = event.author

                        # Extract parts (text content)
                        if hasattr(content_obj, "parts") and content_obj.parts:
                            formatted_event["content"]["parts"] = []
                            for part in content_obj.parts:
                                if hasattr(part, "text"):
                                    formatted_event["content"]["parts"].append(
                                        {"text": part.text}
                                    )

                    formatted_history["events"].append(formatted_event)

                logger.info(
                    f"Formatted {len(formatted_history['events'])} events for session {session_id}"
                )
                return formatted_history
            else:
                logger.warning(f"No events found in session {session_id}")
                return {"session_id": session_id, "events": []}

        except Exception as e:
            logger.error(
                f"Failed to get conversation history for session {session_id}: {e}"
            )
            return None

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        user_context: UserContext,
        session_id: str | None = None,
        conversation_name: str | None = None,
        account_id: str | None = None,
    ) -> tuple[str, str]:
        """Get a chat completion from the Agent Engine using agent_engines API with session management."""
        if not self.agent_engine:
            return (
                "I'm sorry, but I'm unable to process your request at the moment. Please try again later.",
                "",
            )

        try:
            # Get the latest message
            latest_message = messages[-1] if messages else None
            if not latest_message:
                return "I didn't receive any message to process.", ""

            user_input = latest_message.content
            user_id = user_context.user_id

            # Format conversation history if there are previous messages
            if len(messages) > 1:
                # Build conversation context from all messages
                conversation_context = []
                for msg in messages[:-1]:  # All messages except the latest
                    role_label = "User" if msg.role == "user" else "Assistant"
                    conversation_context.append(f"{role_label}: {msg.content}")

                # Add conversation history as context to the current message
                context_str = "\n".join(conversation_context)
                formatted_input = f"Previous conversation:\n{context_str}\n\nCurrent message: {user_input}"
                logger.info(
                    f"[CHAT] Including {len(messages) - 1} previous messages in context"
                )
            else:
                formatted_input = user_input

            logger.info(
                f"[CHAT] Processing message for user {user_id}: {user_input[:100]}..."
            )
            logger.info(
                f"[CHAT] User context: {user_context.accessible_accounts if user_context else 'No context'}"
            )

            # Get or create session for this user (credentials now passed via session state)
            actual_session_id = await self.get_or_create_session(
                user_id, user_context, session_id, conversation_name, account_id
            )

            # Determine account_id for context injection
            context_account_id = account_id
            if not context_account_id and user_context and user_context.accessible_accounts:
                context_account_id = user_context.accessible_accounts[0]

            # Inject organization and campaign context
            formatted_input = await inject_context_into_message(
                formatted_input=formatted_input,
                user_input=user_input,
                account_id=context_account_id,
                session_id=actual_session_id,
                streaming=False,
            )

            # Check if this is the first message and we need to generate a conversation name
            session_key = f"{user_id}:{actual_session_id}"
            if (
                session_key in self._user_sessions
                and self._user_sessions[session_key]["message_count"] == 0
                and not self._user_sessions[session_key].get("conversation_name")
            ):
                # Generate a meaningful name from the user's first message
                generated_name = self.generate_conversation_name(user_input)
                self._user_sessions[session_key]["conversation_name"] = generated_name
                logger.info(
                    f"Generated conversation name: '{generated_name}' for session {actual_session_id}"
                )

            # Increment message count
            self.increment_message_count(user_id, actual_session_id)

            logger.info(
                f"Sending query to Agent Engine for user {user_id}, session {actual_session_id}"
            )
            logger.info(
                f"Query length: {len(formatted_input)} chars, preview: {formatted_input[:200]}..."
            )
            logger.info(f"Session ID being passed to Agent Engine: {actual_session_id}")

            # Use the agent_engines API with proper Queryable interface
            try:
                # Log available methods for debugging
                available_methods = [
                    method
                    for method in dir(self.agent_engine)
                    if not method.startswith("_")
                ]
                logger.info(f"Available methods on agent engine: {available_methods}")

                # Try the agent_engines query patterns
                response = None

                # The Agent Engine has stream_query method - let's collect the stream into a single response
                if hasattr(self.agent_engine, "stream_query"):
                    logger.info("Using stream_query method and collecting response")
                    response_parts = []
                    try:
                        # Use the correct parameters expected by the deployed agent
                        # Run the blocking stream_query in a thread pool with timeout to avoid blocking the event loop
                        loop = asyncio.get_event_loop()
                        try:
                            stream_iterator = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    lambda: list(
                                        self.agent_engine.stream_query(
                                            message=formatted_input,
                                            user_id=user_id,
                                            session_id=actual_session_id,
                                        )
                                    ),
                                ),
                                timeout=1800.0,  # 30 minute timeout for complex requests like strategy generation
                            )
                        except asyncio.TimeoutError:
                            logger.error(
                                f"Agent Engine timed out after 1800 seconds for user {user_id}"
                            )
                            return (
                                "I'm sorry, your request is taking longer than expected. Please try a simpler question or try again later.",
                                actual_session_id,
                            )
                        for chunk in stream_iterator:
                            logger.info(
                                f"Received chunk type: {type(chunk)}, content preview: {str(chunk)[:100]}..."
                            )

                            if isinstance(chunk, dict):
                                # Handle actual dictionary response
                                logger.info(
                                    f"Processing dict chunk with keys: {list(chunk.keys())}"
                                )

                                # Handle nested structure: {'content': {'parts': [{'text': '...'}]}}
                                if "content" in chunk and isinstance(
                                    chunk["content"], dict
                                ):
                                    content = chunk["content"]
                                    if "parts" in content and isinstance(
                                        content["parts"], list
                                    ):
                                        for part in content["parts"]:
                                            if (
                                                isinstance(part, dict)
                                                and "text" in part
                                            ):
                                                logger.info(
                                                    f"Extracted text from nested structure: {part['text'][:50]}..."
                                                )
                                                response_parts.append(part["text"])
                                            else:
                                                response_parts.append(str(part))
                                    else:
                                        response_parts.append(str(content))
                                # Handle direct structure: {'parts': [{'text': '...'}]}
                                elif "parts" in chunk and isinstance(
                                    chunk["parts"], list
                                ):
                                    for part in chunk["parts"]:
                                        if isinstance(part, dict) and "text" in part:
                                            logger.info(
                                                f"Extracted text from direct structure: {part['text'][:50]}..."
                                            )
                                            response_parts.append(part["text"])
                                        else:
                                            response_parts.append(str(part))
                                # Handle string content
                                elif "content" in chunk:
                                    response_parts.append(str(chunk["content"]))
                                else:
                                    # Don't append function_call or function_response data
                                    if not (
                                        "function_call" in chunk
                                        or "function_response" in chunk
                                    ):
                                        response_parts.append(str(chunk))
                                    else:
                                        logger.info(
                                            "Skipping function debug data in non-streaming response"
                                        )
                            elif isinstance(chunk, str):
                                # Handle string representation of dictionary
                                logger.info(f"Processing string chunk: {chunk[:50]}...")
                                if chunk.startswith("{'parts'") and "'text':" in chunk:
                                    logger.info(
                                        "Attempting to parse chunk as dictionary"
                                    )
                                    try:
                                        import ast

                                        parsed_chunk = ast.literal_eval(chunk)
                                        logger.info(
                                            f"Successfully parsed chunk: {type(parsed_chunk)}"
                                        )
                                        if (
                                            isinstance(parsed_chunk, dict)
                                            and "parts" in parsed_chunk
                                        ):
                                            for part in parsed_chunk["parts"]:
                                                if (
                                                    isinstance(part, dict)
                                                    and "text" in part
                                                ):
                                                    logger.info(
                                                        f"Extracted text: {part['text'][:50]}..."
                                                    )
                                                    response_parts.append(part["text"])
                                        else:
                                            response_parts.append(chunk)
                                    except (ValueError, SyntaxError) as e:
                                        logger.warning(
                                            f"Failed to parse chunk as dict: {e}"
                                        )
                                        response_parts.append(chunk)
                                else:
                                    # Check if the chunk contains function_call or function_response
                                    if (
                                        "{'function_call'" in chunk
                                        or "{'function_response'" in chunk
                                    ):
                                        # Try to extract just the text after the function data
                                        logger.info(
                                            "Found function data in string chunk, attempting to extract text"
                                        )

                                        # Look for text after the last }}
                                        if "}}" in chunk:
                                            parts = chunk.rsplit("}}", 1)
                                            if len(parts) == 2 and parts[1].strip():
                                                remaining = parts[1].strip()
                                                if not remaining.startswith("{"):
                                                    logger.info(
                                                        f"Extracted text after function data: {remaining[:50]}..."
                                                    )
                                                    response_parts.append(remaining)
                                                else:
                                                    logger.info(
                                                        "Remaining part is another JSON object, skipping"
                                                    )
                                            else:
                                                logger.info(
                                                    "No text found after function data, skipping entire chunk"
                                                )
                                        else:
                                            logger.info(
                                                "No }} found in chunk with function data, skipping"
                                            )
                                    else:
                                        logger.info(
                                            "Chunk doesn't match dictionary pattern, adding as-is"
                                        )
                                        response_parts.append(chunk)
                            elif hasattr(chunk, "content"):
                                response_parts.append(str(chunk.content))
                            else:
                                response_parts.append(str(chunk))

                        full_response = "".join(response_parts).strip()

                        # Clean up function_call/function_response data from the final response
                        if full_response and (
                            "{'function_call'" in full_response
                            or "{'function_response'" in full_response
                        ):
                            logger.info(
                                f"Cleaning function data from response (length: {len(full_response)})"
                            )
                            # Try to extract only the text after function blocks
                            if "}}" in full_response:
                                # Split by the last occurrence of }} and take what comes after
                                parts = full_response.rsplit("}}", 1)
                                if len(parts) == 2 and parts[1].strip():
                                    cleaned = parts[1].strip()
                                    if not cleaned.startswith("{"):
                                        logger.info(
                                            f"Extracted clean text (length: {len(cleaned)})"
                                        )
                                        full_response = cleaned

                        if full_response:
                            return full_response, actual_session_id
                        else:
                            return (
                                "Received empty response from Agent Engine",
                                actual_session_id,
                            )
                    except Exception as stream_error:
                        logger.error(f"stream_query failed: {stream_error}")
                        return (
                            f"Agent Engine stream_query error: {stream_error!s}",
                            actual_session_id,
                        )

                else:
                    return (
                        f"stream_query method not found. Available methods: {', '.join(available_methods[:10])}",
                        actual_session_id,
                    )

                logger.info(f"Response received: {type(response)}")

                # Process the response
                if isinstance(response, str):
                    return response, actual_session_id
                elif hasattr(response, "content"):
                    return str(response.content), actual_session_id
                elif hasattr(response, "text"):
                    return str(response.text), actual_session_id
                elif isinstance(response, dict):
                    # Handle the agent's response format: {'parts': [{'text': '...'}], 'role': 'model'}
                    if "parts" in response and isinstance(response["parts"], list):
                        text_parts = []
                        for part in response["parts"]:
                            if isinstance(part, dict) and "text" in part:
                                text_parts.append(part["text"])
                            else:
                                text_parts.append(str(part))
                        return "".join(text_parts).strip(), actual_session_id
                    elif "content" in response:
                        return str(response["content"]), actual_session_id
                    elif "text" in response:
                        return str(response["text"]), actual_session_id
                    elif "message" in response:
                        return str(response["message"]), actual_session_id
                    else:
                        return str(response), actual_session_id
                else:
                    return str(response), actual_session_id

            except Exception as call_error:
                logger.error(f"Error calling Agent Engine: {call_error}")
                return (
                    f"Error processing your request: {call_error!s}",
                    actual_session_id or "",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat completion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e!s}",
            )

    async def stream_chat_completion(
        self,
        messages: list[ChatMessage],
        user_context: UserContext,
        session_id: str | None = None,
        conversation_name: str | None = None,
        account_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion from the Agent Engine using agent_engines API."""
        if not self.agent_engine:
            yield "I'm sorry, but I'm unable to process your request at the moment. Please try again later."
            return

        try:
            # Get the latest message
            latest_message = messages[-1] if messages else None
            if not latest_message:
                yield "I didn't receive any message to process."
                return

            user_input = latest_message.content
            user_id = user_context.user_id

            # Format conversation history if there are previous messages
            if len(messages) > 1:
                # Build conversation context from all messages
                conversation_context = []
                for msg in messages[:-1]:  # All messages except the latest
                    role_label = "User" if msg.role == "user" else "Assistant"
                    conversation_context.append(f"{role_label}: {msg.content}")

                # Add conversation history as context to the current message
                context_str = "\n".join(conversation_context)
                formatted_input = f"Previous conversation:\n{context_str}\n\nCurrent message: {user_input}"
                logger.info(
                    f"[CHAT STREAM] Including {len(messages) - 1} previous messages in context"
                )
            else:
                formatted_input = user_input

            logger.info(
                f"[CHAT] Processing message for user {user_id}: {user_input[:100]}..."
            )
            logger.info(
                f"[CHAT] User context: {user_context.accessible_accounts if user_context else 'No context'}"
            )

            # Get or create session for this user (credentials now passed via session state)
            actual_session_id = await self.get_or_create_session(
                user_id, user_context, session_id, conversation_name, account_id
            )

            # Determine account_id for context injection
            context_account_id = account_id
            if not context_account_id and user_context and user_context.accessible_accounts:
                context_account_id = user_context.accessible_accounts[0]

            # Inject organization and campaign context
            formatted_input = await inject_context_into_message(
                formatted_input=formatted_input,
                user_input=user_input,
                account_id=context_account_id,
                session_id=actual_session_id,
                streaming=True,
            )

            # Check if this is the first message and we need to generate a conversation name
            session_key = f"{user_id}:{actual_session_id}"
            if (
                session_key in self._user_sessions
                and self._user_sessions[session_key]["message_count"] == 0
                and not self._user_sessions[session_key].get("conversation_name")
            ):
                # Generate a meaningful name from the user's first message
                generated_name = self.generate_conversation_name(user_input)
                self._user_sessions[session_key]["conversation_name"] = generated_name
                logger.info(
                    f"Generated conversation name: '{generated_name}' for session {actual_session_id}"
                )

            # Increment message count
            self.increment_message_count(user_id, actual_session_id)

            logger.info(
                f"Streaming query to Agent Engine for user {user_id}, session {actual_session_id}"
            )
            logger.info(
                f"Query length: {len(formatted_input)} chars, preview: {formatted_input[:200]}..."
            )
            logger.info(
                f"Session ID being passed to Agent Engine for streaming: {actual_session_id}"
            )

            # Try streaming with agent_engines API
            try:
                # Log available methods for debugging
                available_methods = [
                    method
                    for method in dir(self.agent_engine)
                    if not method.startswith("_")
                ]
                logger.info(f"Available methods on agent engine: {available_methods}")

                # Use stream_query with correct parameters for deployed agent
                if hasattr(self.agent_engine, "stream_query"):
                    logger.info("Using stream_query method for streaming")

                    # Create an async generator that runs the blocking stream_query in a thread
                    import queue
                    import threading

                    chunk_queue = queue.Queue()
                    exception_holder = {"exception": None}

                    def stream_worker():
                        try:
                            for chunk in self.agent_engine.stream_query(
                                message=formatted_input,
                                user_id=user_id,
                                session_id=actual_session_id,
                            ):
                                chunk_queue.put(chunk)
                        except Exception as e:
                            exception_holder["exception"] = e
                        finally:
                            chunk_queue.put(None)  # Signal completion

                    # Start the streaming in a background thread
                    stream_thread = threading.Thread(target=stream_worker)
                    stream_thread.start()

                    # Yield chunks as they arrive
                    while True:
                        # Check for chunks with a timeout to avoid blocking forever
                        try:
                            chunk = chunk_queue.get(timeout=0.1)
                        except queue.Empty:
                            # Check if thread is still alive
                            if not stream_thread.is_alive() and chunk_queue.empty():
                                break
                            await asyncio.sleep(0.01)  # Small yield to event loop
                            continue

                        if chunk is None:  # End signal
                            break

                        if exception_holder["exception"]:
                            raise exception_holder["exception"]
                        if isinstance(chunk, dict):
                            # Handle actual dictionary response
                            # Handle nested structure: {'content': {'parts': [{'text': '...'}]}}
                            if "content" in chunk and isinstance(
                                chunk["content"], dict
                            ):
                                content = chunk["content"]
                                if "parts" in content and isinstance(
                                    content["parts"], list
                                ):
                                    for part in content["parts"]:
                                        if isinstance(part, dict) and "text" in part:
                                            yield part["text"]
                                        else:
                                            yield str(part)
                                else:
                                    yield str(content)
                            # Handle direct structure: {'parts': [{'text': '...'}]}
                            elif "parts" in chunk and isinstance(chunk["parts"], list):
                                for part in chunk["parts"]:
                                    if isinstance(part, dict) and "text" in part:
                                        yield part["text"]
                                    else:
                                        yield str(part)
                            elif "content" in chunk:
                                yield str(chunk["content"])
                            else:
                                # Don't yield raw function_call or function_response data
                                # These are debug/internal data, not user-facing content
                                if not (
                                    "function_call" in chunk
                                    or "function_response" in chunk
                                ):
                                    yield str(chunk)
                        elif isinstance(chunk, str):
                            # Log the raw chunk for debugging
                            logger.debug(
                                f"Raw chunk received (first 200 chars): {chunk[:200]}..."
                            )

                            # Parse and clean string chunks that might contain function data
                            # Check if this is a string representation of function_call/function_response
                            if chunk.startswith("{'function_call'") or chunk.startswith(
                                "{'function_response'"
                            ):
                                # This is debug data, skip it
                                logger.debug(
                                    f"Skipping function debug data in chunk: {chunk[:100]}..."
                                )
                                continue

                            # Handle string representation of dictionary with text content
                            elif chunk.startswith("{'parts'") and "'text':" in chunk:
                                try:
                                    import ast

                                    parsed_chunk = ast.literal_eval(chunk)
                                    if (
                                        isinstance(parsed_chunk, dict)
                                        and "parts" in parsed_chunk
                                    ):
                                        for part in parsed_chunk["parts"]:
                                            if (
                                                isinstance(part, dict)
                                                and "text" in part
                                            ):
                                                yield part["text"]
                                    else:
                                        yield chunk
                                except (ValueError, SyntaxError):
                                    yield chunk

                            # Check if the chunk contains both function data and text
                            elif (
                                "{'function_call'" in chunk
                                or "{'function_response'" in chunk
                            ):
                                # Try to extract just the text after the function data
                                # The pattern is: {'function_call': ...}{'function_response': ...}actual text
                                import re

                                # More robust pattern to match multiple consecutive function blocks
                                # This matches one or more consecutive {function_call/response} blocks
                                pattern = r"^(\{['\"]function_(?:call|response)['\"].*?\}\}(?:\{['\"]function_(?:call|response)['\"].*?\}\})*)(.*)"
                                match = re.match(pattern, chunk, re.DOTALL)

                                if match:
                                    function_blocks = match.group(1)
                                    text_part = match.group(2).strip()

                                    logger.debug(
                                        f"Found function blocks: {function_blocks[:100]}..."
                                    )
                                    logger.debug(
                                        f"Extracted text part: {text_part[:100]}..."
                                    )

                                    # Only yield the text part if it exists and isn't empty
                                    if text_part:
                                        yield text_part
                                else:
                                    # Try simpler approach: split by the last }} and take what comes after
                                    # This handles cases where the regex might fail
                                    if "}}" in chunk:
                                        parts = chunk.rsplit("}}", 1)
                                        if len(parts) == 2 and parts[1].strip():
                                            # Check if the remaining part isn't another JSON object
                                            remaining = parts[1].strip()
                                            if not remaining.startswith("{"):
                                                yield remaining
                                    elif not chunk.strip().startswith("{"):
                                        # If it doesn't start with {, it's probably just text
                                        yield chunk
                            else:
                                yield chunk
                        elif hasattr(chunk, "content"):
                            yield str(chunk.content)
                        else:
                            yield str(chunk)
                    return

                # Fallback: use regular query and yield the result
                response = None

                # Pattern 3: query method
                if hasattr(self.agent_engine, "query"):
                    logger.info("Trying query method for streaming fallback")
                    try:
                        # Try with session parameters first
                        response = self.agent_engine.query(
                            message=formatted_input,
                            user_id=user_id,
                            session_id=actual_session_id,
                        )
                    except TypeError:
                        # Fallback to simple query if parameters not supported
                        response = self.agent_engine.query(formatted_input)

                # Pattern 4: Direct callable
                elif callable(self.agent_engine):
                    logger.info("Trying direct call pattern for streaming fallback")
                    try:
                        # Try with session parameters first
                        response = self.agent_engine(
                            message=formatted_input,
                            user_id=user_id,
                            session_id=actual_session_id,
                        )
                    except TypeError:
                        # Fallback to simple call if parameters not supported
                        response = self.agent_engine(formatted_input)

                else:
                    yield f"Unable to find a valid query method on the Agent Engine. Available methods: {', '.join(available_methods[:10])}"
                    return

                logger.info(f"Streaming response received: {type(response)}")

                # Process and yield the response
                if isinstance(response, str):
                    yield response
                elif hasattr(response, "content"):
                    yield str(response.content)
                elif hasattr(response, "text"):
                    yield str(response.text)
                elif isinstance(response, dict):
                    if "content" in response:
                        yield str(response["content"])
                    elif "text" in response:
                        yield str(response["text"])
                    elif "message" in response:
                        yield str(response["message"])
                    else:
                        yield str(response)
                else:
                    yield str(response)

            except Exception as call_error:
                logger.error(f"Error calling Agent Engine for streaming: {call_error}")
                yield f"Error processing your request: {call_error!s}"

        except Exception as e:
            logger.error(f"Error in streaming chat completion: {e}")
            yield f"Error: Failed to process chat request - {e!s}"


# Global client instance
agent_client = AgentEngineClient()


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest, user_context: UserContext = Depends(get_current_user_context)
):
    """
    Get a chat completion from the Vertex AI Agent Engine.

    This endpoint processes a conversation with the KEN-E marketing assistant
    and returns a response from the deployed Agent Engine.
    """
    try:
        # SECURITY: Validate account access if account_id provided
        if request.account_id and not user_context.has_account_access(request.account_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {request.account_id}",
            )
        if request.stream:
            # Return streaming response
            async def generate_response():
                async for chunk in agent_client.stream_chat_completion(
                    messages=request.messages,
                    user_context=user_context,
                    session_id=request.session_id,
                    conversation_name=request.conversation_name,
                    account_id=request.account_id,
                ):
                    # Format as Server-Sent Events
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_response(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Return single response
            response_content, actual_session_id = await agent_client.chat_completion(
                messages=request.messages,
                user_context=user_context,
                session_id=request.session_id,
                conversation_name=request.conversation_name,
                account_id=request.account_id,
            )

            return ChatResponse(
                content=response_content,
                session_id=actual_session_id,
                conversation_name=request.conversation_name,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.get("/health")
async def chat_health():
    """
    Health check endpoint for the chat service.
    """
    agent_status = "connected" if agent_client.agent_engine_id else "not_configured"

    return {
        "status": "healthy",
        "agent_engine_status": agent_status,
        "project_id": agent_client.project_id,
        "location": agent_client.location,
        "code_version": "session_state_v2_20260120",  # Debug: verify code loaded
    }


@router.post("/conversations", response_model=ConversationInfo)
async def create_conversation(
    request: CreateConversationRequest,
    user_context: UserContext = Depends(get_current_user_context),
):
    """
    Create a new conversation/session with initial state.
    """
    try:
        # SECURITY: Validate account access if account_id provided
        if request.account_id and not user_context.has_account_access(request.account_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {request.account_id}",
            )

        logger.info(f"Creating conversation for user: {user_context.user_id}, account: {request.account_id}")

        session_id = await agent_client.create_conversation(
            user_id=user_context.user_id,
            user_context=user_context,
            conversation_name=request.conversation_name,
            account_id=request.account_id,
        )

        logger.info(f"Created session: {session_id}")

        # Get the conversation info to return
        conversations = await agent_client.get_user_conversations(user_context.user_id)
        for conv in conversations:
            if conv.session_id == session_id:
                return conv

        # Fallback if not found in cache
        return ConversationInfo(
            session_id=session_id,
            conversation_name=request.conversation_name,
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
            message_count=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(user_context: UserContext = Depends(get_current_user_context)):
    """
    List all conversations for the current user.
    """
    try:
        conversations = await agent_client.get_user_conversations(user_context.user_id)

        return ConversationListResponse(
            conversations=conversations, total_count=len(conversations)
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations",
        )


@router.put("/conversations/{session_id}", response_model=ConversationInfo)
async def update_conversation(
    session_id: str,
    request: UpdateConversationRequest,
    user_context: UserContext = Depends(get_current_user_context),
):
    """
    Update conversation metadata (e.g., rename conversation).
    """
    try:
        success = agent_client.update_conversation_metadata(
            user_id=user_context.user_id,
            session_id=session_id,
            conversation_name=request.conversation_name,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        # Get updated conversation info
        conversations = await agent_client.get_user_conversations(user_context.user_id)
        for conv in conversations:
            if conv.session_id == session_id:
                return conv

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found after update",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation",
        )


@router.get("/conversations/{session_id}/history")
async def get_conversation_history(
    session_id: str, user_context: UserContext = Depends(get_current_user_context)
):
    """
    Get the message history for a specific conversation.
    """
    try:
        history = await agent_client.get_conversation_history(
            user_id=user_context.user_id, session_id=session_id
        )

        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation history not found",
            )

        return history

    except Exception as e:
        logger.error(f"Error getting conversation history {session_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation history",
        )


@router.delete("/conversations/{session_id}")
async def delete_conversation(
    session_id: str, user_context: UserContext = Depends(get_current_user_context)
):
    """
    Delete a conversation and its associated session.
    """
    try:
        success = await agent_client.delete_conversation(
            user_id=user_context.user_id, session_id=session_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation",
        )

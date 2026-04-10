"""
Chat API endpoints for Vertex AI Agent Engine integration.
"""

import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import vertexai
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.adk.sessions import VertexAiSessionService
from pydantic import BaseModel, Field

from shared.secrets import get_env_or_secret
from shared.structured_logging import get_structured_logger, log_context

try:
    import weave

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..auth.user_context import get_current_user_context
from ..cache import (
    ga_credentials_key,
    org_context_key,
    session_metadata_key,
    user_session_ids_key,
)
from ..database import get_neo4j_service
from ..firestore import get_firestore_service
from ..models.kene_models import RecoverableSessionInfo
from ..redis_client import get_redis_service
from ..services.ga_credential_helper import GACredentialHelper

logger = get_structured_logger(__name__)

# Cache TTL constants (seconds)
ORG_CONTEXT_TTL_SECONDS = 900  # 15 minutes
GA_CREDENTIALS_TTL_SECONDS = 600  # 10 minutes
SESSION_METADATA_TTL_SECONDS = 86400  # 24 hours

# CRITICAL: Use this constant for all ADK session operations
# Bug fix: Previously line 965 used "ken-e-chatbot" while others used "ken_e_chatbot"
APP_NAME = "ken_e_chatbot"

# Background reauth check cache: populated by async task, consumed on next request
_reauth_cache: dict[str, dict[str, Any]] = {}

# Strong references for fire-and-forget tasks to prevent garbage collection (RUF006)
_background_tasks: set[asyncio.Task[Any]] = set()

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _is_function_event_part(part: dict) -> bool:
    """Check if a dict part is a function_call/function_response event."""
    return "function_call" in part or "function_response" in part


def _is_function_event_json(chunk: str) -> bool:
    """Check if a JSON string represents a function event."""
    stripped = chunk.strip()
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
        return isinstance(parsed, dict) and _is_function_event_part(parsed)
    except (json.JSONDecodeError, ValueError):
        return False


def _contains_function_event_str(text: str) -> bool:
    """Check if text contains function event data (Python repr or JSON)."""
    return (
        "{'function_call'" in text
        or "{'function_response'" in text
        or '{"function_call"' in text
        or '{"function_response"' in text
    )


async def load_organization_context_from_neo4j(account_id: str) -> str | None:
    """Load organization context from Neo4j using API's Neo4j service.

    Loads Account info and Brand Voice/Tone, formats as markdown.
    Uses the canonical shared query (ORG_CONTEXT_QUERY) so API and agent
    loaders always fetch the same fields.

    Args:
        account_id: Account identifier

    Returns:
        Formatted markdown context string, or None if loading fails
    """
    from shared.context_utils import (
        ORG_CONTEXT_QUERY,
        extract_context_from_result,
        format_context_markdown,
    )

    try:
        neo4j_service = await get_neo4j_service()
        result = await neo4j_service.execute_query(
            ORG_CONTEXT_QUERY, {"account_id": account_id}
        )

        context_data = extract_context_from_result(result)
        if not context_data:
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

        context_str = format_context_markdown(context_data)

        logger.info(
            "Organization context loaded",
            extra=log_context(
                component="organization_context",
                action="load",
                account_id=account_id,
                success=True,
                extra={
                    "company_name": context_data.get("account", {}).get(
                        "company_name", "unknown"
                    ),
                    "has_brand_guidelines": bool(
                        context_data.get("brand")
                        and any(context_data["brand"].values())
                    ),
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
    metadata: dict[str, Any] | None = Field(None, description="Response metadata")


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
    preview: str | None = Field(None, description="Preview of last message")


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
            logger.info(
                f"Resolved Agent Engine ID: {self.agent_engine_id} (from {engine_id_full})"
            )

        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)

        self._agent_engine: Any = None
        self._session_service: VertexAiSessionService | None = None
        self._user_sessions: dict[str, dict] = {}
        self._sessions_loaded_for: set[str] = set()
        # Maps pending session IDs to background creation tasks.
        # POST /conversations returns a pending_* ID immediately while
        # create_session runs in the background (~3.8s).  When POST
        # /completions arrives, resolve_pending_session() awaits the
        # task and swaps in the real Vertex AI session ID.
        self._pending_sessions: dict[str, asyncio.Task[str]] = {}

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
                print(
                    f"[AGENT_ENGINE] Creating vertexai.Client with project={self.project_id}, location={self.location}"
                )
                print(
                    f"[AGENT_ENGINE] Calling client.agent_engines.get(name={resource_name})"
                )
                logger.info(
                    f"Calling agent_engines.get with name parameter: {resource_name}"
                )

                client = vertexai.Client(
                    project=self.project_id, location=self.location
                )
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
                ) from e
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
                ) from e
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
            t_total = time.time()
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

                # PERFORMANCE OPTIMIZATION: Parallelize Neo4j and Firestore operations
                # These are independent and can run concurrently, reducing latency by ~50%
                # PHASE 3: Add Redis caching with graceful fallback
                async def load_org_context() -> str | None:
                    """Load organization context from Neo4j with caching."""
                    try:
                        # Try cache first (Phase 3 optimization)
                        redis_service = get_redis_service()
                        if redis_service.is_available():
                            cache_key = org_context_key(selected_account_id)
                            cached_context = redis_service.get(cache_key)

                            if cached_context:
                                logger.info(
                                    f"Cache HIT: Organization context for {selected_account_id} ({len(cached_context)} chars)"
                                )
                                return cached_context

                        # Cache miss or Redis unavailable - load from Neo4j
                        logger.info(
                            f"Loading organization context for account: {selected_account_id}"
                        )
                        org_context = await load_organization_context_from_neo4j(
                            account_id=selected_account_id
                        )

                        if org_context:
                            logger.info(
                                f"Loaded organization context: {len(org_context)} chars"
                            )
                            # Cache for future requests (non-blocking)
                            if redis_service.is_available():
                                cache_key = org_context_key(selected_account_id)
                                redis_service.set(
                                    cache_key, org_context, ttl=ORG_CONTEXT_TTL_SECONDS
                                )
                        else:
                            logger.warning(
                                f"No organization context found for account: {selected_account_id}"
                            )

                        return org_context
                    except Exception as e:
                        logger.error(f"Failed to load organization context: {e}")
                        return None

                async def load_ga_credentials() -> dict | None:
                    """Load and format GA credentials from Firestore with caching."""
                    try:
                        # Try cache first (Phase 3 optimization)
                        redis_service = get_redis_service()
                        if redis_service.is_available():
                            cache_key = ga_credentials_key(selected_account_id)
                            cached_creds = redis_service.get_json(cache_key)

                            if cached_creds:
                                logger.info(
                                    f"Cache HIT: GA credentials for {selected_account_id}"
                                )
                                return cached_creds

                        # Cache miss or Redis unavailable - load from Firestore
                        firestore_service = get_firestore_service()
                        db = firestore_service.get_client()
                        ga_helper = GACredentialHelper(db)

                        logger.info(
                            f"Loading GA credentials for account: {selected_account_id}"
                        )
                        ga_creds = await ga_helper.get_and_format_credentials(
                            selected_account_id
                        )

                        if ga_creds:
                            # Get raw credentials for storage in state
                            raw_creds = await ga_helper.get_oauth_credentials(
                                selected_account_id
                            )
                            if raw_creds:
                                raw_creds = await ga_helper.refresh_if_expired(
                                    selected_account_id, raw_creds
                                )

                            property_ids_to_store = ga_creds.get(
                                "selected_property_ids", []
                            )
                            logger.info(
                                f"Loaded GA credentials with {len(property_ids_to_store)} properties for account: {selected_account_id}"
                            )

                            credentials_dict = {
                                "access_token": raw_creds.get("access_token")
                                if raw_creds
                                else None,
                                "refresh_token": raw_creds.get("refresh_token")
                                if raw_creds
                                else None,
                                "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
                                "client_secret": get_env_or_secret("GOOGLE_OAUTH_CLIENT_SECRET") or "",
                                "tenant_id": ga_creds["tenant_id"],
                                "selected_property_ids": property_ids_to_store,
                                "selected_properties": ga_creds.get(
                                    "selected_properties", []
                                ),
                                "expires_at": raw_creds.get("expires_at")
                                if raw_creds
                                else None,
                            }

                            # Cache for future requests (non-blocking)
                            if redis_service.is_available():
                                cache_key = ga_credentials_key(selected_account_id)
                                redis_service.set_json(
                                    cache_key,
                                    credentials_dict,
                                    ttl=GA_CREDENTIALS_TTL_SECONDS,
                                )

                            return credentials_dict
                        else:
                            logger.warning(
                                f"No GA credentials found for account: {selected_account_id}"
                            )
                            return None
                    except Exception as e:
                        logger.error(f"Failed to load GA credentials: {e}")
                        return None

                # Execute both operations in parallel
                t_parallel = time.time()
                org_context, ga_credentials = await asyncio.gather(
                    load_org_context(),
                    load_ga_credentials(),
                )
                logger.info(
                    "Parallel data loading completed",
                    extra=log_context(
                        component="chat",
                        action="load_session_data",
                        duration_ms=(time.time() - t_parallel) * 1000,
                        extra={
                            "org_context_loaded": org_context is not None,
                            "ga_credentials_loaded": ga_credentials is not None,
                        },
                    ),
                )

                # Store results in session state
                if org_context:
                    initial_state["organization_context"] = org_context

                if ga_credentials:
                    initial_state["ga_credentials"] = ga_credentials

            # Create ADK session
            try:
                logger.info(f"Attempting to create ADK session for user: {user_id}")
                logger.info(
                    f"Session service initialized: {self._session_service is not None}"
                )
                logger.info(f"Agent engine ID: {self.agent_engine_id}")
                if initial_state:
                    logger.info(f"Initial state keys: {list(initial_state.keys())}")

                t0 = time.time()
                session_result = await self.session_service.create_session(
                    app_name=APP_NAME, user_id=user_id, state=initial_state
                )
                session_id = (
                    session_result.id
                    if hasattr(session_result, "id")
                    else str(session_result)
                )
                logger.info(
                    "Vertex AI create_session completed",
                    extra=log_context(
                        component="vertex_ai_session",
                        action="create_session",
                        session_id=session_id,
                        duration_ms=(time.time() - t0) * 1000,
                        extra={"state_keys": list(initial_state.keys())},
                    ),
                )
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

            # Cache session metadata to Redis (survives API restarts)
            try:
                redis_service = get_redis_service()
                if redis_service.is_available():
                    # Convert datetime objects to ISO strings for JSON serialization
                    cache_data = {
                        **conversation_info,
                        "created_at": conversation_info["created_at"].isoformat(),
                        "last_updated": conversation_info["last_updated"].isoformat(),
                    }
                    cache_key = session_metadata_key(user_id, session_id)
                    redis_service.set_json(
                        cache_key, cache_data, ttl=SESSION_METADATA_TTL_SECONDS
                    )
                    logger.info(
                        f"Cached new session metadata to Redis for {session_id}"
                    )

                    # Update the user's session ID list in Redis
                    ids_key = user_session_ids_key(user_id)
                    cached_ids = redis_service.get_json(ids_key)
                    if isinstance(cached_ids, list):
                        cached_ids.append(session_id)
                        redis_service.set_json(
                            ids_key, cached_ids, ttl=SESSION_METADATA_TTL_SECONDS
                        )
            except Exception as e:
                logger.warning(f"Failed to cache new session to Redis: {e}")

            logger.info(
                "create_conversation completed",
                extra=log_context(
                    component="chat",
                    action="create_conversation",
                    duration_ms=(time.time() - t_total) * 1000,
                    extra={"session_id": session_id},
                ),
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

    async def resolve_pending_session(
        self, user_id: str, pending_id: str
    ) -> str:
        """Resolve a pending session ID to a real Vertex AI session ID.

        Args:
            user_id: User identifier
            pending_id: The pending_* session ID returned by POST /conversations

        Returns:
            The real Vertex AI session ID
        """
        # Use pop() to atomically claim the task — prevents double-resolution
        # when two concurrent requests arrive with the same pending_id.
        task = self._pending_sessions.pop(pending_id, None)
        if not task:
            return pending_id

        try:
            real_session_id = await task
        except Exception as e:
            logger.error(f"Background session creation failed for {pending_id}: {e}")
            raise

        # Swap pending → real in _user_sessions
        pending_key = f"{user_id}:{pending_id}"
        real_key = f"{user_id}:{real_session_id}"

        metadata = self._user_sessions.pop(pending_key, None)
        if metadata:
            metadata["session_id"] = real_session_id
            self._user_sessions[real_key] = metadata

        logger.info(
            f"Resolved pending session {pending_id} → {real_session_id}",
        )
        return real_session_id

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
            # Resolve pending sessions created by deferred POST /conversations
            if session_id.startswith("pending_"):
                session_id = await self.resolve_pending_session(user_id, session_id)

            session_key = f"{user_id}:{session_id}"

            # First check in-memory cache
            if session_key in self._user_sessions:
                logger.info(
                    f"Using existing session {session_id} from in-memory cache for user {user_id}"
                )
                return session_id

            # Check Redis cache (survives API restarts)
            try:
                redis_service = get_redis_service()
                if redis_service.is_available():
                    cache_key = session_metadata_key(user_id, session_id)
                    cached_session = redis_service.get_json(cache_key)

                    if cached_session:
                        logger.info(
                            f"Using existing session {session_id} from Redis cache for user {user_id}"
                        )
                        # Convert ISO datetime strings back to datetime objects
                        from datetime import datetime as dt_class

                        if isinstance(cached_session.get("created_at"), str):
                            cached_session["created_at"] = dt_class.fromisoformat(
                                cached_session["created_at"]
                            )
                        if isinstance(cached_session.get("last_updated"), str):
                            cached_session["last_updated"] = dt_class.fromisoformat(
                                cached_session["last_updated"]
                            )

                        # Restore to in-memory cache
                        self._user_sessions[session_key] = cached_session
                        return session_id
            except Exception as e:
                logger.warning(f"Failed to check Redis for session {session_id}: {e}")

            # Not in cache — determine session type
            is_adk_session = not (
                session_id.startswith("chat_")
                or session_id.startswith("fallback_")
                or session_id.startswith("manual_")
                or session_id.startswith("pending_")
            )

            if is_adk_session:
                # Skip the blocking get_session() validation call — stream_query will
                # validate the session itself. Register optimistically in-memory cache.
                logger.info(
                    f"Optimistically registering ADK session {session_id} for user {user_id} (skipping validation call)"
                )
                conversation_info = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "conversation_name": conversation_name,
                    "created_at": datetime.now(timezone.utc),
                    "last_updated": datetime.now(timezone.utc),
                    "message_count": 0,
                }
                self._user_sessions[session_key] = conversation_info
                return session_id
            else:
                logger.info(
                    f"Session {session_id} has non-ADK format and not in cache - creating proper ADK session"
                )

            logger.info(
                f"Creating new conversation for user {user_id} (original session {session_id} not found or invalid)"
            )
        # Create new conversation with user_context and account_id
        return await self.create_conversation(
            user_id, user_context, conversation_name, account_id
        )

    def update_conversation_metadata(
        self, user_id: str, session_id: str, conversation_name: str | None = None
    ) -> bool:
        """Update conversation metadata and sync to Redis."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            if conversation_name is not None:
                self._user_sessions[session_key]["conversation_name"] = (
                    conversation_name
                )
            self._user_sessions[session_key]["last_updated"] = datetime.now(
                timezone.utc
            )

            # Sync to Redis for persistence across API restarts
            try:
                redis_service = get_redis_service()
                if redis_service.is_available():
                    cache_key = session_metadata_key(user_id, session_id)
                    redis_service.set_json(
                        cache_key,
                        self._user_sessions[session_key],
                        ttl_seconds=SESSION_METADATA_TTL_SECONDS,
                    )
            except Exception as e:
                logger.warning(f"Failed to sync session metadata to Redis: {e}")

            return True
        return False

    async def _delete_old_session(self, user_id: str, session_id: str) -> None:
        """Delete an old session from Vertex AI (fire-and-forget)."""
        try:
            await self.session_service.delete_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            logger.info(f"Cleaned up old Vertex AI session: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up old session {session_id}: {e}")

    def _get_cached_conversations(self, user_id: str) -> list[ConversationInfo]:
        """Build conversation list from in-memory cache for a user.

        Args:
            user_id: User identifier

        Returns:
            Sorted list of ConversationInfo from the last 7 days
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        conversations = []
        prefix = f"{user_id}:"

        for session_key, info in self._user_sessions.items():
            if not session_key.startswith(prefix):
                continue

            last_updated = info.get("last_updated", datetime.now(timezone.utc))
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            if last_updated < cutoff:
                continue

            conversations.append(
                ConversationInfo(
                    session_id=info["session_id"],
                    conversation_name=info.get("conversation_name")
                    or f"Chat {info['session_id'][-8:]}",
                    created_at=info.get("created_at", datetime.now(timezone.utc)),
                    last_updated=last_updated,
                    message_count=info.get("message_count", 0),
                    preview=info.get("preview"),
                )
            )

        conversations.sort(key=lambda x: x.last_updated, reverse=True)
        return conversations

    async def get_user_conversations(self, user_id: str) -> list[ConversationInfo]:
        """Get conversations for a user from the last 7 days."""
        # Serve from cache if we've already loaded this user's sessions
        if user_id in self._sessions_loaded_for:
            conversations = self._get_cached_conversations(user_id)
            logger.info(
                "get_user_conversations served from cache",
                extra=log_context(
                    component="vertex_ai_session",
                    action="get_user_conversations",
                    duration_ms=0,
                    results_count=len(conversations),
                    extra={"cache_hit": True},
                ),
            )
            return conversations

        conversations = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        # Try Redis session list before expensive list_sessions call
        try:
            redis_service = get_redis_service()
            if redis_service.is_available():
                cached_ids = redis_service.get_json(user_session_ids_key(user_id))
                if cached_ids and isinstance(cached_ids, list):
                    # Reconstruct _user_sessions from per-session Redis metadata
                    for sid in cached_ids:
                        session_key = f"{user_id}:{sid}"
                        if session_key not in self._user_sessions:
                            meta = redis_service.get_json(
                                session_metadata_key(user_id, sid)
                            )
                            if meta:
                                if isinstance(meta.get("created_at"), str):
                                    meta["created_at"] = datetime.fromisoformat(
                                        meta["created_at"]
                                    )
                                if isinstance(meta.get("last_updated"), str):
                                    meta["last_updated"] = datetime.fromisoformat(
                                        meta["last_updated"]
                                    )
                                self._user_sessions[session_key] = meta

                    self._sessions_loaded_for.add(user_id)
                    result = self._get_cached_conversations(user_id)
                    logger.info(
                        "get_user_conversations restored from Redis",
                        extra=log_context(
                            component="vertex_ai_session",
                            action="get_user_conversations",
                            duration_ms=0,
                            results_count=len(result),
                            extra={"cache_hit": True, "source": "redis"},
                        ),
                    )
                    return result
        except Exception as e:
            logger.warning(f"Failed to load session list from Redis: {e}")

        try:
            t_start = time.time()

            t0 = time.time()
            # ADK's list_sessions uses a synchronous for-loop over a
            # network-fetching iterator, which blocks the asyncio event
            # loop for the full duration (~21s for 38 sessions).  Running
            # it in a separate thread with its own event loop prevents it
            # from starving concurrent requests (e.g. POST /conversations).
            _ss = self.session_service

            def _list_sessions_sync() -> Any:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        _ss.list_sessions(
                            app_name=APP_NAME, user_id=user_id
                        )
                    )
                finally:
                    loop.close()

            sessions = await asyncio.to_thread(_list_sessions_sync)
            logger.info(
                "Vertex AI list_sessions completed",
                extra=log_context(
                    component="vertex_ai_session",
                    action="list_sessions",
                    duration_ms=(time.time() - t0) * 1000,
                ),
            )

            # Handle ListSessionsResponse - it might have a sessions attribute
            session_list = (
                sessions.sessions if hasattr(sessions, "sessions") else sessions
            )

            redis_service = None
            try:
                redis_service = get_redis_service()
                if not redis_service.is_available():
                    redis_service = None
            except Exception:
                pass

            old_session_ids: list[str] = []

            for session in session_list:
                session_id = getattr(session, "id", None) or getattr(
                    session, "session_id", str(session)
                )
                session_key = f"{user_id}:{session_id}"
                cached_info = self._user_sessions.get(session_key)

                # Try Redis when in-memory cache is empty (e.g. after restart)
                if not cached_info and redis_service:
                    try:
                        cache_key = session_metadata_key(user_id, session_id)
                        redis_data = redis_service.get_json(cache_key)
                        if redis_data:
                            if isinstance(redis_data.get("created_at"), str):
                                redis_data["created_at"] = datetime.fromisoformat(
                                    redis_data["created_at"]
                                )
                            if isinstance(redis_data.get("last_updated"), str):
                                redis_data["last_updated"] = datetime.fromisoformat(
                                    redis_data["last_updated"]
                                )
                            self._user_sessions[session_key] = redis_data
                            cached_info = redis_data
                    except Exception as e:
                        logger.warning(f"Failed to load session {session_id} from Redis: {e}")

                cached_info = cached_info or {}

                last_updated = (
                    getattr(session, "update_time", None)
                    or cached_info.get("last_updated", datetime.now(timezone.utc))
                )
                if isinstance(last_updated, str):
                    last_updated = datetime.fromisoformat(last_updated)

                # Skip sessions older than 7 days and mark for cleanup
                if last_updated < cutoff:
                    old_session_ids.append(session_id)
                    continue

                conversations.append(
                    ConversationInfo(
                        session_id=session_id,
                        conversation_name=cached_info.get("conversation_name")
                        or f"Chat {session_id[-8:]}",
                        created_at=getattr(session, "create_time", None)
                        or cached_info.get("created_at", datetime.now(timezone.utc)),
                        last_updated=last_updated,
                        message_count=cached_info.get("message_count", 0),
                        preview=cached_info.get("preview"),
                    )
                )

            # Fire-and-forget cleanup of old sessions from Vertex AI
            if old_session_ids:
                logger.info(
                    f"Cleaning up {len(old_session_ids)} old sessions from Vertex AI"
                )
                for old_id in old_session_ids:
                    task = asyncio.create_task(
                        self._delete_old_session(user_id, old_id)
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

        except Exception as e:
            logger.error(f"Failed to get sessions from ADK service: {e}")
            # Fallback to cached sessions if ADK service fails
            for session_key, info in self._user_sessions.items():
                if session_key.startswith(f"{user_id}:"):
                    last_updated = info["last_updated"]
                    if isinstance(last_updated, str):
                        last_updated = datetime.fromisoformat(last_updated)
                    if last_updated < cutoff:
                        continue
                    conversations.append(
                        ConversationInfo(
                            session_id=info["session_id"],
                            conversation_name=info.get("conversation_name"),
                            created_at=info["created_at"],
                            last_updated=last_updated,
                            message_count=info["message_count"],
                            preview=info.get("preview"),
                        )
                    )

        # Sort by last updated (most recent first)
        conversations.sort(key=lambda x: x.last_updated, reverse=True)

        # Mark this user as loaded so subsequent calls skip list_sessions
        self._sessions_loaded_for.add(user_id)

        # Persist session ID list to Redis for restart resilience
        try:
            redis_service = get_redis_service()
            if redis_service.is_available():
                session_ids = [c.session_id for c in conversations]
                redis_service.set_json(
                    user_session_ids_key(user_id),
                    session_ids,
                    ttl=SESSION_METADATA_TTL_SECONDS,
                )
        except Exception as e:
            logger.warning(f"Failed to persist session list to Redis: {e}")

        logger.info(
            "get_user_conversations completed",
            extra=log_context(
                component="vertex_ai_session",
                action="get_user_conversations",
                duration_ms=(time.time() - t_start) * 1000,
                results_count=len(conversations),
                extra={"cache_hit": False},
            ),
        )
        return conversations

    async def delete_conversation(self, user_id: str, session_id: str) -> bool:
        """Delete a conversation and its session."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            # If this is a pending session, cancel the background creation
            if session_id in self._pending_sessions:
                self._pending_sessions[session_id].cancel()
                del self._pending_sessions[session_id]
                logger.info(f"Cancelled pending session creation for {session_id}")
            else:
                try:
                    await self.session_service.delete_session(
                        app_name=APP_NAME, user_id=user_id, session_id=session_id
                    )
                    logger.info(f"Deleted ADK session {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete ADK session {session_id}: {e}")

            # Remove from in-memory cache
            del self._user_sessions[session_key]

            # Remove from Redis cache
            try:
                redis_service = get_redis_service()
                if redis_service.is_available():
                    cache_key = session_metadata_key(user_id, session_id)
                    redis_service.delete(cache_key)

                    # Remove from user's session ID list
                    ids_key = user_session_ids_key(user_id)
                    cached_ids = redis_service.get_json(ids_key)
                    if isinstance(cached_ids, list) and session_id in cached_ids:
                        cached_ids.remove(session_id)
                        redis_service.set_json(
                            ids_key, cached_ids, ttl=SESSION_METADATA_TTL_SECONDS
                        )

                    logger.info(f"Deleted session from Redis cache: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to delete session from Redis: {e}")

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

    def update_session_preview(self, user_id: str, session_id: str, preview: str) -> dict | None:
        """Update the preview for a session and return the session metadata for caching."""
        session_key = f"{user_id}:{session_id}"
        if session_key in self._user_sessions:
            self._user_sessions[session_key]["preview"] = preview
            return self._user_sessions[session_key]
        return None

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
            t0 = time.time()
            session_data = await self.session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            logger.info(
                "Vertex AI get_session completed",
                extra=log_context(
                    component="vertex_ai_session",
                    action="get_session",
                    session_id=session_id,
                    duration_ms=(time.time() - t0) * 1000,
                ),
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

            # ADK session already maintains conversation history — no need to re-inject
            formatted_input = user_input

            logger.info(
                f"[CHAT] Processing message for user {user_id}: {user_input[:100]}..."
            )

            # Get or create session for this user (credentials now passed via session state)
            actual_session_id = await self.get_or_create_session(
                user_id, user_context, session_id, conversation_name, account_id
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
                f"[PERF] Sending to Agent Engine for user {user_id}, session {actual_session_id}, query_len={len(formatted_input)}"
            )

            # Use the agent_engines API with proper Queryable interface
            try:
                available_methods = [
                    method
                    for method in dir(self.agent_engine)
                    if not method.startswith("_")
                ]
                logger.debug(f"Available methods on agent engine: {available_methods}")

                # Try the agent_engines query patterns
                response = None

                # The Agent Engine has stream_query method - let's collect the stream into a single response
                if hasattr(self.agent_engine, "stream_query"):
                    response_parts = []
                    try:
                        loop = asyncio.get_event_loop()
                        t_query = time.time()
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
                                timeout=1800.0,
                            )
                            logger.info(
                                "Agent Engine stream_query completed",
                                extra=log_context(
                                    component="agent_engine",
                                    action="stream_query",
                                    session_id=actual_session_id,
                                    duration_ms=(time.time() - t_query) * 1000,
                                ),
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
                            logger.debug(
                                f"Received chunk type: {type(chunk)}, content preview: {str(chunk)[:100]}..."
                            )

                            if isinstance(chunk, dict):
                                logger.debug(
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
                                                response_parts.append(part["text"])
                                            elif isinstance(part, dict) and _is_function_event_part(part):
                                                logger.debug(
                                                    "Skipping function_call/function_response part"
                                                )
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
                                            response_parts.append(part["text"])
                                        elif isinstance(part, dict) and _is_function_event_part(part):
                                            logger.debug(
                                                "Skipping function_call/function_response part"
                                            )
                                        else:
                                            response_parts.append(str(part))
                                # Handle string content
                                elif "content" in chunk:
                                    response_parts.append(str(chunk["content"]))
                                else:
                                    if not _is_function_event_part(chunk):
                                        response_parts.append(str(chunk))
                                    else:
                                        logger.debug(
                                            "Skipping function debug data in non-streaming response"
                                        )
                            elif isinstance(chunk, str):
                                logger.debug(f"Processing string chunk: {chunk[:50]}...")

                                # Skip JSON-format function events (double-quoted keys)
                                # Agent Engine may return these as JSON strings, not Python dicts
                                if _is_function_event_json(chunk):
                                    logger.debug(
                                        "Skipping JSON function event data"
                                    )
                                    continue

                                if chunk.startswith("{'parts'") and "'text':" in chunk:
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
                                                    response_parts.append(part["text"])
                                        else:
                                            response_parts.append(chunk)
                                    except (ValueError, SyntaxError) as e:
                                        logger.warning(
                                            f"Failed to parse chunk as dict: {e}"
                                        )
                                        response_parts.append(chunk)
                                else:
                                    if _contains_function_event_str(chunk):
                                        logger.debug(
                                            "Found function data in string chunk, extracting text"
                                        )
                                        if "}}" in chunk:
                                            parts = chunk.rsplit("}}", 1)
                                            if len(parts) == 2 and parts[1].strip():
                                                remaining = parts[1].strip()
                                                if not remaining.startswith("{"):
                                                    response_parts.append(remaining)
                                    else:
                                        response_parts.append(chunk)
                            elif hasattr(chunk, "content"):
                                response_parts.append(str(chunk.content))
                            else:
                                response_parts.append(str(chunk))

                        full_response = "".join(response_parts).strip()

                        # Clean up function_call/function_response data from the final response
                        if full_response and _contains_function_event_str(full_response):
                            logger.debug(
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

                logger.debug(f"Response received: {type(response)}")

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
            ) from e

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

            # ADK session already maintains conversation history — no need to re-inject
            formatted_input = user_input

            logger.info(
                f"[CHAT] Processing stream message for user {user_id}: {user_input[:100]}..."
            )

            # Get or create session for this user (credentials now passed via session state)
            actual_session_id = await self.get_or_create_session(
                user_id, user_context, session_id, conversation_name, account_id
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
                f"[PERF] Streaming to Agent Engine for user {user_id}, session {actual_session_id}, query_len={len(formatted_input)}"
            )

            # Try streaming with agent_engines API
            try:
                available_methods = [
                    method
                    for method in dir(self.agent_engine)
                    if not method.startswith("_")
                ]
                logger.debug(f"Available methods on agent engine: {available_methods}")

                # Use stream_query with correct parameters for deployed agent
                if hasattr(self.agent_engine, "stream_query"):

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
                                        elif isinstance(part, dict) and _is_function_event_part(part):
                                            logger.debug(
                                                "Skipping function_call/function_response part in stream"
                                            )
                                        else:
                                            yield str(part)
                                else:
                                    yield str(content)
                            # Handle direct structure: {'parts': [{'text': '...'}]}
                            elif "parts" in chunk and isinstance(chunk["parts"], list):
                                for part in chunk["parts"]:
                                    if isinstance(part, dict) and "text" in part:
                                        yield part["text"]
                                    elif isinstance(part, dict) and _is_function_event_part(part):
                                        logger.debug(
                                            "Skipping function_call/function_response part in stream"
                                        )
                                    else:
                                        yield str(part)
                            elif "content" in chunk:
                                yield str(chunk["content"])
                            else:
                                if not _is_function_event_part(chunk):
                                    yield str(chunk)
                        elif isinstance(chunk, str):
                            # Log the raw chunk for debugging
                            logger.debug(
                                f"Raw chunk received (first 200 chars): {chunk[:200]}..."
                            )

                            # Skip JSON-format function events (double-quoted keys)
                            # Agent Engine may return these as JSON strings, not Python dicts
                            if _is_function_event_json(chunk):
                                logger.debug(
                                    "Skipping JSON function event data in stream"
                                )
                                continue

                            # Parse and clean string chunks that might contain function data
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
                            elif _contains_function_event_str(chunk):
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

                logger.debug(f"Streaming response received: {type(response)}")

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


def _preload_agent_engine() -> None:
    """Pre-load agent engine connection to avoid lazy-loading delay on first chat request.

    Called from FastAPI startup event in main.py.
    """
    try:
        # Trigger the property to initialize the connection
        _ = agent_client.agent_engine
        logger.info("Agent Engine pre-loaded successfully on startup")
    except Exception as e:
        logger.warning(
            f"Failed to pre-load Agent Engine (will lazy-load on first request): {e}"
        )


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest, user_context: UserContext = Depends(get_current_user_context)
):
    """
    Get a chat completion from the Vertex AI Agent Engine.

    This endpoint processes a conversation with the KEN-E marketing assistant
    and returns a response from the deployed Agent Engine.
    """
    _exit_stack = ExitStack()
    try:
        # PERFORMANCE: Log request arrival time for latency measurement
        logger.info(
            f"[PERF] POST /chat/completions RECEIVED at {time.time():.3f} for user {user_context.user_id}"
        )

        # SECURITY: Validate account access if account_id provided
        if request.account_id and not user_context.has_account_access(
            request.account_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {request.account_id}",
            )
        # Set Weave root span metadata for trace filtering (scoped via contextvars)
        _attrs_cm = None
        if WEAVE_AVAILABLE:
            try:
                _exit_stack.enter_context(weave.attributes({
                    "account_id": request.account_id or "unknown",
                    "session_id": request.session_id or "unknown",
                    "user_id": user_context.user_id or "unknown",
                    "environment": os.getenv("ENVIRONMENT", "development"),
                    "agent": "ken_e_chatbot",
                }))
            except Exception:
                _attrs_cm = None

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

            # Fire post-response writes in background (non-blocking)
            async def _post_response_writes(
                uid: str, sid: str, content: str
            ) -> None:
                try:
                    preview = (
                        content[:100] + "..."
                        if len(content) > 100
                        else content
                    )
                    session_metadata = agent_client.update_session_preview(
                        uid, sid, preview
                    )
                    if session_metadata:
                        try:
                            redis_svc = get_redis_service()
                            if redis_svc.is_available():
                                cache_key = session_metadata_key(uid, sid)
                                redis_svc.set_json(
                                    cache_key,
                                    session_metadata,
                                    ttl_seconds=SESSION_METADATA_TTL_SECONDS,
                                )
                        except Exception:
                            pass
                except Exception:
                    logger.debug(f"Background session preview update failed for {sid}")

            task = asyncio.create_task(
                _post_response_writes(
                    user_context.user_id,
                    actual_session_id,
                    response_content,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

            # Fire reauth check in background (non-blocking, result used on next request)
            async def _check_reauth_bg(uid: str, sid: str) -> None:
                try:
                    from app.adk.session.recovery import (
                        get_recovery_service as _get_recovery,
                    )

                    _recovery = _get_recovery()
                    _session = await _recovery._session_service.get_session(
                        app_name=APP_NAME,
                        user_id=uid,
                        session_id=sid,
                    )
                    if _session and _session.state.get("_requires_reauth"):
                        _reauth_cache[f"{uid}:{sid}"] = {
                            "requires_reauth": True,
                            "service": _session.state.get(
                                "_reauth_service", "google-analytics"
                            ),
                        }
                        _session.state.pop("_requires_reauth", None)
                        _session.state.pop("_reauth_service", None)
                except Exception:
                    pass

            task = asyncio.create_task(
                _check_reauth_bg(user_context.user_id, actual_session_id)
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

            # Use cached reauth result from previous request's background check
            reauth_key = f"{user_context.user_id}:{actual_session_id}"
            metadata = _reauth_cache.pop(reauth_key, None)

            return ChatResponse(
                content=response_content,
                session_id=actual_session_id,
                conversation_name=request.conversation_name,
                metadata=metadata,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
    finally:
        _exit_stack.close()


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

    Returns immediately with a pending session ID while the real
    Vertex AI session is created in the background (~3.8s).  The
    pending ID is resolved transparently when the first message
    is sent via POST /completions.
    """
    try:
        # SECURITY: Validate account access if account_id provided
        if request.account_id and not user_context.has_account_access(
            request.account_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {request.account_id}",
            )

        now = datetime.now(timezone.utc)
        pending_id = f"pending_{uuid4()}"
        user_id = user_context.user_id

        logger.info(
            f"Creating deferred conversation {pending_id} for user: {user_id}, account: {request.account_id}"
        )

        # Store metadata immediately so the UI can display the conversation
        conversation_info = {
            "session_id": pending_id,
            "user_id": user_id,
            "conversation_name": request.conversation_name,
            "created_at": now,
            "last_updated": now,
            "message_count": 0,
        }
        agent_client._user_sessions[f"{user_id}:{pending_id}"] = conversation_info

        # Kick off real session creation in the background
        async def _create_in_background() -> str:
            sid = await agent_client.create_conversation(
                user_id=user_id,
                user_context=user_context,
                conversation_name=request.conversation_name,
                account_id=request.account_id,
            )
            return sid

        agent_client._pending_sessions[pending_id] = asyncio.create_task(
            _create_in_background()
        )

        return ConversationInfo(
            session_id=pending_id,
            conversation_name=request.conversation_name,
            created_at=now,
            last_updated=now,
            message_count=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        ) from e


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
        ) from e


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

        # Return updated info directly from cache (avoids list_sessions call)
        session_key = f"{user_context.user_id}:{session_id}"
        cached = agent_client._user_sessions.get(session_key, {})
        now = datetime.now(timezone.utc)
        return ConversationInfo(
            session_id=session_id,
            conversation_name=cached.get("conversation_name", request.conversation_name),
            created_at=cached.get("created_at", now),
            last_updated=cached.get("last_updated", now),
            message_count=cached.get("message_count", 0),
            preview=cached.get("preview"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation",
        ) from e


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
        ) from e


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
        ) from e


class SessionRecoveryResponse(BaseModel):
    """Response for session recovery."""

    success: bool
    session_id: str | None = None
    conversation_history: list[dict[str, Any]] | None = None
    message_count: int = 0


@router.get("/sessions/recoverable")
async def get_recoverable_sessions(
    limit: int = 10,
    user_context: UserContext = Depends(get_current_user_context),
) -> list[RecoverableSessionInfo]:
    """List sessions available for recovery.

    Returns sessions from the last 7 days that can be resumed.
    """
    try:
        from app.adk.session.recovery import get_recovery_service

        recovery_svc = get_recovery_service()
        sessions = await recovery_svc.list_recoverable_sessions(
            user_id=user_context.user_id, limit=limit
        )
        return [
            RecoverableSessionInfo(
                session_id=s.session_id,
                conversation_name=s.conversation_name,
                last_updated=s.last_updated.isoformat() if s.last_updated else "",
                message_count=s.message_count,
                preview=s.preview,
            )
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Error listing recoverable sessions: {e}")
        return []


@router.post("/sessions/{session_id}/recover")
async def recover_session(
    session_id: str,
    user_context: UserContext = Depends(get_current_user_context),
) -> SessionRecoveryResponse:
    """Recover a previous session, restoring state and conversation history."""
    try:
        from app.adk.session.recovery import get_recovery_service

        recovery_svc = get_recovery_service()
        result = await recovery_svc.recover_session(
            user_id=user_context.user_id, session_id=session_id
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error or "Session not found",
            )

        history = result.conversation_history or []
        return SessionRecoveryResponse(
            success=True,
            session_id=result.session_id,
            conversation_history=history,
            message_count=len(history),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recovering session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recover session",
        ) from e


@router.post("/cache/invalidate/{account_id}")
async def invalidate_cache(
    account_id: str, user_context: UserContext = Depends(get_current_user)
):
    """
    Invalidate cached data for an account (Phase 3 performance optimization).

    This endpoint clears cached organization context and GA credentials
    for a specific account. Use when account data is updated.

    SECURITY: Validates user has access to the account before invalidating cache.
    """
    try:
        # SECURITY: Validate user has access to this account
        if not user_context.has_account_access(account_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {account_id}",
            )

        redis_service = get_redis_service()

        if not redis_service.is_available():
            return {
                "message": "Redis cache not available - no action taken",
                "account_id": account_id,
                "invalidated": False,
            }

        # Invalidate org context
        org_key = org_context_key(account_id)
        org_deleted = redis_service.delete(org_key)

        # Invalidate GA credentials
        ga_key = ga_credentials_key(account_id)
        ga_deleted = redis_service.delete(ga_key)

        logger.info(
            f"Cache invalidated for account {account_id}: "
            f"org_context={org_deleted}, ga_creds={ga_deleted}"
        )

        return {
            "message": "Cache invalidated successfully",
            "account_id": account_id,
            "invalidated": {
                "organization_context": org_deleted,
                "ga_credentials": ga_deleted,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating cache for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache",
        ) from e

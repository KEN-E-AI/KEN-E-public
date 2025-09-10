"""
Chat API endpoints for Vertex AI Agent Engine integration.
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import vertexai
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.adk.sessions import VertexAiSessionService
from pydantic import BaseModel, Field
from vertexai import agent_engines

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..auth.user_context import get_current_user_context
from ..firestore import get_firestore_service
from ..services.ga_credential_helper import GACredentialHelper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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
        self.agent_engine_id = os.getenv("KEN_E_ENGINE_ID") or os.getenv(
            "VERTEX_AI_AGENT_ENGINE_ID"
        )

        if not self.agent_engine_id:
            logger.warning(
                "KEN_E_ENGINE_ID or VERTEX_AI_AGENT_ENGINE_ID not set. Chat functionality will be limited."
            )

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
                logger.info(
                    f"Attempting to connect to Agent Engine: {self.agent_engine_id}"
                )
                logger.info(
                    f"Using project: {self.project_id}, location: {self.location}"
                )

                # Use agent_engines.get() to get the deployed agent engine
                self._agent_engine = agent_engines.get(self.agent_engine_id)

                # Log the available methods for debugging
                available_methods = [
                    method
                    for method in dir(self._agent_engine)
                    if not method.startswith("_")
                ]
                logger.info(f"Available methods on agent engine: {available_methods}")

                logger.info(
                    f"Successfully connected to Agent Engine: {self.agent_engine_id}"
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
                    agent_engine_id=self.agent_engine_id.split("/")[
                        -1
                    ],  # Extract just the ID part
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
        self, user_id: str, conversation_name: str | None = None
    ) -> str:
        """Create a new conversation using ADK session service."""
        try:
            logger.info(f"Creating new conversation for user {user_id}")

            # Create ADK session
            try:
                logger.info(f"Attempting to create ADK session for user: {user_id}")
                logger.info(
                    f"Session service initialized: {self._session_service is not None}"
                )
                logger.info(f"Agent engine ID: {self.agent_engine_id}")

                session_result = await self.session_service.create_session(
                    app_name="ken-e-chatbot", user_id=user_id
                )
                session_id = (
                    session_result.id
                    if hasattr(session_result, "id")
                    else str(session_result)
                )
                logger.info(
                    f"Successfully created ADK session: {session_id} for user: {user_id}"
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
        session_id: str | None = None,
        conversation_name: str | None = None,
    ) -> str:
        """Get an existing session or create a new one."""
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
                            app_name="ken-e-chatbot",
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
        # Create new conversation
        return await self.create_conversation(user_id, conversation_name)

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
                app_name="ken-e-chatbot", user_id=user_id
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
                    app_name="ken-e-chatbot", user_id=user_id, session_id=session_id
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
                app_name="ken-e-chatbot", user_id=user_id, session_id=session_id
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

            logger.info(f"[CHAT] Processing message for user {user_id}: {user_input[:100]}...")
            logger.info(f"[CHAT] User context: {user_context.accessible_accounts if user_context else 'No context'}")

            # Check if this might be a Google Analytics query and inject OAuth credentials
            ga_keywords = ['analytics', 'traffic', 'users', 'sessions', 'pageviews',
                          'bounce rate', 'ga4', 'google analytics', 'website visitors',
                          'conversion', 'acquisition', 'real-time', 'realtime', 'property']

            is_ga_query = any(keyword in user_input.lower() for keyword in ga_keywords)

            # Also check if this is a follow-up in a GA conversation
            session_key = f"{user_id}:{session_id}" if session_id else None
            is_ga_followup = False
            if session_key and session_key in self._user_sessions:
                is_ga_followup = self._user_sessions[session_key].get("is_ga_conversation", False)

            logger.info(f"GA query detection: {is_ga_query} or follow-up: {is_ga_followup} for input: {user_input[:100]}")
            print(f"[DEBUG] GA query detection: {is_ga_query} or follow-up: {is_ga_followup} for input: {user_input[:100]}")

            if is_ga_query or is_ga_followup:
                # Try to get GA OAuth credentials from any accessible account that has them
                logger.info(f"User has {len(user_context.accessible_accounts)} accessible accounts: {user_context.accessible_accounts}")
                print(f"[DEBUG] User has {len(user_context.accessible_accounts) if user_context.accessible_accounts else 0} accessible accounts: {user_context.accessible_accounts}")
                if user_context.accessible_accounts:
                    try:
                        firestore_service = get_firestore_service()
                        db = firestore_service.get_client()
                        ga_helper = GACredentialHelper(db)

                        # Try each accessible account until we find one with GA credentials
                        ga_creds = None
                        for account_id in user_context.accessible_accounts:
                            # Get and format GA credentials
                            ga_creds = await ga_helper.get_and_format_credentials(account_id)
                            if ga_creds:
                                logger.info(f"Found GA OAuth credentials in account {account_id}")
                                print(f"[DEBUG] Found GA OAuth credentials in account {account_id}")
                                break
                            else:
                                logger.debug(f"No GA credentials in account {account_id}, trying next...")
                                print(f"[DEBUG] No GA credentials in account {account_id}, trying next...")

                        if ga_creds:
                            # Create a structured message with credentials embedded
                            enhanced_message = {
                                "message": user_input,
                                "tenant_id": ga_creds["tenant_id"],
                                "tenant_credentials": ga_creds["tenant_credentials"]
                            }
                            # Convert to JSON string for the agent
                            import json
                            user_input = json.dumps(enhanced_message)
                            logger.info(f"Injected GA OAuth credentials (tenant_id: {ga_creds['tenant_id'][:20]}...)")
                            print("[DEBUG] Successfully injected GA credentials into message")
                        else:
                            logger.warning(f"No GA OAuth credentials found in any of the {len(user_context.accessible_accounts)} accessible accounts")
                            print("[DEBUG] Failed to find GA credentials in any accessible account")
                    except Exception as e:
                        logger.error(f"Failed to inject GA credentials: {e}")
                        # Continue with original message if credential injection fails

            # Get or create session for this user
            actual_session_id = await self.get_or_create_session(
                user_id, session_id, conversation_name
            )

            # Mark session as GA conversation if needed
            session_key = f"{user_id}:{actual_session_id}"
            if is_ga_query and session_key in self._user_sessions:
                self._user_sessions[session_key]["is_ga_conversation"] = True
                logger.info(f"Marked session {actual_session_id} as GA conversation")

            # Check if this is the first message and we need to generate a conversation name
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
            logger.info(f"Query: {user_input[:100]}...")
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
                                            message=user_input,
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
                                    if not ("function_call" in chunk or "function_response" in chunk):
                                        response_parts.append(str(chunk))
                                    else:
                                        logger.info("Skipping function debug data in non-streaming response")
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
                                    if "{'function_call'" in chunk or "{'function_response'" in chunk:
                                        # Try to extract just the text after the function data
                                        logger.info("Found function data in string chunk, attempting to extract text")

                                        # Look for text after the last }}
                                        if "}}" in chunk:
                                            parts = chunk.rsplit("}}", 1)
                                            if len(parts) == 2 and parts[1].strip():
                                                remaining = parts[1].strip()
                                                if not remaining.startswith("{"):
                                                    logger.info(f"Extracted text after function data: {remaining[:50]}...")
                                                    response_parts.append(remaining)
                                                else:
                                                    logger.info("Remaining part is another JSON object, skipping")
                                            else:
                                                logger.info("No text found after function data, skipping entire chunk")
                                        else:
                                            logger.info("No }} found in chunk with function data, skipping")
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
                        if full_response and ("{'function_call'" in full_response or "{'function_response'" in full_response):
                            logger.info(f"Cleaning function data from response (length: {len(full_response)})")
                            # Try to extract only the text after function blocks
                            if "}}" in full_response:
                                # Split by the last occurrence of }} and take what comes after
                                parts = full_response.rsplit("}}", 1)
                                if len(parts) == 2 and parts[1].strip():
                                    cleaned = parts[1].strip()
                                    if not cleaned.startswith("{"):
                                        logger.info(f"Extracted clean text (length: {len(cleaned)})")
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

            logger.info(f"[CHAT] Processing message for user {user_id}: {user_input[:100]}...")
            logger.info(f"[CHAT] User context: {user_context.accessible_accounts if user_context else 'No context'}")

            # Check if this might be a Google Analytics query and inject OAuth credentials
            ga_keywords = ['analytics', 'traffic', 'users', 'sessions', 'pageviews',
                          'bounce rate', 'ga4', 'google analytics', 'website visitors',
                          'conversion', 'acquisition', 'real-time', 'realtime', 'property']

            is_ga_query = any(keyword in user_input.lower() for keyword in ga_keywords)

            # Also check if this is a follow-up in a GA conversation
            session_key = f"{user_id}:{session_id}" if session_id else None
            is_ga_followup = False
            if session_key and session_key in self._user_sessions:
                is_ga_followup = self._user_sessions[session_key].get("is_ga_conversation", False)

            logger.info(f"GA query detection: {is_ga_query} or follow-up: {is_ga_followup} for input: {user_input[:100]}")
            print(f"[DEBUG] GA query detection: {is_ga_query} or follow-up: {is_ga_followup} for input: {user_input[:100]}")

            if is_ga_query or is_ga_followup:
                # Try to get GA OAuth credentials from any accessible account that has them
                logger.info(f"User has {len(user_context.accessible_accounts)} accessible accounts: {user_context.accessible_accounts}")
                print(f"[DEBUG] User has {len(user_context.accessible_accounts) if user_context.accessible_accounts else 0} accessible accounts: {user_context.accessible_accounts}")
                if user_context.accessible_accounts:
                    try:
                        firestore_service = get_firestore_service()
                        db = firestore_service.get_client()
                        ga_helper = GACredentialHelper(db)

                        # Try each accessible account until we find one with GA credentials
                        ga_creds = None
                        for account_id in user_context.accessible_accounts:
                            # Get and format GA credentials
                            ga_creds = await ga_helper.get_and_format_credentials(account_id)
                            if ga_creds:
                                logger.info(f"Found GA OAuth credentials in account {account_id}")
                                print(f"[DEBUG] Found GA OAuth credentials in account {account_id}")
                                break
                            else:
                                logger.debug(f"No GA credentials in account {account_id}, trying next...")
                                print(f"[DEBUG] No GA credentials in account {account_id}, trying next...")

                        if ga_creds:
                            # Create a structured message with credentials embedded
                            enhanced_message = {
                                "message": user_input,
                                "tenant_id": ga_creds["tenant_id"],
                                "tenant_credentials": ga_creds["tenant_credentials"]
                            }
                            # Convert to JSON string for the agent
                            import json
                            user_input = json.dumps(enhanced_message)
                            logger.info(f"Injected GA OAuth credentials (tenant_id: {ga_creds['tenant_id'][:20]}...)")
                            print("[DEBUG] Successfully injected GA credentials into message")
                        else:
                            logger.warning(f"No GA OAuth credentials found in any of the {len(user_context.accessible_accounts)} accessible accounts")
                            print("[DEBUG] Failed to find GA credentials in any accessible account")
                    except Exception as e:
                        logger.error(f"Failed to inject GA credentials: {e}")
                        # Continue with original message if credential injection fails

            # Get or create session for this user
            actual_session_id = await self.get_or_create_session(
                user_id, session_id, conversation_name
            )

            # Mark session as GA conversation if needed
            session_key = f"{user_id}:{actual_session_id}"
            if is_ga_query and session_key in self._user_sessions:
                self._user_sessions[session_key]["is_ga_conversation"] = True
                logger.info(f"Marked session {actual_session_id} as GA conversation")

            # Check if this is the first message and we need to generate a conversation name
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
            logger.info(f"Query: {user_input[:100]}...")
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
                                message=user_input,
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
                                if not ("function_call" in chunk or "function_response" in chunk):
                                    yield str(chunk)
                        elif isinstance(chunk, str):
                            # Log the raw chunk for debugging
                            logger.debug(f"Raw chunk received (first 200 chars): {chunk[:200]}...")

                            # Parse and clean string chunks that might contain function data
                            # Check if this is a string representation of function_call/function_response
                            if chunk.startswith("{'function_call'") or chunk.startswith("{'function_response'"):
                                # This is debug data, skip it
                                logger.debug(f"Skipping function debug data in chunk: {chunk[:100]}...")
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
                            elif "{'function_call'" in chunk or "{'function_response'" in chunk:
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

                                    logger.debug(f"Found function blocks: {function_blocks[:100]}...")
                                    logger.debug(f"Extracted text part: {text_part[:100]}...")

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
                                    elif not chunk.strip().startswith('{'):
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
                            message=user_input,
                            user_id=user_id,
                            session_id=actual_session_id,
                        )
                    except TypeError:
                        # Fallback to simple query if parameters not supported
                        response = self.agent_engine.query(user_input)

                # Pattern 4: Direct callable
                elif callable(self.agent_engine):
                    logger.info("Trying direct call pattern for streaming fallback")
                    try:
                        # Try with session parameters first
                        response = self.agent_engine(
                            message=user_input,
                            user_id=user_id,
                            session_id=actual_session_id,
                        )
                    except TypeError:
                        # Fallback to simple call if parameters not supported
                        response = self.agent_engine(user_input)

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
        if request.stream:
            # Return streaming response
            async def generate_response():
                async for chunk in agent_client.stream_chat_completion(
                    messages=request.messages,
                    user_context=user_context,
                    session_id=request.session_id,
                    conversation_name=request.conversation_name,
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
    }


@router.post("/conversations", response_model=ConversationInfo)
async def create_conversation(
    request: CreateConversationRequest,
    user_context: UserContext = Depends(get_current_user),
):
    """
    Create a new conversation/session.
    """
    try:
        session_id = await agent_client.create_conversation(
            user_id=user_context.user_id, conversation_name=request.conversation_name
        )

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

    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(user_context: UserContext = Depends(get_current_user)):
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
    user_context: UserContext = Depends(get_current_user),
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
    session_id: str, user_context: UserContext = Depends(get_current_user)
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
    session_id: str, user_context: UserContext = Depends(get_current_user)
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

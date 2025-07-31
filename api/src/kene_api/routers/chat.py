"""
Chat API endpoints for Vertex AI Agent Engine integration.
"""

import logging
import os
from typing import Any, Dict, List, AsyncGenerator
from uuid import uuid4

import vertexai
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from vertexai.preview import reasoning_engines

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: str | None = Field(None, description="Message timestamp")


class ChatRequest(BaseModel):
    """Request for chat completion."""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: str = Field(default_factory=lambda: str(uuid4()), description="Session ID for conversation tracking")


class ChatResponse(BaseModel):
    """Response from chat completion."""
    role: str = Field(default="assistant", description="Response role")
    content: str = Field(..., description="Response content")
    session_id: str = Field(..., description="Session ID")


class AgentEngineClient:
    """Client for interacting with Vertex AI Agent Engine using session-based API."""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
        
        if not self.agent_engine_id:
            logger.warning("VERTEX_AI_AGENT_ENGINE_ID not set. Chat functionality will be limited.")
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        
        self._reasoning_engine = None
        self._user_sessions = {}  # Cache for user sessions
    
    @property
    def reasoning_engine(self):
        """Lazy-load the reasoning engine."""
        if self._reasoning_engine is None and self.agent_engine_id:
            try:
                logger.info(f"Attempting to connect to Agent Engine: {self.agent_engine_id}")
                logger.info(f"Using project: {self.project_id}, location: {self.location}")
                
                self._reasoning_engine = reasoning_engines.ReasoningEngine(
                    self.agent_engine_id
                )
                
                # Log the available methods for debugging
                available_methods = [method for method in dir(self._reasoning_engine) if not method.startswith('_')]
                logger.info(f"Available methods on reasoning engine: {available_methods}")
                
                logger.info(f"Successfully connected to Agent Engine: {self.agent_engine_id}")
            except Exception as e:
                logger.error(f"Failed to connect to Agent Engine: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Agent Engine is currently unavailable: {str(e)}"
                )
        return self._reasoning_engine
    
    def get_or_create_session(self, user_id: str, session_id: str) -> str:
        """Get or create a session for a user."""
        session_key = f"{user_id}:{session_id}"
        
        if session_key not in self._user_sessions:
            try:
                logger.info(f"Creating new session for user {user_id}")
                # Try to create an ADK session if the method exists
                if hasattr(self.reasoning_engine, 'create_session'):
                    session_response = self.reasoning_engine.create_session(user_id=user_id)
                    
                    if isinstance(session_response, dict) and "id" in session_response:
                        actual_session_id = session_response["id"]
                    else:
                        # Fallback to using the provided session_id
                        actual_session_id = session_id
                else:
                    # If create_session doesn't exist, use the provided session_id
                    actual_session_id = session_id
                
                self._user_sessions[session_key] = actual_session_id
                logger.info(f"Using session {actual_session_id} for user {user_id}")
                
            except Exception as e:
                logger.warning(f"Failed to create session, using provided session_id: {e}")
                # Fallback to using the provided session_id
                self._user_sessions[session_key] = session_id
        
        return self._user_sessions[session_key]
    
    def format_messages_for_agent(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """Format messages for the Agent Engine input format."""
        # Convert messages to the format expected by the agent
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "type": "human" if msg.role == "user" else "ai",
                "content": msg.content
            })
        
        return {"messages": formatted_messages}
    
    async def chat_completion(
        self, 
        messages: List[ChatMessage], 
        user_context: UserContext,
        session_id: str
    ) -> str:
        """Get a chat completion from the Agent Engine using session-based API."""
        if not self.reasoning_engine:
            return "I'm sorry, but I'm unable to process your request at the moment. Please try again later."
        
        try:
            # Get the latest message
            latest_message = messages[-1] if messages else None
            if not latest_message:
                return "I didn't receive any message to process."
            
            user_input = latest_message.content
            user_id = user_context.user_id
            
            # Get or create session for this user
            actual_session_id = self.get_or_create_session(user_id, session_id)
            
            logger.info(f"Sending query to Agent Engine for user {user_id}, session {actual_session_id}")
            logger.info(f"Query: {user_input[:100]}...")
            
            # Use stream_query and collect all events for non-streaming response
            response_parts = []
            
            # Check if stream_query method exists, otherwise try other methods
            if hasattr(self.reasoning_engine, 'stream_query'):
                try:
                    for event in self.reasoning_engine.stream_query(
                        user_id=user_id,
                        session_id=actual_session_id,
                        message=user_input
                    ):
                        logger.debug(f"Received event: {type(event)} - {str(event)[:200]}...")
                        
                        # Extract content from various event types
                        if hasattr(event, 'content') and event.content:
                            response_parts.append(str(event.content))
                        elif isinstance(event, dict):
                            if 'content' in event:
                                response_parts.append(str(event['content']))
                            elif 'message' in event:
                                response_parts.append(str(event['message']))
                            elif 'text' in event:
                                response_parts.append(str(event['text']))
                        elif isinstance(event, str):
                            response_parts.append(event)
                        else:
                            response_parts.append(str(event))
                except Exception as stream_error:
                    logger.error(f"Error during stream_query: {stream_error}")
                    return f"I encountered an error while processing your request: {str(stream_error)}"
            else:
                logger.warning("stream_query method not available on reasoning engine")
                # Check available methods for debugging
                available_methods = [method for method in dir(self.reasoning_engine) if not method.startswith('_')]
                logger.error(f"Available methods on reasoning engine: {available_methods}")
                return f"I'm unable to process your request. The Agent Engine doesn't have the expected interface. Available methods: {', '.join(available_methods[:5])}..."
            
            # Combine all response parts
            full_response = ''.join(response_parts).strip()
            
            if not full_response:
                logger.warning("Empty response from Agent Engine")
                return "I received your message but couldn't generate a response. Please try rephrasing your question."
            
            logger.info(f"Successfully received response from Agent Engine: {len(full_response)} characters")
            return full_response
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat completion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}"
            )
    
    async def stream_chat_completion(
        self, 
        messages: List[ChatMessage], 
        user_context: UserContext,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion from the Agent Engine using session-based API."""
        if not self.reasoning_engine:
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
            
            # Get or create session for this user
            actual_session_id = self.get_or_create_session(user_id, session_id)
            
            logger.info(f"Streaming query to Agent Engine for user {user_id}, session {actual_session_id}")
            logger.info(f"Query: {user_input[:100]}...")
            
            # Check if stream_query method exists
            if hasattr(self.reasoning_engine, 'stream_query'):
                try:
                    # Stream events from the Agent Engine
                    for event in self.reasoning_engine.stream_query(
                        user_id=user_id,
                        session_id=actual_session_id,
                        message=user_input
                    ):
                        logger.debug(f"Streaming event: {type(event)} - {str(event)[:200]}...")
                        
                        # Extract content from various event types and yield immediately
                        content_yielded = False
                        
                        if hasattr(event, 'content') and event.content:
                            yield str(event.content)
                            content_yielded = True
                        elif isinstance(event, dict):
                            if 'content' in event and event['content']:
                                yield str(event['content'])
                                content_yielded = True
                            elif 'message' in event and event['message']:
                                yield str(event['message'])
                                content_yielded = True
                            elif 'text' in event and event['text']:
                                yield str(event['text'])
                                content_yielded = True
                            elif 'delta' in event and isinstance(event['delta'], dict):
                                if 'content' in event['delta'] and event['delta']['content']:
                                    yield str(event['delta']['content'])
                                    content_yielded = True
                        elif isinstance(event, str) and event.strip():
                            yield event
                            content_yielded = True
                        
                        # If we couldn't extract meaningful content, yield the raw event as string
                        if not content_yielded and str(event).strip():
                            yield str(event)
                    
                    logger.info("Finished streaming response from Agent Engine")
                    
                except Exception as stream_error:
                    logger.error(f"Error during stream_query: {stream_error}")
                    yield f"Error: Failed to query Agent Engine - {str(stream_error)}"
            else:
                # Fallback: no streaming support
                logger.warning("stream_query method not available, providing error message")
                available_methods = [method for method in dir(self.reasoning_engine) if not method.startswith('_')]
                logger.error(f"Available methods on reasoning engine: {available_methods}")
                yield f"Streaming not supported. The Agent Engine doesn't have the expected interface. Available methods: {', '.join(available_methods[:5])}..."
                    
        except Exception as e:
            logger.error(f"Error in streaming chat completion: {e}")
            yield f"Error: Failed to process chat request - {str(e)}"


# Global client instance
agent_client = AgentEngineClient()


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    user_context: UserContext = Depends(get_current_user)
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
                    session_id=request.session_id
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
                }
            )
        else:
            # Return single response
            response_content = await agent_client.chat_completion(
                messages=request.messages,
                user_context=user_context,
                session_id=request.session_id
            )
            
            return ChatResponse(
                content=response_content,
                session_id=request.session_id
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
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
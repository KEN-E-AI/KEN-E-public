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
from vertexai import agent_engines
from typing import Any, Dict, List, AsyncGenerator, Union

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
    """Client for interacting with Vertex AI Agent Engine using agent_engines API."""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
        
        if not self.agent_engine_id:
            logger.warning("VERTEX_AI_AGENT_ENGINE_ID not set. Chat functionality will be limited.")
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        
        self._agent_engine: Any = None
        self._user_sessions = {}  # Cache for user sessions
    
    @property
    def agent_engine(self):
        """Lazy-load the agent engine using agent_engines.get()."""
        if self._agent_engine is None and self.agent_engine_id:
            try:
                logger.info(f"Attempting to connect to Agent Engine: {self.agent_engine_id}")
                logger.info(f"Using project: {self.project_id}, location: {self.location}")
                
                # Use agent_engines.get() to get the deployed agent engine
                self._agent_engine = agent_engines.get(self.agent_engine_id)
                
                # Log the available methods for debugging
                available_methods = [method for method in dir(self._agent_engine) if not method.startswith('_')]
                logger.info(f"Available methods on agent engine: {available_methods}")
                
                logger.info(f"Successfully connected to Agent Engine: {self.agent_engine_id}")
            except Exception as e:
                logger.error(f"Failed to connect to Agent Engine: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Agent Engine is currently unavailable: {str(e)}"
                )
        return self._agent_engine
    
    def get_or_create_session(self, user_id: str, session_id: str) -> str:
        """Get or create a session for a user."""
        session_key = f"{user_id}:{session_id}"
        
        if session_key not in self._user_sessions:
            try:
                logger.info(f"Creating new session for user {user_id}")
                # Try to create an ADK session if the method exists
                if hasattr(self.agent_engine, 'create_session'):
                    session_response = self.agent_engine.create_session(user_id=user_id)
                    
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
        """Get a chat completion from the Agent Engine using agent_engines API."""
        if not self.agent_engine:
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
            
            # Use the agent_engines API with proper Queryable interface
            try:
                # Log available methods for debugging
                available_methods = [method for method in dir(self.agent_engine) if not method.startswith('_')]
                logger.info(f"Available methods on agent engine: {available_methods}")
                
                # Try the agent_engines query patterns
                response = None
                
                # Pattern 1: query method (from Queryable interface)
                if hasattr(self.agent_engine, 'query'):
                    logger.info("Trying query method")
                    response = self.agent_engine.query(user_input)
                
                # Pattern 2: Direct callable
                elif hasattr(self.agent_engine, '__call__'):
                    logger.info("Trying direct call pattern")
                    response = self.agent_engine(user_input)
                    
                # Pattern 3: run method
                elif hasattr(self.agent_engine, 'run'):
                    logger.info("Trying run method")
                    response = self.agent_engine.run(user_input)
                    
                else:
                    return f"Unable to find a valid query method on the Agent Engine. Available methods: {', '.join(available_methods[:10])}"
                
                logger.info(f"Response received: {type(response)}")
                
                # Process the response
                if isinstance(response, str):
                    return response
                elif hasattr(response, 'content'):
                    return str(response.content)
                elif hasattr(response, 'text'):
                    return str(response.text)
                elif isinstance(response, dict):
                    if 'content' in response:
                        return str(response['content'])
                    elif 'text' in response:
                        return str(response['text'])
                    elif 'message' in response:
                        return str(response['message'])
                    else:
                        return str(response)
                else:
                    return str(response)
                    
            except Exception as call_error:
                logger.error(f"Error calling Agent Engine: {call_error}")
                return f"Error processing your request: {str(call_error)}"
                
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
            
            # Get or create session for this user
            actual_session_id = self.get_or_create_session(user_id, session_id)
            
            logger.info(f"Streaming query to Agent Engine for user {user_id}, session {actual_session_id}")
            logger.info(f"Query: {user_input[:100]}...")
            
            # Try streaming with agent_engines API
            try:
                # Log available methods for debugging
                available_methods = [method for method in dir(self.agent_engine) if not method.startswith('_')]
                logger.info(f"Available methods on agent engine: {available_methods}")
                
                # Pattern 1: stream method (from StreamQueryable interface)
                if hasattr(self.agent_engine, 'stream'):
                    logger.info("Trying stream method")
                    for chunk in self.agent_engine.stream(user_input):
                        if isinstance(chunk, str):
                            yield chunk
                        elif hasattr(chunk, 'content'):
                            yield str(chunk.content)
                        elif isinstance(chunk, dict) and 'content' in chunk:
                            yield str(chunk['content'])
                        else:
                            yield str(chunk)
                    return
                
                # Pattern 2: stream_query method
                elif hasattr(self.agent_engine, 'stream_query'):
                    logger.info("Trying stream_query method")
                    for chunk in self.agent_engine.stream_query(user_input):
                        if isinstance(chunk, str):
                            yield chunk
                        elif hasattr(chunk, 'content'):
                            yield str(chunk.content)
                        elif isinstance(chunk, dict) and 'content' in chunk:
                            yield str(chunk['content'])
                        else:
                            yield str(chunk)
                    return
                
                # Fallback: use regular query and yield the result
                response = None
                
                # Pattern 3: query method
                if hasattr(self.agent_engine, 'query'):
                    logger.info("Trying query method for streaming fallback")
                    response = self.agent_engine.query(user_input)
                
                # Pattern 4: Direct callable
                elif hasattr(self.agent_engine, '__call__'):
                    logger.info("Trying direct call pattern for streaming fallback")
                    response = self.agent_engine(user_input)
                    
                else:
                    yield f"Unable to find a valid query method on the Agent Engine. Available methods: {', '.join(available_methods[:10])}"
                    return
                
                logger.info(f"Streaming response received: {type(response)}")
                
                # Process and yield the response
                if isinstance(response, str):
                    yield response
                elif hasattr(response, 'content'):
                    yield str(response.content)
                elif hasattr(response, 'text'):
                    yield str(response.text)
                elif isinstance(response, dict):
                    if 'content' in response:
                        yield str(response['content'])
                    elif 'text' in response:
                        yield str(response['text'])
                    elif 'message' in response:
                        yield str(response['message'])
                    else:
                        yield str(response)
                else:
                    yield str(response)
                    
            except Exception as call_error:
                logger.error(f"Error calling Agent Engine for streaming: {call_error}")
                yield f"Error processing your request: {str(call_error)}"
                    
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
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
    timestamp: str = Field(None, description="Message timestamp")


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
    """Client for interacting with Vertex AI Agent Engine."""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
        
        if not self.agent_engine_id:
            logger.warning("VERTEX_AI_AGENT_ENGINE_ID not set. Chat functionality will be limited.")
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        
        self._reasoning_engine = None
    
    @property
    def reasoning_engine(self):
        """Lazy-load the reasoning engine."""
        if self._reasoning_engine is None and self.agent_engine_id:
            try:
                self._reasoning_engine = reasoning_engines.ReasoningEngine(
                    self.agent_engine_id
                )
                logger.info(f"Connected to Agent Engine: {self.agent_engine_id}")
            except Exception as e:
                logger.error(f"Failed to connect to Agent Engine: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Agent Engine is currently unavailable"
                )
        return self._reasoning_engine
    
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
        """Get a chat completion from the Agent Engine."""
        if not self.reasoning_engine:
            # Fallback response when Agent Engine is not available
            return "I'm sorry, but I'm unable to process your request at the moment. Please try again later."
        
        try:
            # Format input for the agent
            agent_input = self.format_messages_for_agent(messages)
            
            # Add user context for personalization
            config = {
                "metadata": {
                    "user_id": user_context.user_id,
                    "session_id": session_id,
                    "email": user_context.email,
                }
            }
            
            # Call the reasoning engine
            response = self.reasoning_engine.query(
                input=agent_input,
                config=config
            )
            
            # Extract the response content
            if isinstance(response, dict) and "content" in response:
                return response["content"]
            elif isinstance(response, str):
                return response
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                return str(response)
                
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process chat request"
            )
    
    async def stream_chat_completion(
        self, 
        messages: List[ChatMessage], 
        user_context: UserContext,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion from the Agent Engine."""
        if not self.reasoning_engine:
            yield "I'm sorry, but I'm unable to process your request at the moment. Please try again later."
            return
        
        try:
            # Format input for the agent
            agent_input = self.format_messages_for_agent(messages)
            
            # Add user context for personalization
            config = {
                "metadata": {
                    "user_id": user_context.user_id,
                    "session_id": session_id,
                    "email": user_context.email,
                }
            }
            
            # Stream from the reasoning engine
            for chunk in self.reasoning_engine.stream_query(
                input=agent_input,
                config=config
            ):
                if isinstance(chunk, dict):
                    # Extract content from chunk
                    if "content" in chunk:
                        yield chunk["content"]
                    elif "delta" in chunk and "content" in chunk["delta"]:
                        yield chunk["delta"]["content"]
                elif isinstance(chunk, str):
                    yield chunk
                    
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
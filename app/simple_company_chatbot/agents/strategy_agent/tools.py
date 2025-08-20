"""
Tools for the strategy agent.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

import vertexai
from vertexai.preview import caching
from vertexai.preview.generative_models import Tool
from google.cloud import discoveryengine_v1 as discoveryengine

from models import StrategyDocument, ReviewFeedback

logger = logging.getLogger(__name__)


class StrategyTools:
    """Tools for strategy document creation and refinement."""
    
    def __init__(self, project_id: str = None, location: str = "us-central1"):
        """Initialize strategy tools."""
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = location
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        
        # Initialize Discovery Engine client for Vertex AI Search
        self.search_client = None
        self._init_search_client()
    
    def _init_search_client(self):
        """Initialize Vertex AI Search client if configured."""
        search_engine_id = os.getenv("VERTEX_AI_SEARCH_ENGINE_ID")
        if search_engine_id:
            try:
                self.search_client = discoveryengine.SearchServiceClient()
                self.search_engine_path = f"projects/{self.project_id}/locations/us-central1/dataStores/{search_engine_id}/servingConfigs/default_search"
                logger.info("Vertex AI Search client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Vertex AI Search: {e}")
    
    def google_search(self, query: str, num_results: int = 5) -> str:
        """
        Search Google for information relevant to strategy creation.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Formatted search results as a string
        """
        try:
            # For now, return a placeholder - in production, integrate with Google Search API
            # You would use the Google Custom Search API or similar service
            return f"[Google Search Results for: {query}]\n\nNote: Google Search integration pending. Using knowledge base for strategy creation."
        except Exception as e:
            logger.error(f"Google search error: {e}")
            return f"Search unavailable, using knowledge base: {str(e)}"
    
    def vertex_ai_search(self, query: str, filter_expression: Optional[str] = None) -> str:
        """
        Search internal knowledge base using Vertex AI Search.
        
        Args:
            query: Search query
            filter_expression: Optional filter for search results
            
        Returns:
            Formatted search results as a string
        """
        if not self.search_client:
            return "Vertex AI Search not configured. Using general knowledge."
        
        try:
            # Create search request
            request = discoveryengine.SearchRequest(
                serving_config=self.search_engine_path,
                query=query,
                page_size=5,
                query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                    condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO
                ),
                spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                    mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
                ),
            )
            
            if filter_expression:
                request.filter = filter_expression
            
            # Execute search
            response = self.search_client.search(request=request)
            
            # Format results
            results = []
            for result in response.results:
                doc = result.document
                results.append({
                    "title": doc.struct_data.get("title", ""),
                    "snippet": doc.struct_data.get("snippet", ""),
                    "url": doc.struct_data.get("url", ""),
                })
            
            if results:
                formatted = "\n\n".join([
                    f"**{r['title']}**\n{r['snippet']}\nSource: {r['url']}"
                    for r in results
                ])
                return f"[Vertex AI Search Results]\n\n{formatted}"
            else:
                return "No relevant documents found in knowledge base."
                
        except Exception as e:
            logger.error(f"Vertex AI Search error: {e}")
            return f"Search error, using general knowledge: {str(e)}"
    
    def save_strategy_document(
        self, 
        document: StrategyDocument, 
        account_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Save strategy document to Firestore.
        
        Args:
            document: Strategy document to save
            account_id: Account ID for scoping
            user_id: User ID for attribution
            
        Returns:
            Success response with document ID
        """
        try:
            # In production, this would save to Firestore
            # For now, return success response
            doc_id = f"{document.doc_type}_{datetime.utcnow().isoformat()}"
            
            logger.info(f"Saving strategy document: {doc_id} for account: {account_id}")
            
            return {
                "success": True,
                "document_id": doc_id,
                "message": f"Strategy document saved successfully",
                "account_id": account_id,
                "user_id": user_id
            }
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def load_strategy_document(
        self,
        doc_type: str,
        account_id: str
    ) -> Optional[StrategyDocument]:
        """
        Load existing strategy document from Firestore.
        
        Args:
            doc_type: Type of strategy document
            account_id: Account ID for scoping
            
        Returns:
            Existing document or None if not found
        """
        try:
            # In production, this would load from Firestore
            # For now, return None to indicate no existing document
            logger.info(f"Checking for existing {doc_type} for account: {account_id}")
            return None
        except Exception as e:
            logger.error(f"Error loading document: {e}")
            return None
    
    def exit_loop(self, final_document: StrategyDocument, reason: str = "approved") -> Dict[str, Any]:
        """
        Exit the refinement loop when document is ready.
        
        Args:
            final_document: The final approved document
            reason: Reason for exiting (approved, max_iterations, user_request)
            
        Returns:
            Exit status with final document
        """
        return {
            "exit": True,
            "reason": reason,
            "final_document": final_document.model_dump(),
            "message": f"Strategy document {reason}. Refinement loop complete."
        }


def create_strategy_tools() -> StrategyTools:
    """Create and return strategy tools instance."""
    return StrategyTools()
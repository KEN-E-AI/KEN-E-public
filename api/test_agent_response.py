#!/usr/bin/env python3
"""
Test script to see what response we get from the Agent Engine.
Now also tests if Firestore permissions work.
"""

import asyncio
import os
import logging
from vertexai import agent_engines
import vertexai
from google.cloud import firestore
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_response():
    """Test what we actually get back from the Agent Engine and if Firestore works."""
    
    # Test account details
    test_account_id = f"acc_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_company = "TestCompany"
    
    logger.info(f"Testing with account ID: {test_account_id}")
    
    # Get environment variables
    project_id = os.getenv("VERTEX_AI_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev"))
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    agent_engine_id = os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
    
    if not agent_engine_id:
        logger.error("VERTEX_AI_AGENT_ENGINE_ID not set")
        return
    
    # Initialize Vertex AI
    vertexai.init(project=project_id, location=location)
    
    # Get the agent engine
    logger.info(f"Getting agent engine: {agent_engine_id}")
    agent_engine = agent_engines.get(agent_engine_id)
    
    # Test message with account ID for Firestore saving
    test_message = f"""Generate all 5 strategy documents for {test_company}

NEW INFORMATION:
Project ID: {project_id}
Account ID: {test_account_id}
Company to analyze: {test_company}
Company websites: ['https://testcompany.com']
Industry: Technology
Customer regions: US, Europe
Annual advertising budget: $100000"""
    
    logger.info("Calling agent engine...")
    
    try:
        # Call the agent
        response = agent_engine.stream_query(
            message=test_message,
            user_id="test_user"
        )
        
        # Collect response
        chunks_received = 0
        total_text = []
        
        for chunk in response:
            chunks_received += 1
            logger.info(f"Chunk {chunks_received} type: {type(chunk)}")
            
            if isinstance(chunk, dict):
                logger.info(f"  Keys: {list(chunk.keys())}")
                
                # Try to extract text
                if 'content' in chunk and isinstance(chunk['content'], dict):
                    content = chunk['content']
                    if 'parts' in content and isinstance(content['parts'], list):
                        for part in content['parts']:
                            if isinstance(part, dict) and 'text' in part:
                                text = part['text']
                                total_text.append(text)
                                logger.info(f"  Found text: {len(text)} chars")
                                logger.info(f"  Preview: {text[:200]}...")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Total chunks received: {chunks_received}")
        logger.info(f"Total text collected: {len(''.join(total_text))} chars")
        
        if total_text:
            full_response = ''.join(total_text)
            logger.info(f"\nFull response preview (first 500 chars):")
            logger.info(full_response[:500])
        else:
            logger.warning("No text content found in response")
        
        # Check if documents were saved to Firestore
        logger.info(f"\n{'='*60}")
        logger.info("Checking Firestore for saved documents...")
        
        db = firestore.Client(project=project_id)
        collection_name = f"strategy_docs_{test_account_id}"
        
        # Wait a moment for documents to be saved
        await asyncio.sleep(5)
        
        # Check for documents
        docs = db.collection(collection_name).get()
        
        if docs:
            logger.info(f"✅ Found {len(docs)} documents in Firestore:")
            for doc in docs:
                doc_data = doc.to_dict()
                logger.info(f"  - {doc.id}:")
                if 'content' in doc_data:
                    content = doc_data['content']
                    if isinstance(content, dict):
                        logger.info(f"    Content keys: {list(content.keys())[:5]}...")
                        logger.info(f"    Content size: {len(json.dumps(content))} bytes")
                if 'created_at' in doc_data:
                    logger.info(f"    Created: {doc_data['created_at']}")
        else:
            logger.warning(f"❌ No documents found in collection {collection_name}")
            logger.info("The Agent Engine might still not be able to write to Firestore")
            
    except Exception as e:
        logger.error(f"Error calling agent engine: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_agent_response())
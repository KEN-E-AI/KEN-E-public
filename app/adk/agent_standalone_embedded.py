#!/usr/bin/env python3
"""
Standalone Multi-Agent Supervisor V3 with Embedded Strategy Agents
This version embeds all strategy agent code directly to ensure proper deployment.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, List
import concurrent.futures
import uuid
import json
import re
from datetime import datetime
from dataclasses import dataclass, field

from google.adk.agents import Agent, SequentialAgent, AgentTool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part
from google.genai import types
from vertexai.preview import reasoning_engines

try:
    import weave
except ImportError:
    weave = None  # type: ignore[assignment]

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# EMBEDDED STRATEGY AGENT CODE
# ============================================================================

@dataclass
class StrategyContext:
    """Context for strategy generation passed between agents."""
    company_name: str
    industry: str
    websites: List[str]
    customer_regions: List[str]
    account_id: str
    user_id: str
    annual_ad_budget: Optional[float] = None
    project_id: str = "ken-e-dev"
    
    # Agent outputs stored here
    business_strategy: Optional[Dict] = None
    competitive_strategy: Optional[Dict] = None
    customer_strategy: Optional[Dict] = None
    marketing_strategy: Optional[Dict] = None
    brand_guidelines: Optional[Dict] = None
    
    # Track which agents have completed
    completed_agents: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "company_name": self.company_name,
            "industry": self.industry,
            "websites": self.websites,
            "customer_regions": self.customer_regions,
            "account_id": self.account_id,
            "user_id": self.user_id,
            "annual_ad_budget": self.annual_ad_budget,
            "project_id": self.project_id,
            "business_strategy": self.business_strategy,
            "competitive_strategy": self.competitive_strategy,
            "customer_strategy": self.customer_strategy,
            "marketing_strategy": self.marketing_strategy,
            "brand_guidelines": self.brand_guidelines,
            "completed_agents": self.completed_agents
        }


def create_google_search_agent() -> Agent:
    """Create a simple Google search agent."""
    return Agent(
        name="google_search",
        model="gemini-2.5-pro",
        tools=["google_search"],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        )
    )


def create_business_strategy_agent() -> Agent:
    """Create the business strategist agent with gemini-2.5-pro."""
    google_search_agent = create_google_search_agent()
    
    instruction = """You are a strategic business expert creating comprehensive business strategy documents.
    
    Analyze the company and create a detailed business strategy document with these sections:
    
    1. Executive Summary
    2. Business Model Analysis  
    3. Value Proposition
    4. Revenue Streams
    5. Cost Structure
    6. Key Resources and Capabilities
    7. Strategic Partnerships
    8. Growth Opportunities
    9. Risk Assessment
    10. Strategic Recommendations
    
    Use web search to gather relevant information about the company and industry.
    Provide specific, actionable insights tailored to the company's context."""
    
    return Agent(
        name="business_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Strategic business expert that creates comprehensive business strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="business_strategy_doc"
    )


def create_competitive_strategy_agent() -> Agent:
    """Create the competitive strategist agent with gemini-2.5-pro."""
    google_search_agent = create_google_search_agent()
    
    instruction = """You are a competitive intelligence expert creating detailed competitive analysis documents.
    
    Analyze the competitive landscape and create a comprehensive document with:
    
    1. Market Overview
    2. Key Competitors Analysis
    3. Competitive Positioning Matrix
    4. SWOT Analysis
    5. Market Share Analysis
    6. Competitive Advantages
    7. Threat Assessment  
    8. Opportunity Identification
    9. Competitive Response Strategies
    10. Strategic Recommendations
    
    Use web search to identify and analyze key competitors.
    Provide specific insights on how to compete effectively."""
    
    return Agent(
        name="competitive_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Competitive intelligence expert that creates detailed competitive analysis",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="competitive_strategy_doc"
    )


def create_customer_strategy_agent() -> Agent:
    """Create the customer strategist agent with gemini-2.5-pro."""
    google_search_agent = create_google_search_agent()
    
    instruction = """You are a customer insights expert creating comprehensive customer strategy documents.
    
    Analyze the target customers and create a detailed document with:
    
    1. Customer Segmentation
    2. Buyer Personas
    3. Customer Journey Mapping
    4. Pain Points Analysis
    5. Needs and Preferences
    6. Behavioral Insights
    7. Customer Lifetime Value
    8. Retention Strategies
    9. Acquisition Channels
    10. Customer Experience Recommendations
    
    Use web search to understand customer demographics and behaviors.
    Provide actionable insights for customer engagement."""
    
    return Agent(
        name="customer_strategist", 
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Customer insights expert that creates detailed customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="customer_strategy_doc"
    )


def create_marketing_strategy_agent() -> Agent:
    """Create the marketing strategist agent with gemini-2.5-pro."""
    google_search_agent = create_google_search_agent()
    
    instruction = """You are a marketing strategy expert creating comprehensive marketing strategy documents.
    
    Create a detailed marketing strategy document with:
    
    1. Marketing Objectives
    2. Target Audience Definition
    3. Positioning Strategy
    4. Marketing Mix (4Ps)
    5. Channel Strategy
    6. Content Strategy
    7. Campaign Planning
    8. Budget Allocation
    9. KPIs and Metrics
    10. Implementation Roadmap
    
    Use web search to understand market trends and best practices.
    Provide specific, actionable marketing recommendations."""
    
    return Agent(
        name="marketing_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Marketing strategy expert that creates comprehensive marketing plans",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="marketing_strategy_doc"
    )


def create_brand_guidelines_agent() -> Agent:
    """Create the brand guidelines agent with gemini-2.5-pro."""
    google_search_agent = create_google_search_agent()
    
    instruction = """You are a brand strategy expert creating comprehensive brand guidelines documents.
    
    Create detailed brand guidelines with:
    
    1. Brand Mission and Vision
    2. Brand Values
    3. Brand Personality
    4. Voice and Tone Guidelines
    5. Visual Identity Principles
    6. Messaging Framework
    7. Brand Architecture
    8. Usage Guidelines
    9. Brand Experience Principles
    10. Brand Governance
    
    Use web search to understand the company's current brand presence.
    Provide clear, actionable brand guidelines."""
    
    return Agent(
        name="brand_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Brand strategy expert that creates comprehensive brand guidelines",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="brand_guidelines_doc"
    )


def save_strategy_to_firestore(
    context: StrategyContext,
    doc_type: str,
    content: Dict[str, Any]
) -> bool:
    """Save a strategy document to Firestore."""
    try:
        from google.cloud import firestore
        
        db = firestore.Client(project=context.project_id)
        collection_name = f"strategy_docs_{context.account_id}"
        
        doc_data = {
            "content": content,
            "metadata": {
                "company_name": context.company_name,
                "industry": context.industry,
                "created_at": datetime.utcnow().isoformat(),
                "account_id": context.account_id,
                "user_id": context.user_id,
                "doc_type": doc_type
            },
            "status": "completed",
            "version": 1
        }
        
        doc_ref = db.collection(collection_name).document(doc_type)
        doc_ref.set(doc_data)
        
        logger.info(f"Saved {doc_type} to Firestore collection {collection_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save {doc_type} to Firestore: {e}")
        return False


# ============================================================================
# SUPERVISOR IMPLEMENTATION
# ============================================================================

def extract_tenant_context(input_data: Any) -> Tuple[Optional[str], Optional[str], str]:
    """Extract tenant context from various input formats."""
    tenant_id = None
    tenant_credentials = None
    message = ""
    
    if isinstance(input_data, str):
        message = input_data
    elif isinstance(input_data, dict):
        message = input_data.get('message', input_data.get('query', str(input_data)))
        tenant_id = input_data.get('tenant_id')
        tenant_credentials = input_data.get('tenant_credentials')
    else:
        message = str(input_data)
    
    return tenant_id, tenant_credentials, message


def invoke_agent_sync(
    agent: Agent, 
    query: str, 
    user_id: str = None, 
    session_id: str = None
) -> str:
    """Synchronous wrapper for agent invocation with proper async handling."""
    if user_id is None:
        user_id = f"supervisor_user_{uuid.uuid4().hex[:8]}"
    if session_id is None:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    async def invoke_agent():
        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()
        
        runner = Runner(
            agent=agent,
            app_name=agent.name,
            session_service=session_service,
            artifact_service=artifact_service
        )
        
        await session_service.create_session(
            app_name=agent.name,
            user_id=user_id,
            session_id=session_id
        )
        
        user_message = Content(
            role="user",
            parts=[Part.from_text(text=query)]
        )
        
        response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            if event.content and event.content.parts:
                if text := ''.join(part.text or '' for part in event.content.parts):
                    response_text += text
        
        return response_text
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            executor_cls = weave.ThreadPoolExecutor if weave is not None else concurrent.futures.ThreadPoolExecutor
            with executor_cls() as executor:
                future = executor.submit(asyncio.run, invoke_agent())
                return future.result(timeout=300)
        else:
            return loop.run_until_complete(invoke_agent())
    except Exception as e:
        logger.error(f"Error in sync agent invocation: {str(e)}")
        return f"Error invoking agent: {str(e)}"


def dispatch_to_create_strategy(query: str, tenant_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dispatch strategy creation queries to the embedded strategy agents.
    """
    try:
        logger.info("🔄 Routing to embedded strategy generation agents...")
        
        # Parse the query to extract parameters
        context = parse_strategy_context(query)
        
        if not context:
            return {
                "success": False,
                "error": "Could not parse strategy generation parameters",
                "output": "Please provide all required parameters for strategy generation."
            }
        
        logger.info(f"Creating strategy for {context.company_name} (account: {context.account_id})")
        
        # Create strategy agents
        agents = {
            "business_strategy": create_business_strategy_agent(),
            "competitive_strategy": create_competitive_strategy_agent(),
            "customer_strategy": create_customer_strategy_agent(),
            "marketing_strategy": create_marketing_strategy_agent(),
            "brand_guidelines": create_brand_guidelines_agent()
        }
        
        results = {}
        errors = []
        
        # Generate each strategy document
        for doc_type, agent in agents.items():
            try:
                logger.info(f"Generating {doc_type}...")
                
                # Prepare the query for the agent
                agent_query = f"""
                Company: {context.company_name}
                Industry: {context.industry}
                Websites: {', '.join(context.websites)}
                Customer Regions: {', '.join(context.customer_regions)}
                Annual Ad Budget: ${context.annual_ad_budget:,.0f} if context.annual_ad_budget else 'Not specified'
                
                Create a comprehensive {doc_type.replace('_', ' ')} document for this company.
                """
                
                # Invoke the agent
                result = invoke_agent_sync(
                    agent,
                    agent_query,
                    user_id=context.user_id,
                    session_id=f"strategy_{context.account_id}_{doc_type}"
                )
                
                if result and not result.startswith("Error"):
                    # Parse the result into structured format
                    doc_content = {
                        "title": f"{doc_type.replace('_', ' ').title()} for {context.company_name}",
                        "content": result,
                        "generated_at": datetime.utcnow().isoformat()
                    }
                    
                    # Save to Firestore
                    if save_strategy_to_firestore(context, doc_type, doc_content):
                        results[doc_type] = "✅ Generated and saved"
                        logger.info(f"✅ Successfully generated {doc_type}")
                    else:
                        results[doc_type] = "⚠️ Generated but failed to save"
                        errors.append(f"Failed to save {doc_type}")
                else:
                    results[doc_type] = f"❌ Failed: {result[:100]}"
                    errors.append(f"{doc_type}: {result}")
                    logger.error(f"Failed to generate {doc_type}: {result}")
                    
            except Exception as e:
                results[doc_type] = f"❌ Error: {str(e)}"
                errors.append(f"{doc_type}: {str(e)}")
                logger.error(f"Error generating {doc_type}: {e}")
        
        # Prepare response
        success = len(errors) == 0
        
        if success:
            output = f"""
✅ Successfully generated all 5 strategy documents for {context.company_name}!

Documents created:
- Business Strategy
- Competitive Strategy  
- Customer Strategy
- Marketing Strategy
- Brand Guidelines

All documents have been saved to account {context.account_id}.
"""
        else:
            output = f"""
⚠️ Partially completed strategy generation for {context.company_name}.

Results:
{chr(10).join(f"- {k}: {v}" for k, v in results.items())}

{"Errors: " + '; '.join(errors) if errors else ""}
"""
        
        return {
            "success": success,
            "output": output,
            "results": results,
            "errors": errors,
            "account_id": context.account_id
        }
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {e}")
        return {
            "success": False,
            "error": str(e),
            "output": f"Failed to generate strategy documents: {str(e)}"
        }


def parse_strategy_context(query: str) -> Optional[StrategyContext]:
    """Parse strategy generation parameters from query."""
    try:
        # Try to extract parameters from formatted query
        params = {}
        
        # Extract company_name
        if match := re.search(r'company_name:\s*([^\n,]+)', query):
            params['company_name'] = match.group(1).strip()
        elif match := re.search(r'for\s+(\w+[\w\s]*?)[\n,]', query):
            params['company_name'] = match.group(1).strip()
        
        # Extract other parameters
        if match := re.search(r'industry:\s*([^\n,]+)', query):
            params['industry'] = match.group(1).strip()
        
        if match := re.search(r'websites?:\s*([^\n]+)', query):
            websites = match.group(1).strip()
            params['websites'] = [w.strip() for w in websites.split(',')]
        
        if match := re.search(r'customer_regions?:\s*([^\n]+)', query):
            regions = match.group(1).strip()
            params['customer_regions'] = [r.strip() for r in regions.split(',')]
        
        if match := re.search(r'account_id:\s*([^\n,]+)', query):
            params['account_id'] = match.group(1).strip()
        
        if match := re.search(r'user_id:\s*([^\n,]+)', query):
            params['user_id'] = match.group(1).strip()
        
        if match := re.search(r'annual_ad_budget:\s*(\d+)', query):
            params['annual_ad_budget'] = float(match.group(1))
        
        if match := re.search(r'project_id:\s*([^\n,]+)', query):
            params['project_id'] = match.group(1).strip()
        
        # Check if we have minimum required fields
        if 'company_name' in params and 'account_id' in params:
            # Set defaults for missing fields
            params.setdefault('industry', 'General')
            params.setdefault('websites', [])
            params.setdefault('customer_regions', ['US'])
            params.setdefault('user_id', 'system')
            params.setdefault('project_id', 'ken-e-dev')
            
            return StrategyContext(**params)
        
        logger.warning(f"Could not parse required fields from query: {query[:200]}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing strategy context: {e}")
        return None


def route_query(query: str, tenant_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Route queries to appropriate handlers."""
    
    query_lower = query.lower()
    
    # Check for strategy generation requests
    if any(keyword in query_lower for keyword in [
        'generate all 5 strategy',
        'create strategy doc',
        'strategy generation',
        'execute strategy generation'
    ]):
        return dispatch_to_create_strategy(query, tenant_context)
    
    # Default response for other queries
    return {
        "success": True,
        "output": f"Received query: {query[:100]}... (No specific handler for this query type)"
    }


# ============================================================================
# MAIN APP FOR DEPLOYMENT
# ============================================================================

def app(
    query: str,
    tenant_context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Main entry point for the supervisor agent with embedded strategy agents.
    """
    try:
        logger.info("=" * 60)
        logger.info("Supervisor V3 with Embedded Strategy Agents invoked")
        logger.info(f"Query length: {len(query)} chars")
        logger.info(f"Query preview: {query[:200]}...")
        
        # Route the query
        result = route_query(query, tenant_context)
        
        if isinstance(result, dict):
            output = result.get("output", "No output generated")
            logger.info(f"Response: {output[:200]}...")
            return output
        else:
            return str(result)
            
    except Exception as e:
        logger.error(f"Error in supervisor: {e}", exc_info=True)
        return f"Error processing request: {str(e)}"


# For local testing
if __name__ == "__main__":
    test_query = """Generate all 5 strategy documents for TestCompany

Please execute strategy generation with these parameters:
- company_name: TestCompany
- industry: Technology
- websites: testcompany.com
- customer_regions: US
- account_id: test_123
- user_id: test_user
- annual_ad_budget: 50000
- project_id: ken-e-dev"""
    
    print("Testing embedded strategy generation...")
    result = app(test_query)
    print(f"Result: {result}")
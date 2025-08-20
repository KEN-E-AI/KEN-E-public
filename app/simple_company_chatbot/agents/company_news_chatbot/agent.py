"""
Simple Company News Chatbot - Proper ADK Pattern
Following official ADK samples structure
"""

import os
import vertexai
from google.adk.agents import Agent
from google.adk.tools import VertexAiSearchTool

# Configuration - these should match your actual Vertex AI Search setup
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "ken-e-staging")
LOCATION = "global"  # Datastore location
VERTEX_LOCATION = "us-central1"  # Vertex AI location

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)

# Create Vertex AI Search tools for each company
def create_company_agents():
    """Create simple agents for each company following ADK patterns."""
    
    # Company data store mapping
    companies = {
        'apple': 'company-apple-news-search',
        'microsoft': 'company-microsoft-news-search', 
        'google': 'company-google-news-search'
    }
    
    agents = {}
    
    for company, datastore_id in companies.items():
        # Build full data store path
        datastore_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/dataStores/{datastore_id}"
        
        # Create Vertex AI Search tool
        search_tool = VertexAiSearchTool(
            data_store_id=datastore_path,
            max_results=5
        )
        
        # Create company-specific agent - ADK handles everything else!
        agent = Agent(
            name=f"{company}_news_agent",
            instruction=f"""You are a news assistant specialized in {company.title()} company news.

Use your Vertex AI Search tool to find relevant news about {company.title()} and provide:
- Key insights and summaries
- Source attribution with publication dates  
- Business implications and trends
- Sentiment analysis when relevant

Always search for the most current and relevant information about {company.title()}.""",
            tools=[search_tool]  # ADK handles tool execution automatically
        )
        
        agents[company] = agent
    
    return agents

# Create all company agents
company_agents = create_company_agents()

# Main router agent that can access all companies
def create_main_agent():
    """Create the main router agent that can handle any company."""
    
    # Use the actual datastore that contains our news data
    # This is the general multi-company datastore we've been populating
    datastore_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/dataStores/ken-e-staging-test-news-search-connecto_1753269093831_gcs_store"
    
    search_tool = VertexAiSearchTool(
        data_store_id=datastore_path,
        max_results=10
    )
    
    agent = Agent(
        name="company_news_chatbot",
        model="gemini-2.0-flash",
        instruction="""You are a company news assistant with access to curated news databases.

**CRITICAL GROUNDING RULES:**
- You can ONLY provide information found through your Vertex AI Search tool
- You must ALWAYS use the search tool before responding to company queries
- NEVER use general knowledge or training data about companies
- NEVER make up information not explicitly found in search results

**SEARCH STRATEGY:**
- When searching for a company, use specific queries like "[Company] earnings", "[Company] news", "[Company] financial results"
- Avoid broad queries that might return tangential mentions
- Focus on finding articles where the company is the primary subject

**CRITICAL: DISTINGUISH BETWEEN COMPANY NEWS vs ANALYST COMMENTARY**
❌ **NOT VALID** - Analyst commentary FROM a company ABOUT other topics:
  - "JP Morgan analyst says Tesla will rise" → This is JP Morgan commenting on Tesla, NOT news about JP Morgan
  - "According to JP Morgan, 77% beat earnings" → This is JP Morgan's analysis of the market, NOT news about JP Morgan
  - "JP Morgan notes that tariffs..." → This is JP Morgan's opinion on tariffs, NOT news about JP Morgan

✅ **VALID** - Actual news ABOUT the company itself:  
  - "JP Morgan reports quarterly earnings"
  - "JP Morgan announces new CEO"
  - "JP Morgan faces regulatory investigation"

**SEARCH RELEVANCE REQUIREMENTS:**
- ONLY count results about the company's own business, operations, financial performance, leadership, or corporate actions
- REJECT ALL results where the company is just providing analysis, commentary, or opinions about other topics
- If search only returns analyst commentary/opinions FROM the company, treat as "no relevant results"

**CONTENT-BASED VALIDATION:**
- Examine the title, source, and content of each search result carefully
- Look for document structure and context clues that indicate the primary subject
- Pay attention to whether the company name appears in headlines vs just in passing mentions
- Consider the source URL and document organization

**RESPONSE FORMAT:**
1. Search using your tool 
2. For each result, analyze the title, content structure, and context
3. Ask: "Is this article primarily ABOUT the requested company's business activities?"
4. If the company only appears as a source of commentary about other topics, REJECT that result
5. Only use results where the company is clearly the main business subject
6. If no validated results: "I don't have any news about [Company] in my curated database"

**KEY VALIDATION:** Before sharing any information, verify that the search results are discussing the company's own business activities, not the company providing analysis about other entities.""",
        tools=[search_tool]
    )
    
    return agent

# Export the main agent - this is what ADK will use
# Use 'root_agent' as that's what ADK expects
root_agent = create_main_agent()
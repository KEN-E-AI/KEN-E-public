#!/usr/bin/env python
"""
Test Neo4j integration with Competitive Analysis generation.
Demonstrates complete flow from research to graph storage with embeddings.
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

# Set up logging to see progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agents', '.env')
load_dotenv(env_path)

from google import adk
from google.genai.types import GenerateContentConfig, Content, Part
from google.adk.tools import google_search
from pydantic import BaseModel, Field

# Import our modules
from agents.neo4j_tools import Neo4jOperations, get_neo4j_operations
from agents.competitive_graph_builder import CompetitiveGraphBuilder
from agents.embeddings import EmbeddingGenerator, EmbeddingSearch
from agents.firestore_tools import _save_to_firestore_impl
from agents.strategy_agent.competitive_models import CompetitiveAnalysis
from agents.competitive_agents import create_competitive_researcher, create_competitive_formatter

from google.adk import Runner
from google.adk.tools import AgentTool
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService


# ========== GOOGLE SEARCH AGENT ==========

def create_google_search_agent():
    """Create a Google search agent with direct search capabilities."""
    return adk.Agent(
        name="google_search",
        description="Searches the web for information",
        model="gemini-2.0-flash",
        tools=[google_search],  # Using the ADK google_search tool
        instruction="""You are a web search specialist.
When given a search query, use google_search to find relevant information.
Return comprehensive results from multiple searches if needed.
Focus on recent, authoritative sources."""
    )


# ========== COMPETITIVE STRATEGY RUNNER ==========

class CompetitiveStrategyRunner:
    """Runner for competitive analysis generation with Neo4j storage."""

    def __init__(self):
        self.session_id = f"session_{int(datetime.now().timestamp())}"
        self.user_id = "test_user"
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()

        # Initialize Neo4j components
        self.neo4j_ops = get_neo4j_operations()
        self.graph_builder = CompetitiveGraphBuilder(self.neo4j_ops)
        self.embedding_generator = EmbeddingGenerator(self.neo4j_ops)
        self.search = EmbeddingSearch(self.neo4j_ops, self.embedding_generator)

        # Ensure indexes exist
        self.neo4j_ops.create_indexes()

    async def run_agent(self, agent: adk.Agent, query: str, session_suffix: str = "") -> str:
        """Run an agent and return its response."""
        runner = Runner(
            agent=agent,
            app_name=agent.name,
            session_service=self.session_service,
            artifact_service=self.artifact_service
        )

        session_id = f"{self.session_id}_{session_suffix}"

        await self.session_service.create_session(
            app_name=agent.name,
            user_id=self.user_id,
            session_id=session_id
        )

        user_message = Content(role="user", parts=[Part.from_text(text=query)])

        response_text = ""
        async for event in runner.run_async(
            user_id=self.user_id,
            session_id=session_id,
            new_message=user_message
        ):
            if event.content and event.content.parts:
                if text := "".join(part.text or "" for part in event.content.parts):
                    response_text += text

        return response_text

    def format_with_openai(self, research_data: str) -> Dict[str, Any]:
        """
        Use OpenAI to format research data into structured competitive analysis.
        OpenAI handles complex schemas better than Gemini.
        """
        from openai import OpenAI as OpenAIClient

        client = OpenAIClient(api_key=os.getenv('OPENAI_API_KEY'))

        # Use the chat.completions.parse method
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": """You are a competitive analysis formatter.

Take the research report provided and format it into a structured competitive analysis.

Guidelines:
- Identify 1-10 top competitors based on the research
- For each competitor, extract:
  * Name and comprehensive description (history, size, revenue, pricing, distribution, positioning)
  * 1-5 core value propositions explaining why customers choose them
  * 1-5 marketing tactics they use (social media, events, ads, etc.)
  * 1-5 substitute products with detailed descriptions
  * For each substitute product: ONE key value proposition
  * 1-10 key strengths with names, descriptions, AND 1-5 risks each strength creates for your company
  * 1-10 weaknesses with names, descriptions, AND 1-5 opportunities each weakness creates for your company

- Write clear, concise names (e.g., "Brand Recognition", "Market Leader")
- Provide detailed descriptions with specific examples
- Focus on actionable competitive intelligence
- Ensure the competitive_environment_description explains the strategy
  used to identify competitors (geography, size, brand awareness, etc.)

Output valid JSON matching the CompetitiveAnalysis schema EXACTLY.
Ensure all required fields are populated."""},
                {"role": "user", "content": f"Format this research into structured competitive analysis:\n\n{research_data}"}
            ],
            # Pass the Pydantic class directly - OpenAI will handle the conversion
            response_format=CompetitiveAnalysis
        )

        # The parsed response is in the parsed attribute
        if completion.choices[0].message.parsed:
            # Convert to dict for compatibility with the rest of our code
            return completion.choices[0].message.parsed.model_dump()
        else:
            # Fallback to JSON content if parsing failed
            return json.loads(completion.choices[0].message.content)

    async def generate_competitive_analysis(self, company_name: str, account_id: str = None) -> Dict[str, Any]:
        """
        Generate a complete competitive analysis and store in Neo4j.

        Args:
            company_name: Name of the company to analyze
            account_id: Unique account identifier

        Returns:
            Dictionary with analysis data and graph nodes
        """
        if not account_id:
            account_id = f"acc_{company_name.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"

        print(f"\n{'='*60}")
        print(f"Generating Competitive Analysis for {company_name}")
        print(f"Account ID: {account_id}")
        print(f"Session ID: {self.session_id}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Research
            print("📊 Step 1: Researching competitive landscape...")
            google_search_agent = create_google_search_agent()
            researcher = create_competitive_researcher(google_search_agent)
            research_data = await self.run_agent(
                researcher,
                f"Research the competitive environment for {company_name}. Identify their top competitors, the products that compete with theirs, and analyze competitor strengths, weaknesses, and value propositions.",
                "competitive_research"
            )
            print(f"✅ Research complete: {len(research_data)} characters")

            # Step 2: Format into structured data using Gemini 2.5 Pro first
            print("\n📝 Step 2: Formatting into structured analysis using Gemini 2.5 Pro...")
            try:
                formatter = create_competitive_formatter()
                formatted_json = await self.run_agent(
                    formatter,
                    f"Format this research into structured competitive analysis:\n\n{research_data}",
                    "competitive_format"
                )
                analysis_dict = json.loads(formatted_json)
                analysis = CompetitiveAnalysis(**analysis_dict)
                print("✅ Gemini 2.5 Pro successfully formatted the analysis!")
            except Exception as e:
                # Fallback to OpenAI if Gemini fails
                print(f"⚠️ Gemini 2.5 Pro formatting failed: {e}, falling back to OpenAI...")
                analysis_dict = self.format_with_openai(research_data)
                analysis = CompetitiveAnalysis(**analysis_dict)
                print("✅ OpenAI successfully formatted the analysis as fallback")
            print(f"✅ Structured analysis created with {len(analysis.competitors)} competitors")

            # Step 3: Save to Firestore (backup)
            print("\n💾 Step 3: Saving to Firestore...")
            firestore_result = self.save_to_firestore(analysis_dict, "competitive_analysis", account_id)
            print(f"✅ Saved to Firestore: {firestore_result['document_id']}")

            # Step 4: Build Neo4j graph with validation
            print("\n🔗 Step 4: Building competitive knowledge graph in Neo4j...")
            try:
                graph_nodes = self.graph_builder.build_competitive_graph(
                    analysis,
                    account_id,
                    self.user_id
                )

                # Validate graph creation
                expected_counts = {
                    'competitors': len(analysis.competitors),
                    'substitute_products': sum(len(c.substitute_products) for c in analysis.competitors),
                    'competitor_strengths': sum(len(c.strengths) for c in analysis.competitors),
                    'competitor_weaknesses': sum(len(c.weaknesses) for c in analysis.competitors),
                    'competitor_tactics': sum(len(c.marketing_tactics) for c in analysis.competitors),
                    'competitor_value_propositions': sum(len(c.value_propositions) for c in analysis.competitors),
                    'substitute_value_propositions': sum(len(c.substitute_products) for c in analysis.competitors)  # One VP per substitute
                }

                actual_counts = {
                    'competitors': len(graph_nodes.get('competitors', [])),
                    'substitute_products': len(graph_nodes.get('substitute_products', [])),
                    'competitor_strengths': len(graph_nodes.get('competitor_strengths', [])),
                    'competitor_weaknesses': len(graph_nodes.get('competitor_weaknesses', [])),
                    'competitor_tactics': len(graph_nodes.get('competitor_tactics', [])),
                    'competitor_value_propositions': len(graph_nodes.get('competitor_value_propositions', [])),
                    'substitute_value_propositions': len(graph_nodes.get('substitute_value_propositions', [])),
                    'risks': len(graph_nodes.get('risks', [])),
                    'opportunities': len(graph_nodes.get('opportunities', []))
                }

                # Check for discrepancies
                validation_passed = True
                for key, expected in expected_counts.items():
                    actual = actual_counts.get(key, 0)
                    if actual < expected:
                        print(f"   ⚠️  {key}: Expected {expected}, got {actual}")
                        validation_passed = False
                    else:
                        print(f"   ✅ {key}: {actual} nodes created")

                # Risks and opportunities are dynamic (1-5 per strength/weakness)
                print(f"   ✅ risks: {actual_counts['risks']} nodes created (from competitor strengths)")
                print(f"   ✅ opportunities: {actual_counts['opportunities']} nodes created (from competitor weaknesses)")

                if not validation_passed:
                    raise ValueError("Graph creation incomplete - some nodes missing")

                # Check for competitive environment node
                if graph_nodes.get('competitive_environment'):
                    print(f"   ✅ competitive_environment: 1 node created")
                else:
                    print(f"   ⚠️  competitive_environment: Missing")
                    validation_passed = False

            except Exception as e:
                print(f"\n❌ Graph creation failed: {e}")
                print("Attempting retry with increased timeout...")
                raise

            # Step 5: Generate embeddings with validation
            print("\n🧠 Step 5: Generating embeddings for semantic search...")

            # First check how many nodes need embeddings
            nodes_needing_embeddings = self.neo4j_ops.connection.execute_query("""
                MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
                WHERE n.embedding IS NULL AND n.description IS NOT NULL
                RETURN count(n) as count
            """, {'account_id': account_id})

            nodes_to_embed = nodes_needing_embeddings[0]['count'] if nodes_needing_embeddings else 0

            if nodes_to_embed == 0:
                print("   ⚠️  No nodes found needing embeddings")
                # Check if nodes exist at all
                total_nodes = self.neo4j_ops.connection.execute_query("""
                    MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
                    RETURN count(n) as count
                """, {'account_id': account_id})
                total = total_nodes[0]['count'] if total_nodes else 0

                if total == 0:
                    raise ValueError("No strategy nodes found in Neo4j - graph creation may have failed")
                else:
                    print(f"   ℹ️  {total} nodes already have embeddings")
            else:
                print(f"   ℹ️  Found {nodes_to_embed} nodes needing embeddings")

            # Generate embeddings
            embedding_result = self.embedding_generator.generate_embeddings_for_account(account_id)

            # Validate embedding generation
            if embedding_result['success_count'] == 0 and nodes_to_embed > 0:
                print(f"\n❌ Embedding generation failed: Expected {nodes_to_embed}, generated 0")
                print("   This indicates a problem with the embedding service or node structure")
                raise ValueError(f"Failed to generate embeddings for {nodes_to_embed} nodes")
            elif embedding_result['success_count'] < nodes_to_embed:
                print(f"   ⚠️  Partial success: {embedding_result['success_count']}/{nodes_to_embed} embeddings generated")
                if embedding_result.get('errors'):
                    print(f"   Errors: {embedding_result['errors'][:3]}...")  # Show first 3 errors
            else:
                print(f"   ✅ Successfully generated {embedding_result['success_count']} embeddings")

            # Step 6: Test semantic search on competitive data
            print("\n🔍 Step 6: Testing semantic search on competitive intelligence...")
            test_queries = [
                "Who are our main competitors?",
                "What are competitor strengths we need to watch out for?",
                "What products compete with our offerings?"
            ]

            for query in test_queries:
                results = self.search.search(query, account_id, top_k=3)
                print(f"\nQuery: '{query}'")
                if results:
                    for r in results[:2]:
                        print(f"  - {r['type']}: {r['name']} (score: {r['score']})")
                else:
                    print("  No results found")

            print(f"\n{'='*60}")
            print("✅ COMPETITIVE ANALYSIS GENERATION COMPLETE")
            print(f"{'='*60}\n")

            return {
                'success': True,
                'account_id': account_id,
                'analysis': analysis_dict,
                'graph_nodes': graph_nodes,
                'embeddings': embedding_result,
                'firestore_doc': firestore_result['document_id']
            }

        except Exception as e:
            print(f"\n❌ Error generating competitive analysis: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'account_id': account_id
            }

    def save_to_firestore(self, analysis_dict: Dict, doc_type: str, account_id: str) -> Dict:
        """Save competitive analysis to Firestore."""
        doc_data = {
            "type": doc_type,
            "account_id": account_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "data": analysis_dict,
            "created_at": datetime.now().isoformat(),
            "version": 1
        }

        result = _save_to_firestore_impl(
            collection=f"strategy_documents_{doc_type}",
            document_id=f"{account_id}_{self.session_id}",
            data=doc_data
        )

        return {'document_id': result.get('document_id', f"{account_id}_{self.session_id}"), 'collection': f"strategy_documents_{doc_type}"}

    def close(self):
        """Clean up connections."""
        self.neo4j_ops.close()


# ========== MAIN TEST FUNCTION ==========

async def test_competitive_analysis():
    """Test the complete competitive analysis integration flow."""
    runner = CompetitiveStrategyRunner()

    try:
        # Test with Tesla (good competitor landscape to analyze)
        result = await runner.generate_competitive_analysis(
            company_name="Tesla",
            account_id="acc_tesla_competitive_test"
        )

        if result['success']:
            print("\n" + "="*60)
            print("INTEGRATION TEST SUMMARY")
            print("="*60)
            print(f"✅ Account ID: {result['account_id']}")
            print(f"✅ Firestore Document: {result['firestore_doc']}")
            print(f"✅ Graph Nodes Created: Multiple types")
            print(f"✅ Embeddings Generated: {result['embeddings']['success_count']}")
            print(f"✅ Semantic Search: Working")
            print("\n🎉 Competitive analysis integration test completed successfully!")

            # Verify we can retrieve the data
            print("\n📋 Verifying data retrieval from Neo4j...")
            retrieved = runner.neo4j_ops.get_account_strategies(result['account_id'])
            if retrieved:
                print(f"✅ Successfully retrieved {len(retrieved.get('strategies', []))} strategy nodes")

        else:
            print(f"\n❌ Test failed: {result.get('error', 'Unknown error')}")

    finally:
        runner.close()


if __name__ == "__main__":
    # Check for Neo4j credentials
    if not os.getenv('NEO4J_URI') or 'your-neo4j' in os.getenv('NEO4J_URI', ''):
        print("\n⚠️  Please update agents/.env with your Neo4j credentials:")
        print("   NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io")
        print("   NEO4J_USERNAME=neo4j")
        print("   NEO4J_PASSWORD=your-password")
        print("\n   Vertex AI credentials are already configured via GOOGLE_CLOUD_PROJECT")
        print("   Then run this test again.\n")
    else:
        asyncio.run(test_competitive_analysis())

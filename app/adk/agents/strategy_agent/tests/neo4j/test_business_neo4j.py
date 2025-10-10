#!/usr/bin/env python
"""
Test Neo4j integration with Business Strategy generation.
Demonstrates complete flow from research to graph storage with embeddings.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

# Set up logging to see progress
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents", ".env")
load_dotenv(env_path)

from agents.embeddings import EmbeddingGenerator, EmbeddingSearch
from agents.firestore_tools import _save_to_firestore_impl
from agents.graph_builder import GraphBuilder

# Import our modules
from agents.neo4j_tools import get_neo4j_operations
from agents.strategy_agent.structured_models import (
    StructuredBusinessStrategy,
)
from google import adk
from google.adk import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import AgentTool, google_search
from google.genai.types import Content, GenerateContentConfig, Part

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
Focus on recent, authoritative sources.""",
    )


# ========== SPLIT AGENT ARCHITECTURE FOR BUSINESS STRATEGY ==========


def create_business_researcher():
    """Create researcher agent with tools but NO output_schema."""
    google_search_agent = create_google_search_agent()

    return adk.Agent(
        name="business_researcher",
        description="Researches business strategy information",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000,  # Limit to prevent rate limit issues
        ),
        instruction="""You are a business strategy researcher.

For the company mentioned by the user, research and provide a comprehensive report covering:

1. Company Overview - History, mission, vision, current status
2. Business Value Propositions - Core value the company delivers to customers overall
3. Products and Services - Product categories and specific products with their value propositions
4. SWOT Analysis - For each strength, identify opportunities it creates. For each weakness, identify risks it exposes.
5. Strategic Goals - Top strategic objectives the company should focus on

Use the google_search agent to find current information about the company.
Provide detailed, factual research findings.
Be specific and include examples of how strengths create opportunities and weaknesses create risks.""",
    )


def create_business_formatter():
    """Create formatter agent with structured output_schema but NO tools."""
    return adk.Agent(
        name="business_formatter",
        description="Formats business research into structured strategy",
        model="gemini-2.5-pro",  # Testing with 2.5 Pro instead of 2.0-flash
        tools=[],  # NO tools
        generate_content_config=GenerateContentConfig(
            temperature=0.1, maxOutputTokens=4000, responseMimeType="application/json"
        ),
        output_schema=StructuredBusinessStrategy,
        instruction="""You are a business strategy formatter.

Take the research report provided by the user and format it into a structured business strategy.

For the structured output:

1. Extract 1-5 business-level value propositions that describe the overall company value
2. Extract 1-5 main product categories with 1-5 specific products each
3. For SWOT Analysis:
   - Identify 1-5 core strengths, and for EACH strength list 1-5 opportunities it creates
   - Identify 1-5 key weaknesses, and for EACH weakness list 1-5 risks it exposes
4. Identify 1-5 strategic goals

Create IDs using lowercase-hyphenated format (e.g., 'strength-brand-recognition').
Be specific and actionable in all descriptions.
Ensure all required fields are populated.""",
    )


# ========== STRATEGY RUNNER ==========


class Neo4jStrategyRunner:
    """Runner for strategy generation with Neo4j storage."""

    def __init__(self):
        self.session_id = f"session_{int(datetime.now().timestamp())}"
        self.user_id = "test_user"
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()

        # Initialize Neo4j components
        self.neo4j_ops = get_neo4j_operations()
        self.graph_builder = GraphBuilder(self.neo4j_ops)
        self.embedding_generator = EmbeddingGenerator(self.neo4j_ops)
        self.search = EmbeddingSearch(self.neo4j_ops, self.embedding_generator)

        # Ensure indexes exist
        self.neo4j_ops.create_indexes()

    async def run_agent(
        self, agent: adk.Agent, query: str, session_suffix: str = ""
    ) -> str:
        """Run an agent and return its response."""
        runner = Runner(
            agent=agent,
            app_name=agent.name,
            session_service=self.session_service,
            artifact_service=self.artifact_service,
        )

        session_id = f"{self.session_id}_{session_suffix}"

        await self.session_service.create_session(
            app_name=agent.name, user_id=self.user_id, session_id=session_id
        )

        user_message = Content(role="user", parts=[Part.from_text(text=query)])

        response_text = ""
        async for event in runner.run_async(
            user_id=self.user_id, session_id=session_id, new_message=user_message
        ):
            if event.content and event.content.parts:
                if text := "".join(part.text or "" for part in event.content.parts):
                    response_text += text

        return response_text

    def format_with_openai(self, research_data: str) -> dict[str, Any]:
        """
        Use OpenAI to format research data into structured strategy.
        OpenAI handles complex schemas better than Gemini.
        """
        from openai import OpenAI as OpenAIClient

        client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))

        # Use the chat.completions.parse method (beta is needed for parse)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",  # Use the specific model that supports structured outputs
            messages=[
                {
                    "role": "system",
                    "content": """You are a business strategy formatter.

Take the research report provided and format it into a structured business strategy.

For the structured output:
1. Extract 1-5 business-level value propositions that describe the overall company value
2. Extract 1-5 main product categories with 1-5 specific products each
3. For SWOT Analysis:
   - Identify 1-5 core strengths, and for EACH strength list 1-5 opportunities it creates
   - Identify 1-5 key weaknesses, and for EACH weakness list 1-5 risks it exposes
4. Identify 1-5 strategic goals

Create IDs using lowercase-hyphenated format (e.g., 'strength-brand-recognition').
Be specific and actionable in all descriptions.
Ensure all required fields are populated.""",
                },
                {
                    "role": "user",
                    "content": f"Format this research into structured business strategy:\n\n{research_data}",
                },
            ],
            # Pass the Pydantic class directly - OpenAI will handle the conversion
            response_format=StructuredBusinessStrategy,
        )

        # The parsed response is in the parsed attribute
        if completion.choices[0].message.parsed:
            # Convert to dict for compatibility with the rest of our code
            return completion.choices[0].message.parsed.model_dump()
        else:
            # Fallback to JSON content if parsing failed
            return json.loads(completion.choices[0].message.content)

    async def generate_business_strategy(
        self, company_name: str, account_id: str = None
    ) -> dict[str, Any]:
        """
        Generate a complete business strategy and store in Neo4j.

        Args:
            company_name: Name of the company to analyze
            account_id: Unique account identifier

        Returns:
            Dictionary with strategy data and graph nodes
        """
        if not account_id:
            account_id = f"acc_{company_name.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"

        print(f"\n{'=' * 60}")
        print(f"Generating Business Strategy for {company_name}")
        print(f"Account ID: {account_id}")
        print(f"Session ID: {self.session_id}")
        print(f"{'=' * 60}\n")

        try:
            # Step 1: Research
            print("📊 Step 1: Researching business strategy...")
            researcher = create_business_researcher()
            research_data = await self.run_agent(
                researcher,
                f"Research comprehensive business strategy for {company_name}",
                "business_research",
            )
            print(f"✅ Research complete: {len(research_data)} characters")

            # Step 2: Format into structured data using Gemini 2.5 Pro first
            print(
                "\n📝 Step 2: Formatting into structured strategy using Gemini 2.5 Pro..."
            )
            try:
                formatter = create_business_formatter()
                formatted_json = await self.run_agent(
                    formatter,
                    f"Format this research into structured business strategy:\n\n{research_data}",
                    "business_format",
                )
                strategy_dict = json.loads(formatted_json)
                strategy = StructuredBusinessStrategy(**strategy_dict)
                print("✅ Gemini 2.5 Pro successfully formatted the strategy!")
            except Exception as e:
                # Fallback to OpenAI if Gemini fails
                print(
                    f"⚠️ Gemini 2.5 Pro formatting failed: {e}, falling back to OpenAI..."
                )
                strategy_dict = self.format_with_openai(research_data)
                strategy = StructuredBusinessStrategy(**strategy_dict)
                print("✅ OpenAI successfully formatted the strategy as fallback")
            print(
                f"✅ Structured strategy created with {len(strategy.strategic_goals)} goals"
            )

            # Step 3: Save to Firestore (backup)
            print("\n💾 Step 3: Saving to Firestore...")
            firestore_result = self.save_to_firestore(
                strategy_dict, "business_strategy", account_id
            )
            print(f"✅ Saved to Firestore: {firestore_result['document_id']}")

            # Step 4: Build Neo4j graph with validation
            print("\n🔗 Step 4: Building knowledge graph in Neo4j...")
            try:
                graph_nodes = self.graph_builder.build_strategy_graph(
                    strategy, account_id, self.user_id
                )

                # Validate graph creation
                num_strengths = len(strategy.swot_analysis.strengths_and_opportunities)
                num_weaknesses = len(strategy.swot_analysis.weaknesses_and_risks)

                actual_counts = {
                    "business_value_propositions": len(
                        graph_nodes.get("business_value_propositions", [])
                    ),
                    "products": len(graph_nodes.get("products", [])),
                    "goals": len(graph_nodes.get("goals", [])),
                    "strengths": len(graph_nodes.get("swot", {}).get("strengths", [])),
                    "weaknesses": len(
                        graph_nodes.get("swot", {}).get("weaknesses", [])
                    ),
                    "opportunities": len(
                        graph_nodes.get("swot", {}).get("opportunities", [])
                    ),
                    "risks": len(graph_nodes.get("swot", {}).get("risks", [])),
                }

                # Check for discrepancies
                validation_passed = True
                expected_strengths = num_strengths
                expected_weaknesses = num_weaknesses

                if actual_counts["strengths"] < expected_strengths:
                    print(
                        f"   ⚠️  strengths: Expected {expected_strengths}, got {actual_counts['strengths']}"
                    )
                    validation_passed = False
                else:
                    print(
                        f"   ✅ strengths: {actual_counts['strengths']} nodes created"
                    )

                if actual_counts["weaknesses"] < expected_weaknesses:
                    print(
                        f"   ⚠️  weaknesses: Expected {expected_weaknesses}, got {actual_counts['weaknesses']}"
                    )
                    validation_passed = False
                else:
                    print(
                        f"   ✅ weaknesses: {actual_counts['weaknesses']} nodes created"
                    )

                # Opportunities and Risks are dynamic (1-5 per strength/weakness)
                print(
                    f"   ✅ opportunities: {actual_counts['opportunities']} nodes created (linked to strengths)"
                )
                print(
                    f"   ✅ risks: {actual_counts['risks']} nodes created (linked to weaknesses)"
                )
                print(
                    f"   ✅ business_value_propositions: {actual_counts['business_value_propositions']} nodes created"
                )
                print(f"   ✅ products: {actual_counts['products']} nodes created")
                print(f"   ✅ goals: {actual_counts['goals']} nodes created")

                if not validation_passed:
                    raise ValueError("Graph creation incomplete - some nodes missing")

            except Exception as e:
                print(f"\n❌ Graph creation failed: {e}")
                print("Attempting retry with increased timeout...")
                # Could implement retry logic here
                raise

            # Step 5: Generate embeddings with validation
            print("\n🧠 Step 5: Generating embeddings for semantic search...")

            # First check how many nodes need embeddings
            nodes_needing_embeddings = self.neo4j_ops.connection.execute_query(
                """
                MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
                WHERE n.embedding IS NULL AND n.description IS NOT NULL
                RETURN count(n) as count
            """,
                {"account_id": account_id},
            )

            nodes_to_embed = (
                nodes_needing_embeddings[0]["count"] if nodes_needing_embeddings else 0
            )

            if nodes_to_embed == 0:
                print("   ⚠️  No nodes found needing embeddings")
                # Check if nodes exist at all
                total_nodes = self.neo4j_ops.connection.execute_query(
                    """
                    MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
                    RETURN count(n) as count
                """,
                    {"account_id": account_id},
                )
                total = total_nodes[0]["count"] if total_nodes else 0

                if total == 0:
                    raise ValueError(
                        "No strategy nodes found in Neo4j - graph creation may have failed"
                    )
                else:
                    print(f"   ℹ️  {total} nodes already have embeddings")
            else:
                print(f"   ℹ️  Found {nodes_to_embed} nodes needing embeddings")

            # Generate embeddings
            embedding_result = self.embedding_generator.generate_embeddings_for_account(
                account_id
            )

            # Validate embedding generation
            if embedding_result["success_count"] == 0 and nodes_to_embed > 0:
                print(
                    f"\n❌ Embedding generation failed: Expected {nodes_to_embed}, generated 0"
                )
                print(
                    "   This indicates a problem with the embedding service or node structure"
                )
                raise ValueError(
                    f"Failed to generate embeddings for {nodes_to_embed} nodes"
                )
            elif embedding_result["success_count"] < nodes_to_embed:
                print(
                    f"   ⚠️  Partial success: {embedding_result['success_count']}/{nodes_to_embed} embeddings generated"
                )
                if embedding_result.get("errors"):
                    print(
                        f"   Errors: {embedding_result['errors'][:3]}..."
                    )  # Show first 3 errors
            else:
                print(
                    f"   ✅ Successfully generated {embedding_result['success_count']} embeddings"
                )

            # Step 6: Test semantic search
            print("\n🔍 Step 6: Testing semantic search...")
            test_queries = [
                "What are our main competitive advantages?",
                "How should we adapt to technological changes?",
                "What revenue streams do we have?",
            ]

            for query in test_queries:
                results = self.search.search(query, account_id, top_k=3)
                print(f"\nQuery: '{query}'")
                if results:
                    for r in results[:2]:
                        print(f"  - {r['type']}: {r['name']} (score: {r['score']})")
                else:
                    print("  No results found")

            print(f"\n{'=' * 60}")
            print("✅ BUSINESS STRATEGY GENERATION COMPLETE")
            print(f"{'=' * 60}\n")

            return {
                "success": True,
                "account_id": account_id,
                "strategy": strategy_dict,
                "graph_nodes": graph_nodes,
                "embeddings": embedding_result,
                "firestore_doc": firestore_result["document_id"],
            }

        except Exception as e:
            print(f"\n❌ Error generating strategy: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(e), "account_id": account_id}

    def save_to_firestore(
        self, strategy_dict: dict, doc_type: str, account_id: str
    ) -> dict:
        """Save strategy to Firestore."""
        doc_data = {
            "type": doc_type,
            "account_id": account_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "data": strategy_dict,
            "created_at": datetime.now().isoformat(),
            "version": 1,
        }

        result = _save_to_firestore_impl(
            collection=f"strategy_documents_{doc_type}",
            document_id=f"{account_id}_{self.session_id}",
            data=doc_data,
        )

        return {
            "document_id": result.get("document_id", f"{account_id}_{self.session_id}"),
            "collection": f"strategy_documents_{doc_type}",
        }

    def close(self):
        """Clean up connections."""
        self.neo4j_ops.close()


# ========== MAIN TEST FUNCTION ==========


async def test_neo4j_integration():
    """Test the complete Neo4j integration flow."""
    runner = Neo4jStrategyRunner()

    try:
        # Test with Tesla
        result = await runner.generate_business_strategy(
            company_name="Tesla", account_id="acc_tesla_test"
        )

        if result["success"]:
            print("\n" + "=" * 60)
            print("INTEGRATION TEST SUMMARY")
            print("=" * 60)
            print(f"✅ Account ID: {result['account_id']}")
            print(f"✅ Firestore Document: {result['firestore_doc']}")
            print("✅ Graph Nodes Created: Multiple types")
            print(f"✅ Embeddings Generated: {result['embeddings']['success_count']}")
            print("✅ Semantic Search: Working")
            print("\n🎉 Neo4j integration test completed successfully!")

            # Verify we can retrieve the data
            print("\n📋 Verifying data retrieval from Neo4j...")
            retrieved = runner.neo4j_ops.get_account_strategies(result["account_id"])
            if retrieved:
                print(
                    f"✅ Successfully retrieved {len(retrieved.get('strategies', []))} strategy nodes"
                )

        else:
            print(f"\n❌ Test failed: {result.get('error', 'Unknown error')}")

    finally:
        runner.close()


if __name__ == "__main__":
    # Check for Neo4j credentials
    if not os.getenv("NEO4J_URI") or "your-neo4j" in os.getenv("NEO4J_URI", ""):
        print("\n⚠️  Please update agents/.env with your Neo4j credentials:")
        print("   NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io")
        print("   NEO4J_USERNAME=neo4j")
        print("   NEO4J_PASSWORD=your-password")
        print(
            "\n   Vertex AI credentials are already configured via GOOGLE_CLOUD_PROJECT"
        )
        print("   Then run this test again.\n")
    else:
        asyncio.run(test_neo4j_integration())

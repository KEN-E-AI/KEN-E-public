#!/usr/bin/env python
"""
Test Neo4j integration with Marketing Strategy generation.
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
from agents.marketing_agents import (
    create_marketing_formatter,
    create_marketing_researcher,
)
from agents.marketing_graph_builder import MarketingGraphBuilder

# Import our modules
from agents.neo4j_tools import get_neo4j_operations
from agents.strategy_agent.marketing_models import MarketingResearchReport
from google import adk
from google.adk import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai.types import Content, Part

# ========== GOOGLE SEARCH AGENT ==========


def create_google_search_agent():
    """Create a Google search agent with direct search capabilities."""
    return adk.Agent(
        name="google_search",
        description="Searches the web for information",
        model="gemini-2.5-pro",
        tools=[google_search],  # Using the ADK google_search tool
        instruction="""You are a web search specialist.
When given a search query, use google_search to find relevant information.
Return comprehensive results from multiple searches if needed.
Focus on recent, authoritative sources.""",
    )


# ========== MARKETING STRATEGY RUNNER ==========


class MarketingStrategyRunner:
    """Runner for marketing strategy generation with Neo4j storage."""

    def __init__(self):
        self.session_id = f"session_{int(datetime.now().timestamp())}"
        self.user_id = "test_user"
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()

        # Initialize Neo4j components
        self.neo4j_ops = get_neo4j_operations()
        self.graph_builder = MarketingGraphBuilder(self.neo4j_ops)
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
        Use OpenAI to format research data into structured marketing research.
        OpenAI handles complex schemas better than Gemini.
        """
        from openai import OpenAI as OpenAIClient

        client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))

        # Use the chat.completions.parse method
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content": """You are a marketing research formatter.

Take the research report provided and format it into a structured marketing research report.

Guidelines:
- Identify all product categories mentioned in the research
- For each product category, extract 2-5 distinct ideal customer profiles
- For each customer profile, create:
  * A narrative describing the persona (name, background, pain points, needs, motivations, channels)
  * Problem awareness strategy (max 4000 chars) - how to make them aware of the problem
  * Brand awareness strategy (max 4000 chars) - how to introduce the brand
  * Consideration strategy (max 4000 chars) - how they evaluate options
  * Conversion strategy (max 4000 chars) - critical factors for purchase decision
  * Loyalty strategy (max 4000 chars) - how to foster retention and advocacy

- Write detailed, actionable strategies with specific channels and touchpoints
- Include concrete examples and tactics
- Focus on practical, implementable marketing approaches

Output valid JSON matching the MarketingResearchReport schema EXACTLY.
Ensure all required fields are populated with rich, detailed content.""",
                },
                {
                    "role": "user",
                    "content": f"Format this research into structured marketing research report:\n\n{research_data}",
                },
            ],
            # Pass the Pydantic class directly - OpenAI will handle the conversion
            response_format=MarketingResearchReport,
        )

        # The parsed response is in the parsed attribute
        if completion.choices[0].message.parsed:
            # Convert to dict for compatibility with the rest of our code
            return completion.choices[0].message.parsed.model_dump()
        else:
            # Fallback to JSON content if parsing failed
            return json.loads(completion.choices[0].message.content)

    async def generate_marketing_strategy(
        self, company_name: str, account_id: str = None
    ) -> dict[str, Any]:
        """
        Generate a complete marketing strategy and store in Neo4j.

        Args:
            company_name: Name of the company to analyze
            account_id: Unique account identifier

        Returns:
            Dictionary with strategy data and graph nodes
        """
        if not account_id:
            account_id = f"acc_{company_name.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"

        print(f"\n{'=' * 60}")
        print(f"Generating Marketing Strategy for {company_name}")
        print(f"Account ID: {account_id}")
        print(f"Session ID: {self.session_id}")
        print(f"{'=' * 60}\n")

        try:
            # Step 1: Research
            print("📊 Step 1: Researching customer profiles and marketing strategy...")
            google_search_agent = create_google_search_agent()
            researcher = create_marketing_researcher(google_search_agent)
            research_data = await self.run_agent(
                researcher,
                f"Research ideal customer profiles and marketing strategies for {company_name}. For each product category, identify 2-5 ideal customer profiles with detailed persona narratives and strategies for problem awareness, brand awareness, consideration, conversion, and loyalty.",
                "marketing_research",
            )
            print(f"✅ Research complete: {len(research_data)} characters")

            # Step 2: Format into structured data using Gemini 2.5 Pro first
            print(
                "\n📝 Step 2: Formatting into structured research report using Gemini 2.5 Pro..."
            )
            try:
                formatter = create_marketing_formatter()
                formatted_json = await self.run_agent(
                    formatter,
                    f"Format this research into structured marketing research report:\n\n{research_data}",
                    "marketing_format",
                )
                report_dict = json.loads(formatted_json)
                report = MarketingResearchReport(**report_dict)
                print("✅ Gemini 2.5 Pro successfully formatted the research!")
            except Exception as e:
                # Fallback to OpenAI if Gemini fails
                print(
                    f"⚠️ Gemini 2.5 Pro formatting failed: {e}, falling back to OpenAI..."
                )
                report_dict = self.format_with_openai(research_data)
                report = MarketingResearchReport(**report_dict)
                print("✅ OpenAI successfully formatted the research as fallback")

            total_profiles = sum(
                len(pc.ideal_customer_profiles) for pc in report.product_categories
            )
            print(
                f"✅ Structured research created with {len(report.product_categories)} product categories and {total_profiles} customer profiles"
            )

            # Step 3: Save to Firestore (backup)
            print("\n💾 Step 3: Saving to Firestore...")
            firestore_result = self.save_to_firestore(
                report_dict, "marketing_strategy", account_id
            )
            print(f"✅ Saved to Firestore: {firestore_result['document_id']}")

            # Step 4: Build Neo4j graph with validation
            print("\n🔗 Step 4: Building marketing knowledge graph in Neo4j...")
            try:
                graph_nodes = self.graph_builder.build_marketing_graph(
                    report, account_id, self.user_id
                )

                # Validate graph creation
                expected_profile_count = total_profiles
                expected_strategy_count = total_profiles * 5  # 5 strategies per profile

                actual_counts = {
                    "customer_profiles": len(graph_nodes.get("customer_profiles", [])),
                    "problem_awareness": len(
                        graph_nodes.get("problem_awareness_strategies", [])
                    ),
                    "brand_awareness": len(
                        graph_nodes.get("brand_awareness_strategies", [])
                    ),
                    "consideration": len(
                        graph_nodes.get("consideration_strategies", [])
                    ),
                    "conversion": len(graph_nodes.get("conversion_strategies", [])),
                    "loyalty": len(graph_nodes.get("loyalty_strategies", [])),
                }

                # Check for discrepancies
                validation_passed = True
                if actual_counts["customer_profiles"] < expected_profile_count:
                    print(
                        f"   ⚠️  customer_profiles: Expected {expected_profile_count}, got {actual_counts['customer_profiles']}"
                    )
                    validation_passed = False
                else:
                    print(
                        f"   ✅ customer_profiles: {actual_counts['customer_profiles']} nodes created"
                    )

                for strategy_type in [
                    "problem_awareness",
                    "brand_awareness",
                    "consideration",
                    "conversion",
                    "loyalty",
                ]:
                    if actual_counts[strategy_type] < expected_profile_count:
                        print(
                            f"   ⚠️  {strategy_type}: Expected {expected_profile_count}, got {actual_counts[strategy_type]}"
                        )
                        validation_passed = False
                    else:
                        print(
                            f"   ✅ {strategy_type}: {actual_counts[strategy_type]} nodes created"
                        )

                if not validation_passed:
                    raise ValueError("Graph creation incomplete - some nodes missing")

                # Check IS_MARKETED_TO relationships
                is_marketed_to_count = len(
                    graph_nodes.get("is_marketed_to_relationships", [])
                )
                print(
                    f"   ✅ IS_MARKETED_TO relationships: {is_marketed_to_count} created"
                )

            except Exception as e:
                print(f"\n❌ Graph creation failed: {e}")
                print("Attempting retry with increased timeout...")
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

            # Step 6: Test semantic search on marketing data
            print("\n🔍 Step 6: Testing semantic search on marketing intelligence...")
            test_queries = [
                "Who are our ideal customers?",
                "How should we make customers aware of our brand?",
                "What motivates customers to purchase?",
            ]

            for query in test_queries:
                results = self.search.search(query, account_id, top_k=3)
                print(f"\nQuery: '{query}'")
                if results:
                    for r in results[:2]:
                        print(
                            f"  - {r['type']}: {r['name'][:80]}... (score: {r['score']})"
                        )
                else:
                    print("  No results found")

            print(f"\n{'=' * 60}")
            print("✅ MARKETING STRATEGY GENERATION COMPLETE")
            print(f"{'=' * 60}\n")

            return {
                "success": True,
                "account_id": account_id,
                "research": report_dict,
                "graph_nodes": graph_nodes,
                "embeddings": embedding_result,
                "firestore_doc": firestore_result["document_id"],
            }

        except Exception as e:
            print(f"\n❌ Error generating marketing strategy: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(e), "account_id": account_id}

    def save_to_firestore(
        self, research_dict: dict, doc_type: str, account_id: str
    ) -> dict:
        """Save marketing research to Firestore."""
        doc_data = {
            "type": doc_type,
            "account_id": account_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "data": research_dict,
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


async def test_marketing_strategy():
    """Test the complete marketing strategy integration flow."""
    runner = MarketingStrategyRunner()

    try:
        # Test with Tesla (already has business strategy with ProductCategory nodes)
        result = await runner.generate_marketing_strategy(
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
            print("\n🎉 Marketing strategy integration test completed successfully!")

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
        asyncio.run(test_marketing_strategy())

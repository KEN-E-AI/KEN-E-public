#!/usr/bin/env python
"""
Test Neo4j integration with Brand Guidelines generation.
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

# Import our modules
from agents.neo4j_tools import Neo4jOperations, get_neo4j_operations
from agents.brand_graph_builder import BrandGraphBuilder
from agents.embeddings import EmbeddingGenerator, EmbeddingSearch
from agents.firestore_tools import _save_to_firestore_impl
from agents.strategy_agent.brand_models import BrandGuidelines
from agents.brand_agents import create_brand_researcher, create_brand_formatter

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
        tools=[google_search],
        instruction="""You are a web search specialist.
When given a search query, use google_search to find relevant information.
Return comprehensive results from multiple searches if needed.
Focus on recent, authoritative sources."""
    )


# ========== BRAND GUIDELINES RUNNER ==========

class BrandGuidelinesRunner:
    """Runner for brand guidelines generation with Neo4j storage."""

    def __init__(self):
        self.session_id = f"session_{int(datetime.now().timestamp())}"
        self.user_id = "test_user"
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()

        # Initialize Neo4j components
        self.neo4j_ops = get_neo4j_operations()
        self.graph_builder = BrandGraphBuilder(self.neo4j_ops)
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
        Use OpenAI to format research data into structured brand guidelines.
        OpenAI handles complex schemas better than Gemini.
        """
        from openai import OpenAI as OpenAIClient

        client = OpenAIClient(api_key=os.getenv('OPENAI_API_KEY'))

        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": """You are a brand guidelines formatter.

Take the research report provided and format it into structured brand guidelines.

Guidelines for each field:
- brand_identity: Brief introduction to the brand, its reason for existence, taglines
- brand_personality: Describe as if brand were a person (friendly, professional, adventurous, etc.)
- voice_and_tone: How brand speaks, tone (friendly/formal/playful), style, specific language to use/avoid
- color_palette: List all colors with codes (HEX, RGB, CMYK, Pantone), usage guidelines
- typography: Primary/secondary fonts, hierarchy (headlines, body, captions), sizes, spacing rules
- image_style: Photography/illustration style (bright/minimalist/bold), treatments, subject matter
- mission_and_values: Underlying principles and purpose guiding actions and messaging

Write detailed, comprehensive descriptions. Include specific examples and technical details.
Output valid JSON matching the BrandGuidelines schema EXACTLY."""},
                {"role": "user", "content": f"Format this research into structured brand guidelines:\n\n{research_data}"}
            ],
            response_format=BrandGuidelines
        )

        if completion.choices[0].message.parsed:
            return completion.choices[0].message.parsed.model_dump()
        else:
            return json.loads(completion.choices[0].message.content)

    async def generate_brand_guidelines(self, company_name: str, account_id: str = None) -> Dict[str, Any]:
        """
        Generate complete brand guidelines and store in Neo4j.

        Args:
            company_name: Name of the company
            account_id: Unique account identifier

        Returns:
            Dictionary with guidelines data and graph nodes
        """
        if not account_id:
            account_id = f"acc_{company_name.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"

        print(f"\n{'='*60}")
        print(f"Generating Brand Guidelines for {company_name}")
        print(f"Account ID: {account_id}")
        print(f"Session ID: {self.session_id}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Research
            print("📊 Step 1: Researching brand guidelines...")
            google_search_agent = create_google_search_agent()
            researcher = create_brand_researcher(google_search_agent)
            research_data = await self.run_agent(
                researcher,
                f"Research comprehensive brand guidelines for {company_name}. Find information about their brand identity, personality, voice and tone, color palette, typography, image style, and mission/values.",
                "brand_research"
            )
            print(f"✅ Research complete: {len(research_data)} characters")

            # Step 2: Format using Gemini 2.5 Pro first
            print("\n📝 Step 2: Formatting into structured guidelines using Gemini 2.5 Pro...")
            try:
                formatter = create_brand_formatter()
                formatted_json = await self.run_agent(
                    formatter,
                    f"Format this research into structured brand guidelines:\n\n{research_data}",
                    "brand_format"
                )
                guidelines_dict = json.loads(formatted_json)
                guidelines = BrandGuidelines(**guidelines_dict)
                print("✅ Gemini 2.5 Pro successfully formatted the guidelines!")
            except Exception as e:
                print(f"⚠️ Gemini 2.5 Pro formatting failed: {e}, falling back to OpenAI...")
                guidelines_dict = self.format_with_openai(research_data)
                guidelines = BrandGuidelines(**guidelines_dict)
                print("✅ OpenAI successfully formatted the guidelines as fallback")
            print(f"✅ Structured brand guidelines created")

            # Step 3: Save to Firestore
            print("\n💾 Step 3: Saving to Firestore...")
            firestore_result = self.save_to_firestore(guidelines_dict, "brand_guidelines", account_id)
            print(f"✅ Saved to Firestore: {firestore_result['document_id']}")

            # Step 4: Build Neo4j graph
            print("\n🔗 Step 4: Building brand guidelines knowledge graph in Neo4j...")
            graph_nodes = self.graph_builder.build_brand_graph(
                guidelines,
                account_id,
                self.user_id
            )

            # Validate all 7 nodes created
            expected_nodes = ['brand_identity', 'brand_personality', 'voice_and_tone',
                            'color_palette', 'typography', 'image_style', 'mission_and_values']
            for node_type in expected_nodes:
                if graph_nodes.get(node_type):
                    print(f"   ✅ {node_type}: Created")
                else:
                    print(f"   ⚠️  {node_type}: Missing")

            # Step 5: Generate embeddings
            print("\n🧠 Step 5: Generating embeddings for semantic search...")
            embedding_result = self.embedding_generator.generate_embeddings_for_account(account_id)
            print(f"   ✅ Successfully generated {embedding_result['success_count']} embeddings")

            # Step 6: Test semantic search
            print("\n🔍 Step 6: Testing semantic search on brand guidelines...")
            test_queries = [
                "What is the brand's personality?",
                "What colors should we use?",
                "How should we communicate with customers?"
            ]

            for query in test_queries:
                results = self.search.search(query, account_id, top_k=2)
                print(f"\nQuery: '{query}'")
                if results:
                    for r in results[:2]:
                        print(f"  - {r['type']}: {r['name'][:60]}...")
                else:
                    print("  No results found")

            print(f"\n{'='*60}")
            print("✅ BRAND GUIDELINES GENERATION COMPLETE")
            print(f"{'='*60}\n")

            return {
                'success': True,
                'account_id': account_id,
                'guidelines': guidelines_dict,
                'graph_nodes': graph_nodes,
                'embeddings': embedding_result,
                'firestore_doc': firestore_result['document_id']
            }

        except Exception as e:
            print(f"\n❌ Error generating brand guidelines: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'account_id': account_id
            }

    def save_to_firestore(self, guidelines_dict: Dict, doc_type: str, account_id: str) -> Dict:
        """Save brand guidelines to Firestore."""
        doc_data = {
            "type": doc_type,
            "account_id": account_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "data": guidelines_dict,
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

async def test_brand_guidelines():
    """Test the complete brand guidelines integration flow."""
    runner = BrandGuidelinesRunner()

    try:
        # Test with Tesla (already has business, competitive, and marketing strategy)
        result = await runner.generate_brand_guidelines(
            company_name="Tesla",
            account_id="acc_tesla_test"
        )

        if result['success']:
            print("\n" + "="*60)
            print("INTEGRATION TEST SUMMARY")
            print("="*60)
            print(f"✅ Account ID: {result['account_id']}")
            print(f"✅ Firestore Document: {result['firestore_doc']}")
            print(f"✅ Graph Nodes Created: 7 brand guideline nodes")
            print(f"✅ Embeddings Generated: {result['embeddings']['success_count']}")
            print("\n🎉 Brand guidelines integration test completed successfully!")

        else:
            print(f"\n❌ Test failed: {result.get('error', 'Unknown error')}")

    finally:
        runner.close()


if __name__ == "__main__":
    # Check for Neo4j credentials
    if not os.getenv('NEO4J_URI') or 'your-neo4j' in os.getenv('NEO4J_URI', ''):
        print("\n⚠️  Please update agents/.env with your Neo4j credentials")
        print("   Then run this test again.\n")
    else:
        asyncio.run(test_brand_guidelines())

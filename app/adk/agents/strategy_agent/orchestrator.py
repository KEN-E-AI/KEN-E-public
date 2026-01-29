#!/usr/bin/env python3
from __future__ import annotations

"""
Strategy Agent Orchestrator - Manages execution and persistence of strategy documents.
Includes comprehensive analytics tracking for cost, performance, and optimization.
"""

import json
import logging
import os
import time
import uuid
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any, List, Optional

# Import weave for tracing
import weave  # noqa: E402
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content
from vertexai.preview import reasoning_engines

# Import strategy components
try:
    # Absolute imports for deployment
    from agents.strategy_agent.alert_manager import AlertManager

    # Import analytics components
    from agents.strategy_agent.analytics_helpers import (
        check_token_limits_before_execution,
        initialize_analytics_services,
        report_execution_summary,
    )
    from agents.strategy_agent.analytics_service import AnalyticsService
    from agents.strategy_agent.artifact_utils import (
        load_uploaded_documents_as_artifacts,
    )
    from agents.strategy_agent.constants import (
        DEFAULT_PRODUCT_CATEGORIES,
        VALID_STRATEGY_TYPES,
    )
    from agents.strategy_agent.firestore import FirestoreClient
    from agents.strategy_agent.models import StrategyContext
    from agents.strategy_agent.performance_profiler import PerformanceProfiler
    from shared.token_utils import TokenEstimator
except ImportError:
    # Relative imports for local testing
    from shared.token_utils import TokenEstimator

    from .alert_manager import AlertManager

    # Import analytics components
    from .analytics_helpers import (
        check_token_limits_before_execution,
        initialize_analytics_services,
        report_execution_summary,
    )
    from .analytics_service import AnalyticsService
    from .artifact_utils import load_uploaded_documents_as_artifacts
    from .constants import VALID_STRATEGY_TYPES
    from .firestore import FirestoreClient
    from .models import StrategyContext
    from .performance_profiler import PerformanceProfiler

# Load environment variables from .env file if it exists
# The .env file is deployed with the agent and loaded at runtime
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        logging.info(f"Loaded environment variables from {env_path}")
    else:
        # Try alternate location (agents/.env)
        alt_path = Path(__file__).parent.parent / ".env"
        if alt_path.exists():
            load_dotenv(alt_path, override=False)
            logging.info(f"Loaded environment variables from {alt_path}")
except ImportError:
    logging.warning("python-dotenv not available")
except Exception as e:
    logging.warning(f"Failed to load .env file: {e}")

logger = logging.getLogger(__name__)

# W&B observability will be initialized lazily when needed
# This prevents initialization failures during Engine startup
WEAVE_INITIALIZED = False


def init_weave_if_needed():
    """Initialize W&B Weave if not already initialized and API key is available."""
    global WEAVE_INITIALIZED
    if not WEAVE_INITIALIZED:
        # Get W&B API key using shared secrets utility
        wandb_api_key = None
        try:
            from shared.secrets import get_env_or_secret

            wandb_api_key = get_env_or_secret("WANDB_API_KEY")
            if wandb_api_key:
                os.environ["WANDB_API_KEY"] = wandb_api_key
                logger.info("✅ Retrieved WANDB_API_KEY")
            else:
                logger.warning("⚠️ WANDB_API_KEY not found in environment or Secret Manager")
        except Exception as e:
            logger.warning(f"⚠️ Failed to retrieve WANDB_API_KEY: {e}")

        if wandb_api_key:
            try:
                # Use environment-specific project name from .env
                project_name = os.getenv("WEAVE_PROJECT_NAME", "ken-e-dev")
                weave.init(project_name=project_name)
                logger.info(f"✅ W&B Weave initialized (project: {project_name})")
                WEAVE_INITIALIZED = True
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Weave: {e}")
                WEAVE_INITIALIZED = True  # Mark as attempted to avoid retry
        else:
            logger.warning(
                "⚠️ WANDB_API_KEY not available, W&B tracing will not be enabled"
            )
            WEAVE_INITIALIZED = True  # Mark as attempted to avoid retry


# Define the mapping of output keys to document types
DOCUMENT_KEY_MAPPING = {
    "business_strategy_doc": "business_strategy",
    "competitive_strategy_doc": "competitive_strategy",
    "customer_strategy_doc": "customer_strategy",
    "marketing_strategy_doc": "marketing_strategy",
    "brand_guidelines_doc": "brand_guidelines",
}


def _create_placeholder_strategy(model_class, strategy_name: str, company_name: str):
    """
    Create minimal placeholder data when strategy generation fails.

    Creates top-level entities with "Requires further research" descriptions.
    DOES NOT create child nodes (Opportunities/Risks for SWOT, ValuePropositions for products).

    Args:
        model_class: Pydantic model class for the strategy
        strategy_name: Type of strategy (business_strategy, competitive_strategy, etc.)
        company_name: Company name for context

    Returns:
        Minimal placeholder data matching the model schema
    """
    from .brand_models import BrandGuidelines
    from .competitive_models import (
        CompetitiveAnalysis,
        Competitor,
        NamedDetail,
        StrengthWithRisks,
        SubstituteProduct,
        WeaknessWithOpportunities,
    )
    from .marketing_models import (
        IdealCustomerProfile,
        MarketingResearchReport,
        MarketingStrategy,
        MarketingStrategyForProfile,
        ProductCategoryMapping,
    )
    from .structured_models import (
        ProductCategory,
        ProductService,
        StrategicGoal,
        StrengthOpportunityLink,
        StructuredBusinessStrategy,
        SWOTItem,
        WeaknessRiskLink,
    )

    if model_class == StructuredBusinessStrategy:
        # Business: Create minimal products/goals/SWOT WITHOUT child nodes
        return StructuredBusinessStrategy(
            company_name=company_name,
            company_overview_summary=f"Automated research for {company_name} requires further investigation.",
            business_value_propositions=[],  # No placeholder ValueProps
            product_portfolio=[
                ProductCategory(
                    category_name="Primary Products",
                    value_propositions=[],  # No placeholder ValueProps
                    products=[
                        ProductService(
                            id="placeholder-product",
                            display_name="Product Analysis Pending",
                            description="Requires further research",
                            value_propositions=[],  # No placeholder ValueProps
                        )
                    ],
                )
            ],
            swot_analysis={
                "strengths_and_opportunities": [
                    StrengthOpportunityLink(
                        strength=SWOTItem(
                            id="placeholder-strength",
                            description="Requires further research",
                        ),
                        linked_opportunities=[
                            SWOTItem(
                                id="placeholder-opportunity",
                                description="Requires further research",
                            )
                        ],  # Schema requires min_length=1
                    )
                ],
                "weaknesses_and_risks": [
                    WeaknessRiskLink(
                        weakness=SWOTItem(
                            id="placeholder-weakness",
                            description="Requires further research",
                        ),
                        linked_risks=[
                            SWOTItem(
                                id="placeholder-risk",
                                description="Requires further research",
                            )
                        ],  # Schema requires min_length=1
                    )
                ],
            },
            strategic_goals=[
                StrategicGoal(
                    id="placeholder-goal",
                    display_name="Strategic Planning Pending",
                    description="Requires further research",
                )
            ],
            final_summary=f"Strategy analysis for {company_name} requires further research.",
        )

    elif model_class == CompetitiveAnalysis:
        # Competitive: Create competitor WITHOUT child nodes
        return CompetitiveAnalysis(
            company_products=["Analysis Pending"],
            competitive_environment_description=f"Competitive analysis for {company_name} requires further research.",
            competitors=[
                Competitor(
                    name="Competitive Analysis Pending",
                    description="Requires further research",
                    value_propositions=[],  # No placeholder ValueProps
                    marketing_tactics=[
                        NamedDetail(
                            name="Analysis Pending",
                            description="Requires further research",
                        )
                    ],
                    substitute_products=[
                        SubstituteProduct(
                            name="Analysis Pending",
                            description="Requires further research",
                            value_proposition=NamedDetail(
                                name="Pending", description="Requires further research"
                            ),
                        )
                    ],
                    strengths=[
                        StrengthWithRisks(
                            name="Analysis Pending",
                            description="Requires further research",
                            risks=[
                                NamedDetail(
                                    name="Risk Analysis Pending",
                                    description="Requires further research",
                                )
                            ],  # Schema requires min_length=1
                        )
                    ],
                    weaknesses=[
                        WeaknessWithOpportunities(
                            name="Analysis Pending",
                            description="Requires further research",
                            opportunities=[
                                NamedDetail(
                                    name="Opportunity Analysis Pending",
                                    description="Requires further research",
                                )
                            ],  # Schema requires min_length=1
                        )
                    ],
                )
            ],
        )

    elif model_class == MarketingResearchReport:
        # Marketing: Create master customer profiles and category mappings
        # Note: Strategies are now scoped to product category + profile combinations
        return MarketingResearchReport(
            ideal_customer_profiles=[
                IdealCustomerProfile(
                    display_name="Placeholder Customer",
                    narrative=f"Customer analysis for {company_name} requires further research.",
                    references=[],
                ),
                IdealCustomerProfile(
                    display_name="Generic Buyer",
                    narrative=f"Generic buyer profile for {company_name} requires further research.",
                    references=[],
                ),
            ],
            product_category_mappings=[
                ProductCategoryMapping(
                    category_name="Primary Products",
                    customer_strategies=[
                        MarketingStrategyForProfile(
                            customer_profile_name="Placeholder Customer",
                            strategy=MarketingStrategy(
                                problem_awareness_strategy="Requires further research",
                                brand_awareness_strategy="Requires further research",
                                consideration_strategy="Requires further research",
                                conversion_strategy="Requires further research",
                                loyalty_strategy="Requires further research",
                                references=[],
                            ),
                        ),
                        MarketingStrategyForProfile(
                            customer_profile_name="Generic Buyer",
                            strategy=MarketingStrategy(
                                problem_awareness_strategy="Requires further research",
                                brand_awareness_strategy="Requires further research",
                                consideration_strategy="Requires further research",
                                conversion_strategy="Requires further research",
                                loyalty_strategy="Requires further research",
                                references=[],
                            ),
                        ),
                    ],
                )
            ],
        )

    elif model_class == BrandGuidelines:
        # Brand: Create minimal brand identity
        return BrandGuidelines(
            brand_identity=f"Brand analysis for {company_name} requires further research.",
            brand_personality="Requires further research",
            voice_and_tone="Requires further research",
            color_palette="Requires further research",
            typography="Requires further research",
            image_style="Requires further research",
            mission_and_values="Requires further research",
        )

    else:
        raise ValueError(f"Unknown model class: {model_class}")


def extract_document_sections(
    doc: dict | None, required_fields: list[str]
) -> dict[str, Any]:
    """
    Extract specific fields from a strategy document.

    Args:
        doc: The strategy document dictionary
        required_fields: List of field names to extract

    Returns:
        Dictionary with only the required fields
    """
    if not doc:
        return {}

    extracted = {}
    for field in required_fields:
        if field in doc:
            extracted[field] = doc[field]

    return extracted


@weave.op(name="execute_single_strategy")
def _execute_single_strategy(
    strategy_config: dict,
    strategy_context: StrategyContext,
    firestore_client: FirestoreClient,
    google_search_agent: Any,
    neo4j_ops: Any,
    embedding_generator: Any,
    performance_profiler: Any | None,
    analytics_service: Any | None,
    dry_run: bool,
    product_category_names: list[str] | None = None,
    override_product_categories: list[str] | None = None,
) -> tuple[str, dict, bool]:
    """
    Execute a single strategy (research + format + save).

    Args:
        strategy_config: Strategy configuration dict
        strategy_context: StrategyContext with company information
        firestore_client: Firestore client for saving
        google_search_agent: Google search tool agent
        neo4j_ops: Neo4j operations instance
        embedding_generator: Embedding generator instance
        performance_profiler: Optional performance profiler
        analytics_service: Optional analytics service
        dry_run: If True, skip storage operations
        product_category_names: Product categories from business strategy (for marketing)
        override_product_categories: Override categories (for marketing)

    Returns:
        Tuple of (strategy_name, doc_content, used_openai)

    Raises:
        Exception: If strategy execution fails
    """
    strategy_name = strategy_config["name"]
    logger.info(f"\n[SPLIT AGENT] ========== Starting {strategy_name} ==========")

    # Track operation
    operation = None
    if performance_profiler:
        operation = performance_profiler.start_operation(
            agent_name=f"{strategy_name}_split",
            operation="strategy_generation",
            metadata={"strategy_type": strategy_name},
        )

    used_openai = False

    try:
        # ===== STEP 1: RESEARCH (with tools, no schema) =====
        logger.info(f"[SPLIT AGENT] Step 1: Research phase for {strategy_name}")
        researcher = strategy_config["create_researcher"]()

        # Run researcher agent
        from google.adk import Runner
        from google.genai.types import Content

        session_service = InMemorySessionService()
        app_name = f"{strategy_name}_research"
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        session = session_service.create_session_sync(
            app_name=app_name,
            user_id=strategy_context.user_id or "system",
            session_id=session_id,
            state={},
        )

        runner = Runner(
            agent=researcher, app_name=app_name, session_service=session_service
        )

        # Build comprehensive research query
        research_query = f"Research comprehensive {strategy_name.replace('_', ' ')} for {strategy_context.company_name}\n\n"
        research_query += f"Company: {strategy_context.company_name}\n"
        if strategy_context.websites:
            research_query += f"Website(s): {', '.join(strategy_context.websites)}\n"
        research_query += f"Industry: {strategy_context.industry}\n"
        if strategy_context.customer_regions:
            research_query += (
                f"Customer Regions: {', '.join(strategy_context.customer_regions)}\n"
            )
        if strategy_context.annual_ad_budget:
            research_query += f"Annual Advertising Budget: ${strategy_context.annual_ad_budget:,.0f}\n"

        # For marketing strategy, handle product categories
        if strategy_name == "marketing_strategy":
            from .constants import DEFAULT_PRODUCT_CATEGORIES

            categories_to_use = None
            if override_product_categories is not None:
                categories_to_use = override_product_categories
                logger.info(
                    f"[SELECTIVE] Using {len(categories_to_use)} override product categories"
                )
            elif product_category_names:
                categories_to_use = product_category_names
                logger.info(
                    f"[COORDINATION] Using {len(categories_to_use)} product categories from business strategy"
                )
            else:
                categories_to_use = DEFAULT_PRODUCT_CATEGORIES
                logger.info(
                    f"[SELECTIVE] Using {len(categories_to_use)} default product categories"
                )

            # Add structured instructions
            research_query += "\n\n=== CRITICAL STRUCTURE REQUIREMENTS ===\n"
            research_query += "\nPHASE 1: Create 2-5 MASTER customer profiles for the entire company\n"
            research_query += "- Give each profile a unique, descriptive display_name\n"
            research_query += "- Include ONLY: display_name, narrative, references\n"
            research_query += f"\nPHASE 2: For EACH of these {len(categories_to_use)} product categories, create a dedicated marketing strategy:\n"
            for i, category in enumerate(categories_to_use, 1):
                research_query += f"\n{i}. {category}"
            research_query += "\n\nFor each category, include:\n"
            research_query += "- product_category_name (EXACT name from above)\n"
            research_query += (
                "- customer_profile_names (reference Master profiles by display_name)\n"
            )
            research_query += "- marketing_channels, messaging_themes, campaign_ideas\n"

        # Execute research
        logger.info(
            f"[SPLIT AGENT] Sending research query (length: {len(research_query)} chars)"
        )

        @weave.op(name=f"{strategy_name}_research")
        def run_research():
            return list(
                runner.run(
                    user_id=strategy_context.user_id or "system",
                    session_id=session_id,
                    new_message=Content(parts=[{"text": research_query}]),
                )
            )

        events = run_research()

        # Extract research text and grounding metadata (source URLs)
        research_text = ""
        source_urls = []
        for event in events:
            if hasattr(event, "content") and hasattr(event.content, "parts"):
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text is not None:
                        research_text += part.text

            # Extract source URLs from grounding metadata
            if hasattr(event, "grounding_metadata") and event.grounding_metadata:
                if hasattr(event.grounding_metadata, "grounding_attributions"):
                    for attribution in event.grounding_metadata.grounding_attributions:
                        if hasattr(attribution, "source_id"):
                            if hasattr(attribution.source_id, "grounding_passage"):
                                if hasattr(
                                    attribution.source_id.grounding_passage, "uri"
                                ):
                                    url = attribution.source_id.grounding_passage.uri
                                    if url and url not in source_urls:
                                        source_urls.append(url)

        logger.info(
            f"[SPLIT AGENT] ✅ Research completed: {len(research_text)} chars, "
            f"{len(source_urls)} source URLs"
        )
        if source_urls:
            logger.info(f"[SPLIT AGENT] Source URLs: {source_urls[:3]}...")

        if not research_text:
            raise ValueError(f"Research phase returned no data for {strategy_name}")

        # ===== STEP 2: FORMAT (no tools, with schema) =====
        # Using OpenAI directly (Gemini formatter removed due to high failure rate)
        logger.info(
            f"[SPLIT AGENT] Step 2: Formatting with OpenAI ({strategy_config['model_class'].__name__})"
        )

        # Import OpenAI formatter
        from .openai_formatter import format_with_openai

        # Load Firestore instructions using config_loader
        firestore_instructions = None
        if "formatter_doc_id" in strategy_config:
            try:
                from .config_loader import load_config_from_firestore

                # Use environment-specific project ID
                formatter_project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
                config, _ = load_config_from_firestore(
                    strategy_config["formatter_doc_id"],
                    project_id=formatter_project_id
                )
                firestore_instructions = getattr(
                    config, "instruction", None
                ) or getattr(config, "system_instruction", None)
                if firestore_instructions:
                    logger.info(
                        f"[SPLIT AGENT] ✅ Loaded Firestore instructions for {strategy_name} "
                        f"(length: {len(firestore_instructions)} chars)"
                    )
            except Exception as e:
                logger.warning(
                    f"[SPLIT AGENT] ⚠️  Failed to load Firestore instructions: {e}"
                )

        @weave.op(name=f"{strategy_name}_format_openai")
        def run_openai_formatter():
            return format_with_openai(
                research_text,
                strategy_config["model_class"],
                strategy_name,
                source_urls,
                custom_instructions=firestore_instructions,
            )

        openai_dict = run_openai_formatter()
        formatted_data = strategy_config["model_class"](**openai_dict)
        used_openai = True
        logger.info("[SPLIT AGENT] ✅ OpenAI formatting successful")

        # Convert to dict for storage
        doc_content = formatted_data.model_dump()

        # ===== STEP 3: SAVE TO FIRESTORE =====
        if not dry_run:
            logger.info("[SPLIT AGENT] Step 3: Saving to Firestore")
            save_result = firestore_client.save_strategy_document_sync(
                account_id=strategy_context.account_id,
                doc_type=strategy_name,
                content=doc_content,
                user_id=strategy_context.user_id,
            )

            if not save_result:
                raise ValueError(f"Failed to save {strategy_name} to Firestore")

            logger.info("[SPLIT AGENT] ✅ Saved to Firestore")
        else:
            logger.info("[DRY-RUN] ⏩ Skipping Firestore save")

        # ===== STEP 4: BUILD NEO4J GRAPH =====
        if neo4j_ops and not dry_run:
            logger.info("[SPLIT AGENT] Step 4: Building Neo4j knowledge graph")
            graph_builder = strategy_config["graph_builder_class"](neo4j_ops)
            build_method = getattr(graph_builder, strategy_config["graph_method"])
            graph_nodes = build_method(
                formatted_data,
                strategy_context.account_id,
                strategy_context.user_id or "system",
            )
            logger.info("[SPLIT AGENT] ✅ Neo4j graph built successfully")
        elif dry_run:
            logger.info("[DRY-RUN] ⏩ Skipping Neo4j graph build")

        # ===== STEP 5: GENERATE EMBEDDINGS =====
        if neo4j_ops and embedding_generator and not dry_run:
            logger.info("[SPLIT AGENT] Step 5: Generating embeddings")
            try:
                embedding_result = embedding_generator.generate_embeddings_for_account(
                    strategy_context.account_id
                )
                logger.info(
                    f"[SPLIT AGENT] ✅ Embeddings generated: {embedding_result.get('embeddings_created', 0)} nodes"
                )
            except Exception as embed_error:
                logger.error(
                    f"[SPLIT AGENT] ❌ Embedding generation failed: {embed_error}"
                )
        elif dry_run:
            logger.info("[DRY-RUN] ⏩ Skipping embedding generation")

        # Track analytics
        if performance_profiler and operation:
            performance_profiler.end_operation(operation, success=True)

        if analytics_service:
            analytics_service.track_agent_execution(
                agent_name=f"{strategy_name}_{'openai' if used_openai else 'gemini'}",
                prompt_tokens=0,
                response_tokens=0,
                model="gpt-4o" if used_openai else "gemini-2.5-pro",
                execution_time=0,
                success=True,
            )

        logger.info(f"[SPLIT AGENT] ✅✅✅ Successfully completed {strategy_name}")
        return (strategy_name, doc_content, used_openai)

    except Exception as e:
        error_msg = f"Error generating {strategy_name}: {e}"
        logger.error(f"[SPLIT AGENT] ❌ {error_msg}")

        if performance_profiler and operation:
            performance_profiler.end_operation(operation, success=False, error=str(e))

        raise  # Re-raise for fail-fast behavior


@weave.op(name="execute_all_strategies")
def execute_strategy_generation_direct(
    context: StrategyContext,
    firestore_client: FirestoreClient,
    analytics_service: AnalyticsService | None = None,
    performance_profiler: PerformanceProfiler | None = None,
    alert_manager: AlertManager | None = None,
    enabled_strategies: list[str] | None = None,
    override_product_categories: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Execute strategy generation using split agent architecture + Neo4j.

    This function orchestrates all 4 strategy executions (business first,
    then 3 in parallel) and is traced to ensure proper parent-child
    relationships in W&B Weave.

    New architecture:
    1. Runs researcher agent (with tools, no output_schema)
    2. Runs formatter agent (no tools, with output_schema)
    3. Falls back to OpenAI if Gemini formatter fails
    4. Saves to Firestore
    5. Builds Neo4j knowledge graph
    6. Generates embeddings for semantic search

    Args:
        context: StrategyContext with company information
        firestore_client: Firestore client for saving documents
        analytics_service: Optional analytics service for tracking
        performance_profiler: Optional performance profiler
        alert_manager: Optional alert manager
        enabled_strategies: Optional list of strategy types to generate.
            Valid values: ["business_strategy", "competitive_strategy",
            "marketing_strategy", "brand_guidelines"].
            If None, all strategies are generated.
        override_product_categories: Optional list of product category names
            to use for marketing strategy when business strategy is not run.
            If None and marketing strategy is enabled without business strategy,
            default categories will be used.
        dry_run: If True, skips Firestore, Neo4j, and embedding storage.
            Useful for evaluation runs where you want W&B traces without
            persisting data. Default is False.

    Returns:
        Dictionary of generated documents
    """
    generated_documents = {}

    # Log dry-run mode if enabled
    if dry_run:
        logger.info(
            "[DRY-RUN] 🔧 Dry-run mode enabled - strategies will NOT be saved to Firestore/Neo4j"
        )
        logger.info(
            "[DRY-RUN] W&B Weave traces will be captured for evaluation purposes"
        )

    # Validate and set default for enabled_strategies
    if enabled_strategies is None:
        # If not specified, generate all strategies
        enabled_strategies = VALID_STRATEGY_TYPES.copy()
        logger.info(
            "[SELECTIVE] No enabled_strategies specified, generating all strategies"
        )
    else:
        # Validate that all provided strategies are valid
        invalid_strategies = [
            s for s in enabled_strategies if s not in VALID_STRATEGY_TYPES
        ]
        if invalid_strategies:
            raise ValueError(
                f"Invalid strategy types: {invalid_strategies}. "
                f"Valid types are: {VALID_STRATEGY_TYPES}"
            )
        # Validate that at least one strategy is selected
        if len(enabled_strategies) == 0:
            raise ValueError("At least one strategy must be selected for generation")
        logger.info(
            f"[SELECTIVE] Generating selected strategies: {', '.join(enabled_strategies)}"
        )

    # Handle product category override for marketing strategy
    if override_product_categories is not None:
        if "marketing_strategy" not in enabled_strategies:
            logger.warning(
                "[SELECTIVE] override_product_categories provided but marketing_strategy "
                "not in enabled_strategies - ignoring override"
            )
            override_product_categories = None
        else:
            logger.info(
                f"[SELECTIVE] Using {len(override_product_categories)} override product "
                f"categories for marketing strategy: {', '.join(override_product_categories)}"
            )

    # Import split agent creators and graph builders
    try:
        from .agents import create_google_search_agent
        from .brand_agents import create_brand_formatter, create_brand_researcher
        from .brand_graph_builder import BrandGraphBuilder
        from .brand_models import BrandGuidelines
        from .business_agents import (
            create_business_formatter,
            create_business_researcher,
        )
        from .business_graph_builder import GraphBuilder
        from .competitive_agents import (
            create_competitive_formatter,
            create_competitive_researcher,
        )
        from .competitive_graph_builder import CompetitiveGraphBuilder
        from .competitive_models import CompetitiveAnalysis
        from .embeddings import EmbeddingGenerator
        from .marketing_agents import (
            create_marketing_formatter,
            create_marketing_researcher,
        )
        from .marketing_graph_builder import MarketingGraphBuilder
        from .marketing_models import MarketingResearchReport

        # Import Neo4j components
        from .neo4j_tools import get_neo4j_operations

        # Import Pydantic models
        from .structured_models import StructuredBusinessStrategy
    except ImportError as e:
        logger.error(f"Failed to import split agent modules: {e}")
        raise

    # Initialize Neo4j components
    try:
        neo4j_ops = get_neo4j_operations()
        neo4j_ops.create_indexes()  # Ensure indexes exist
        embedding_generator = EmbeddingGenerator(neo4j_ops)
        logger.info("✅ Neo4j components initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Neo4j: {e}")
        # Continue without Neo4j - save to Firestore only
        neo4j_ops = None
        embedding_generator = None

    # Create google search agent (shared across all researchers)
    google_search_agent = create_google_search_agent()

    # Log config metadata for business strategy agents to Weave
    try:
        from .config_loader import get_current_config_metadata

        business_researcher_config = get_current_config_metadata("business_researcher")
        business_formatter_config = get_current_config_metadata("business_formatter")

        # Log config metadata to Weave using call.summary (correct API)
        try:
            call = weave.get_current_call()
            if call:
                call.summary["business_researcher_version"] = (
                    business_researcher_config.get("version", "unknown")
                )
                call.summary["business_researcher_variant"] = (
                    business_researcher_config.get("variant_name", "unknown")
                )
                call.summary["business_researcher_model"] = (
                    business_researcher_config.get("model", "unknown")
                )
                call.summary["business_formatter_version"] = (
                    business_formatter_config.get("version", "unknown")
                )
                call.summary["business_formatter_variant"] = (
                    business_formatter_config.get("variant_name", "unknown")
                )
                call.summary["business_formatter_model"] = (
                    business_formatter_config.get("model", "unknown")
                )
        except Exception:
            pass  # Weave not initialized, continue without logging

        logger.info(
            f"[CONFIG] Using business_researcher config - "
            f"version: {business_researcher_config.get('version', 'unknown')}, "
            f"variant: {business_researcher_config.get('variant_name', 'unknown')}, "
            f"model: {business_researcher_config.get('model', 'unknown')}"
        )
        logger.info(
            f"[CONFIG] Using business_formatter config - "
            f"version: {business_formatter_config.get('version', 'unknown')}, "
            f"variant: {business_formatter_config.get('variant_name', 'unknown')}, "
            f"model: {business_formatter_config.get('model', 'unknown')}"
        )
    except Exception as e:
        logger.warning(f"[CONFIG] Failed to log config metadata to Weave: {e}")

    # Define strategy types to generate (removed customer_strategy)
    strategy_types = [
        {
            "name": "business_strategy",
            "create_researcher": lambda: create_business_researcher(
                google_search_agent
            ),
            "create_formatter": create_business_formatter,
            "formatter_doc_id": "business_formatter",
            "model_class": StructuredBusinessStrategy,
            "graph_builder_class": GraphBuilder,
            "graph_method": "build_strategy_graph",
        },
        {
            "name": "competitive_strategy",
            "create_researcher": lambda: create_competitive_researcher(
                google_search_agent
            ),
            "create_formatter": create_competitive_formatter,
            "formatter_doc_id": "competitive_formatter",
            "model_class": CompetitiveAnalysis,
            "graph_builder_class": CompetitiveGraphBuilder,
            "graph_method": "build_competitive_graph",
        },
        {
            "name": "marketing_strategy",
            "create_researcher": lambda: create_marketing_researcher(
                google_search_agent
            ),
            "create_formatter": create_marketing_formatter,
            "formatter_doc_id": "marketing_formatter",
            "model_class": MarketingResearchReport,
            "graph_builder_class": MarketingGraphBuilder,
            "graph_method": "build_marketing_graph",
        },
        {
            "name": "brand_guidelines",
            "create_researcher": lambda: create_brand_researcher(google_search_agent),
            "create_formatter": create_brand_formatter,
            "formatter_doc_id": "brand_formatter",
            "model_class": BrandGuidelines,
            "graph_builder_class": BrandGraphBuilder,
            "graph_method": "build_brand_graph",
        },
    ]

    # Track ProductCategory names for marketing strategy coordination
    product_category_names = []

    # ===== TWO-PHASE EXECUTION: Business first, then parallel =====
    # Phase 1: Execute business_strategy first (if enabled) to extract product categories
    # Phase 2: Execute remaining strategies in parallel with fail-fast behavior

    # Separate business strategy from others
    business_strategy_config = next(
        (s for s in strategy_types if s["name"] == "business_strategy"), None
    )
    other_strategy_configs = [
        s for s in strategy_types if s["name"] != "business_strategy"
    ]

    # PHASE 1: Execute business strategy (if enabled)
    if business_strategy_config and "business_strategy" in enabled_strategies:
        logger.info(
            "\n[PARALLEL] ========== PHASE 1: Executing business_strategy (must run first) =========="
        )
        try:
            strategy_name, doc_content, _used_openai = _execute_single_strategy(
                strategy_config=business_strategy_config,
                strategy_context=context,
                firestore_client=firestore_client,
                google_search_agent=google_search_agent,
                neo4j_ops=neo4j_ops,
                embedding_generator=embedding_generator,
                performance_profiler=performance_profiler,
                analytics_service=analytics_service,
                dry_run=dry_run,
                product_category_names=None,
                override_product_categories=override_product_categories,
            )
            generated_documents[strategy_name] = doc_content

            # Extract ProductCategory names for marketing coordination
            if "product_portfolio" in doc_content:
                try:
                    for category in doc_content["product_portfolio"]:
                        if "product_name" in category:
                            product_category_names.append(category["product_name"])
                        elif "category_name" in category:
                            product_category_names.append(category["category_name"])
                    logger.info(
                        f"[COORDINATION] Extracted {len(product_category_names)} ProductCategory names: {product_category_names}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[COORDINATION] Failed to extract ProductCategory names: {e}"
                    )

        except Exception as e:
            error_msg = f"Business strategy generation failed: {e}"
            logger.error(f"[PARALLEL] ❌ {error_msg}")
            # Fail-fast: If business strategy fails, we might want to continue with others
            # but marketing will use default categories
            logger.warning(
                "[PARALLEL] Continuing with other strategies using default product categories"
            )

    # PHASE 2: Execute remaining strategies in parallel
    remaining_strategies = [
        s for s in other_strategy_configs if s["name"] in enabled_strategies
    ]

    if remaining_strategies:
        logger.info(
            f"\n[PARALLEL] ========== PHASE 2: Executing {len(remaining_strategies)} strategies in parallel =========="
        )
        logger.info(
            f"[PARALLEL] Strategies: {[s['name'] for s in remaining_strategies]}"
        )

        # Use Weave's ThreadPoolExecutor to maintain trace context across threads
        # This ensures all parallel strategy executions nest under the parent trace
        logger.info(
            "[PARALLEL] Using weave.ThreadPoolExecutor for trace-aware parallel execution"
        )

        # Use weave.ThreadPoolExecutor for parallel execution with proper trace nesting
        with weave.ThreadPoolExecutor(
            max_workers=len(remaining_strategies)
        ) as executor:
            # Submit all strategies for parallel execution
            # Context propagation happens automatically in Python 3.12+
            future_to_strategy = {}
            for strat_config in remaining_strategies:
                future = executor.submit(
                    _execute_single_strategy,
                    strategy_config=strat_config,
                    strategy_context=context,
                    firestore_client=firestore_client,
                    google_search_agent=google_search_agent,
                    neo4j_ops=neo4j_ops,
                    embedding_generator=embedding_generator,
                    performance_profiler=performance_profiler,
                    analytics_service=analytics_service,
                    dry_run=dry_run,
                    product_category_names=product_category_names,
                    override_product_categories=override_product_categories,
                )
                future_to_strategy[future] = strat_config["name"]

            # Process results as they complete (fail-fast on first error)
            for future in as_completed(future_to_strategy):
                strategy_name = future_to_strategy[future]
                try:
                    result_name, doc_content, _used_openai = future.result()
                    generated_documents[result_name] = doc_content
                    logger.info(f"[PARALLEL] ✅ {result_name} completed successfully")
                except Exception as e:
                    error_msg = f"{strategy_name} failed: {e}"
                    logger.error(f"[PARALLEL] ❌ {error_msg}")
                    # Fail-fast: Cancel remaining futures and raise
                    logger.error(
                        "[PARALLEL] Cancelling remaining strategies due to failure (fail-fast)"
                    )
                    for remaining_future in future_to_strategy:
                        if not remaining_future.done():
                            remaining_future.cancel()
                    raise RuntimeError(
                        f"Strategy generation failed (fail-fast): {error_msg}"
                    ) from e

        logger.info(
            f"[PARALLEL] ✅ All {len(remaining_strategies)} parallel strategies completed successfully"
        )

    # Don't close Neo4j connection - let driver manage its own lifecycle and handle reconnections
    # Closing causes "Driver closed" errors when strategies take a long time to generate

    logger.info(
        f"\n[PARALLEL] 🎉🎉🎉 Successfully generated all {len(generated_documents)} strategies!"
    )
    return generated_documents


# OLD SEQUENTIAL LOOP CODE REMOVED - Now using two-phase parallel execution above
# The old code has been extracted into _execute_single_strategy() helper function
# Business strategy runs first, then remaining strategies run in parallel with ThreadPoolExecutor


@weave.op(name="execute_strategy_generation")
def execute_strategy_generation(
    company_name: str,
    industry: str,
    websites: str,
    customer_regions: str,
    account_id: str,
    user_id: str,
    annual_ad_budget: float = 0.0,
    project_id: Optional[str] = None,
    uploaded_documents: Optional[List[str]] = None,
    enable_analytics: bool = True,
    enabled_strategies: Optional[List[str]] = None,
    override_product_categories: Optional[List[str]] = None,
    dry_run: bool = False,
) -> str:
    """
    Execute the complete strategy generation process with analytics tracking.

    This function:
    1. Creates the strategy context
    2. Initializes analytics services
    3. Initializes the sequential agent
    4. Runs the agent pipeline with performance tracking
    5. Monitors execution and captures documents
    6. Saves documents to Firestore as they're generated
    7. Tracks costs and performance metrics
    8. Generates optimization recommendations

    Args:
        company_name: Name of the company
        industry: Industry sector
        websites: Comma-separated list of websites
        customer_regions: Comma-separated list of regions
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        annual_ad_budget: Annual advertising budget
        project_id: Optional GCP project ID
        uploaded_documents: List of uploaded document URLs
        enable_analytics: Whether to enable analytics tracking
        enabled_strategies: Optional list of strategy types to generate.
            If None, all strategies are generated.
        override_product_categories: Optional list of product category names
            to use for marketing strategy when business strategy is not run.
        dry_run: If True, skips Firestore, Neo4j, and embedding storage.
            Useful for evaluation runs. Default is False.

    Returns:
        Status message indicating success or failure
    """
    # Initialize analytics services
    analytics_service, performance_profiler, alert_manager, optimization_analyzer = (
        initialize_analytics_services(account_id, project_id, enable_analytics)
    )

    # Start performance tracking
    main_operation = None
    if performance_profiler:
        main_operation = performance_profiler.start_operation(
            agent_name="orchestrator",
            operation="strategy_generation",
            metadata={"company_name": company_name, "account_id": account_id},
        )

    try:
        logger.info(f"[EXECUTION] Starting strategy generation for {company_name}")

        # Initialize Weave if needed (lazy initialization)
        init_weave_if_needed()

        # Create Firestore client
        client = FirestoreClient(project_id=project_id)

        # Create context from inputs
        context = StrategyContext(
            account_id=account_id,
            user_id=user_id,
            company_name=company_name,
            websites=websites.split(",") if websites else [],
            industry=industry,
            customer_regions=customer_regions.split(",") if customer_regions else [],
            annual_ad_budget=annual_ad_budget,
        )

        # Use direct execution instead of sequential workflow
        logger.info("[EXECUTION] Using direct sequential execution (workflow disabled)")

        # Set up session management
        session_service = InMemorySessionService()
        app_name = f"strategy_gen_{account_id}"
        session_user_id = user_id or "system"
        session_id = f"session_{account_id}_{uuid.uuid4().hex[:8]}"

        # Initialize state with empty uploaded documents
        initial_state = {"uploaded_strategy_documents": {}}

        # Create session with initial state
        session = session_service.create_session_sync(
            app_name=app_name,
            user_id=session_user_id,
            session_id=session_id,
            state=initial_state,
        )
        logger.info(f"[EXECUTION] Created session: {session_id}")

        # Set up artifact service using the extracted utility function
        # This simplifies the function and improves testability
        artifact_service = load_uploaded_documents_as_artifacts(
            uploaded_documents=uploaded_documents,
            account_id=account_id,
            session_user_id=session_user_id,
            session_id=session_id,
            project_id=project_id,
        )

        # Verify artifact loading if documents were uploaded
        if uploaded_documents:
            logger.info(
                f"[ARTIFACT_VERIFICATION] Verifying {len(uploaded_documents)} uploaded documents"
            )
            loaded_count = 0

            try:
                # List artifact keys to verify they were loaded
                # Check if we have a GcsArtifactService with sync methods
                if hasattr(artifact_service, "_list_artifact_keys"):
                    # Use the synchronous private method directly
                    artifact_keys = artifact_service._list_artifact_keys(
                        app_name, session_user_id, session_id
                    )
                else:
                    # For InMemoryArtifactService or other async-only services
                    import asyncio

                    async def list_keys():
                        return await artifact_service.list_artifact_keys(
                            app_name=app_name,
                            user_id=session_user_id,
                            session_id=session_id,
                        )

                    # Try to handle async properly
                    try:
                        loop = asyncio.get_running_loop()
                        # If there's a running loop, use nest_asyncio
                        import nest_asyncio

                        nest_asyncio.apply()
                        artifact_keys = asyncio.run(list_keys())
                    except RuntimeError:
                        # No running loop, safe to use asyncio.run
                        artifact_keys = asyncio.run(list_keys())

                # Check for input_strategy_ prefixed artifacts
                strategy_artifacts = [
                    key for key in artifact_keys if key.startswith("input_strategy_")
                ]
                loaded_count = len(strategy_artifacts)

                logger.info(
                    f"[ARTIFACT_VERIFICATION] Found {loaded_count}/{len(uploaded_documents)} strategy artifacts"
                )
                for artifact_key in strategy_artifacts:
                    logger.info(f"  ✓ Loaded: {artifact_key}")

                # Log any missing documents
                if loaded_count < len(uploaded_documents):
                    logger.warning(
                        "[ARTIFACT_VERIFICATION] Some documents may not have loaded successfully"
                    )

            except Exception as e:
                logger.error(f"[ARTIFACT_VERIFICATION] Failed to verify artifacts: {e}")

        # Load uploaded documents from GCS if URLs provided
        from .document_utils import (
            DocumentProcessingError,
            create_document_loading_summary,
            load_documents_from_gcs_urls,
        )

        loaded_docs = {}
        if uploaded_documents:
            # Handle both string and list formats
            if isinstance(uploaded_documents, str):
                uploaded_documents = [
                    url.strip() for url in uploaded_documents.split(",") if url.strip()
                ]

            # Only process if we have GCS URLs
            if uploaded_documents and uploaded_documents[0].startswith("gs://"):
                logger.info(
                    f"[DOCUMENT_LOADING] Loading {len(uploaded_documents)} documents from GCS"
                )

                try:
                    loaded_docs = load_documents_from_gcs_urls(
                        uploaded_documents, project_id
                    )

                    # Log summary
                    summary = create_document_loading_summary(
                        loaded_docs, uploaded_documents
                    )
                    if summary:
                        logger.info(f"[DOCUMENT_LOADING] {summary}")

                except DocumentProcessingError as e:
                    logger.error(f"[DOCUMENT_LOADING] Document processing error: {e}")
                except Exception as e:
                    logger.error(
                        f"[DOCUMENT_LOADING] Failed to load GCS documents: {e}"
                    )

        # Also try loading from artifact service if available
        if (
            uploaded_documents
            and hasattr(artifact_service, "_load_artifact")
            and not loaded_docs
        ):
            logger.info(
                f"[STATE_LOADING] Loading {len(uploaded_documents)} uploaded documents into session state"
            )

            try:
                # Get list of artifact keys
                if hasattr(artifact_service, "_list_artifact_keys"):
                    logger.info(
                        f"[ARTIFACT_KEYS] Calling _list_artifact_keys with app={app_name}, user={session_user_id}, session={session_id}"
                    )
                    artifact_keys = artifact_service._list_artifact_keys(
                        app_name, session_user_id, session_id
                    )
                    logger.info(
                        f"[ARTIFACT_KEYS] Found {len(artifact_keys)} total artifact keys: {artifact_keys}"
                    )

                    # Filter for strategy documents
                    strategy_artifacts = [
                        key
                        for key in artifact_keys
                        if key.startswith("input_strategy_")
                    ]
                    logger.info(
                        f"[ARTIFACT_KEYS] Filtered to {len(strategy_artifacts)} strategy artifacts: {strategy_artifacts}"
                    )

                    # Load each document
                    for artifact_key in strategy_artifacts:
                        try:
                            # Load the artifact content
                            artifact_content = artifact_service._load_artifact(
                                app_name,
                                session_user_id,
                                session_id,
                                artifact_key,
                                None,  # version
                            )

                            if artifact_content:
                                # Extract text content from the Part object
                                if hasattr(artifact_content, "text"):
                                    doc_text = artifact_content.text
                                elif hasattr(artifact_content, "data"):
                                    # Try to decode binary data
                                    try:
                                        doc_text = artifact_content.data.decode(
                                            "utf-8", errors="ignore"
                                        )
                                    except:
                                        doc_text = str(artifact_content.data)
                                else:
                                    doc_text = str(artifact_content)

                                # Store in loaded_docs dictionary
                                loaded_docs[artifact_key] = doc_text
                                logger.info(
                                    f"[STATE_LOADING] Loaded {artifact_key} - {len(doc_text)} chars"
                                )

                        except Exception as e:
                            logger.error(
                                f"[STATE_LOADING] Failed to load {artifact_key}: {e}"
                            )

                    # Update session state with loaded documents
                    if loaded_docs:
                        session.state["uploaded_strategy_documents"] = loaded_docs
                        # Note: InMemorySessionService doesn't have update_session_sync
                        # The state is already updated by reference
                        logger.info(
                            f"[STATE_LOADING] Added {len(loaded_docs)} documents to session state"
                        )
                        for doc_name in loaded_docs:
                            doc_content = loaded_docs[doc_name]
                            logger.info(
                                f"  ✓ {doc_name}: {len(doc_content) if doc_content else 0} chars"
                            )

            except Exception as e:
                logger.error(
                    f"[STATE_LOADING] Failed to load documents into state: {e}"
                )

        # Direct execution doesn't need a runner here - we'll handle it in the direct function
        # Just prepare the execution context

        # Prepare execution message with uploaded documents
        execution_input = f"Generate all 5 strategy documents for {company_name} in the {industry} industry."

        # Add uploaded documents to the initial message if they exist
        if loaded_docs:
            logger.info(
                f"[MESSAGE_PREP] Adding {len(loaded_docs)} uploaded documents to initial message"
            )
            execution_input += "\n\n=== UPLOADED STRATEGY DOCUMENTS ===\n"
            execution_input += "The following strategy documents have been uploaded and should be used as the primary source for your analysis:\n\n"
            for doc_name, doc_content in loaded_docs.items():
                execution_input += f"--- Document: {doc_name} ---\n"
                execution_input += f"{doc_content}\n\n"
                logger.info(
                    f"[MESSAGE_PREP] Added {doc_name} to message - {len(doc_content)} chars"
                )
            execution_input += "=== END OF UPLOADED DOCUMENTS ===\n"
            execution_input += "\nIMPORTANT: Prioritize information from these uploaded documents over web searches. Only search for information not found in these documents."
        else:
            logger.info(
                "[MESSAGE_PREP] No uploaded documents to add to initial message"
            )

        # Check token usage before execution
        abort_msg = check_token_limits_before_execution(
            alert_manager, execution_input, performance_profiler, main_operation
        )
        if abort_msg:
            return abort_msg

        message_content = Content(role="user", parts=[{"text": execution_input}])

        # Run direct sequential execution
        logger.info("[EXECUTION] Starting direct sequential execution")
        start_time = time.time()

        # Execute strategy generation directly
        generated_documents = execute_strategy_generation_direct(
            context=context,
            firestore_client=client,
            analytics_service=analytics_service,
            performance_profiler=performance_profiler,
            alert_manager=alert_manager,
            enabled_strategies=enabled_strategies,
            override_product_categories=override_product_categories,
            dry_run=dry_run,
        )

        execution_time = time.time() - start_time

        # Generate comprehensive execution reports
        report_execution_summary(
            analytics_service,
            performance_profiler,
            optimization_analyzer,
            main_operation,
            execution_time,
            len(generated_documents),
        )

        logger.info(f"[EXECUTION] Completed strategy generation for {company_name}")
        logger.info(
            f"[EXECUTION] Generated documents: {list(generated_documents.keys())}"
        )

        return f"Successfully generated {len(generated_documents)} strategy documents for {company_name}: {', '.join(generated_documents.keys())}"

    except Exception as e:
        error_msg = f"Failed to generate strategy documents: {e}"
        logger.error(error_msg)
        return error_msg


def process_and_save_documents_with_analytics(
    events,
    account_id: str,
    user_id: str,
    firestore_client: FirestoreClient,
    analytics_service: AnalyticsService | None = None,
    performance_profiler: PerformanceProfiler | None = None,
    alert_manager: AlertManager | None = None,
) -> dict[str, Any]:
    """
    Process execution events and save documents to Firestore with analytics tracking.

    This enhanced version includes:
    - Token usage tracking per agent
    - Performance profiling
    - Alert monitoring
    - Cost tracking

    Args:
        events: Generator of execution events from Runner
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        firestore_client: Firestore client for saving documents
        analytics_service: Optional analytics service for tracking
        performance_profiler: Optional performance profiler
        alert_manager: Optional alert manager

    Returns:
        Dictionary of generated documents
    """
    generated_documents = {}
    event_count = 0
    agent_start_times = {}  # Track agent execution times

    for event in events:
        event_count += 1

        # Log event details
        event_info = f"[EVENT #{event_count}]"
        if hasattr(event, "author"):
            event_info += f" author='{event.author}'"

        # Debug: Check all event attributes to find where the LLM response is
        if hasattr(event, "content"):
            logger.info(f"[DEBUG] event.content exists: {type(event.content)}")
            if hasattr(event.content, "parts"):
                logger.info(
                    f"[DEBUG] event.content.parts: {event.content.parts[:500] if isinstance(event.content.parts, (str, list)) else 'complex type'}"
                )
                # Try to extract JSON from parts if it exists
                if isinstance(event.content.parts, list):
                    for part in event.content.parts:
                        if isinstance(part, dict) and "text" in part and part["text"]:
                            text_preview = (
                                str(part["text"])[:500] if part["text"] else "None"
                            )
                            logger.info(f"[DEBUG] Found text in part: {text_preview}")
                        elif hasattr(part, "text") and part.text:
                            text_preview = str(part.text)[:500] if part.text else "None"
                            logger.info(
                                f"[DEBUG] Found text attr in part: {text_preview}"
                            )
        if hasattr(event, "parts"):
            logger.info(
                f"[DEBUG] event.parts exists: {event.parts[:500] if isinstance(event.parts, (str, list)) else 'complex type'}"
            )
        if hasattr(event, "message"):
            logger.info(f"[DEBUG] event.message exists: {type(event.message)}")
        if hasattr(event, "response"):
            logger.info(f"[DEBUG] event.response exists: {type(event.response)}")

            # Track agent performance
            if performance_profiler and event.author:
                if event.author not in agent_start_times:
                    # Start tracking this agent
                    agent_start_times[event.author] = (
                        performance_profiler.start_operation(
                            agent_name=event.author, operation="document_generation"
                        )
                    )

        # Check for token usage in event metadata
        if hasattr(event, "usage_metadata") and event.usage_metadata:
            usage = event.usage_metadata
            prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
            response_tokens = getattr(usage, "candidates_token_count", 0) or 0

            if (prompt_tokens > 0 or response_tokens > 0) and hasattr(event, "author"):
                # Track token usage
                if analytics_service:
                    # Determine model from agent name (reviewers and editors use Flash)
                    model = "gemini-2.5-flash"
                    if "strategist" in event.author.lower():
                        model = "gemini-2.5-pro"

                    analytics_service.track_agent_execution(
                        agent_name=event.author,
                        prompt_tokens=prompt_tokens,
                        response_tokens=response_tokens,
                        model=model,
                        execution_time=0,  # Will be updated when agent completes
                        success=True,
                    )

                # Check token limits
                if alert_manager:
                    total_tokens = prompt_tokens + response_tokens
                    alerts = alert_manager.check_token_usage(
                        current_tokens=total_tokens,
                        max_tokens=TokenEstimator.MAX_OUTPUT_TOKENS,
                        context="agent_output",
                        agent_name=event.author,
                    )
                    if alerts:
                        logger.warning(
                            f"[ALERTS] {len(alerts)} alerts for {event.author}"
                        )

        # Check for documents in BOTH locations to ensure compatibility
        # First check state delta (original implementation location)
        if hasattr(event, "actions") and event.actions:
            if hasattr(event.actions, "state_delta") and event.actions.state_delta:
                state_delta = event.actions.state_delta

                # Log all keys in state_delta for debugging
                if state_delta:
                    logger.info(
                        f"[STATE_DELTA] Keys present: {list(state_delta.keys())[:10]}"
                    )  # Limit to first 10 keys

                # Check for each document type's unique key
                for doc_key, doc_type in DOCUMENT_KEY_MAPPING.items():
                    if doc_key in state_delta:
                        doc_content = state_delta[doc_key]
                        logger.info(
                            f"[DOCUMENT] Found {doc_key} in state_delta for {doc_type}"
                        )

                        # Debug logging to see what we're actually getting
                        logger.info(
                            f"[DEBUG] Raw doc_content type: {type(doc_content)}"
                        )
                        logger.info(
                            f"[DEBUG] Raw doc_content value: {repr(doc_content)[:500]}"
                        )
                        if isinstance(doc_content, str):
                            logger.info(
                                f"[DEBUG] Doc content length: {len(doc_content)}"
                            )
                            logger.info(
                                f"[DEBUG] Doc content is empty: {not doc_content.strip()}"
                            )

                            # If we got empty markdown blocks, try to find JSON in event.content.parts
                            if doc_content.strip() in ["```\n```", "```json\n```", ""]:
                                logger.info(
                                    f"[DEBUG] Got empty content, checking event.content.parts for {doc_type}"
                                )
                                if hasattr(event, "content") and hasattr(
                                    event.content, "parts"
                                ):
                                    for part in event.content.parts:
                                        json_text = None
                                        if (
                                            isinstance(part, dict)
                                            and "text" in part
                                            and part["text"]
                                        ):
                                            json_text = part["text"]
                                        elif hasattr(part, "text") and part.text:
                                            json_text = part.text

                                        if json_text:
                                            text_preview = (
                                                str(json_text)[:200]
                                                if json_text
                                                else "None"
                                            )
                                            logger.info(
                                                f"[DEBUG] Found potential JSON in event.content.parts: {text_preview}"
                                            )
                                            # Try to parse this as JSON
                                            try:
                                                test_parse = json.loads(json_text)
                                                # If it parses, use this instead
                                                doc_content = json_text
                                                logger.info(
                                                    f"[DEBUG] Successfully extracted JSON from event.content.parts for {doc_type}"
                                                )
                                                break
                                            except:
                                                # Not valid JSON, continue searching
                                                pass

                        # Parse the document
                        parsed_doc = parse_document_content(doc_content)

                        if parsed_doc and doc_type not in generated_documents:
                            # Complete performance tracking for this agent
                            if (
                                performance_profiler
                                and hasattr(event, "author")
                                and event.author in agent_start_times
                            ):
                                performance_profiler.end_operation(
                                    agent_start_times[event.author], success=True
                                )
                                del agent_start_times[event.author]

                            # Save to memory
                            generated_documents[doc_type] = parsed_doc
                            logger.info(
                                f"[DOCUMENT] Captured {doc_type} from key {doc_key} - {len(json.dumps(parsed_doc))} bytes"
                            )

                            # Save to Firestore immediately
                            try:
                                result = firestore_client.save_strategy_document_sync(
                                    account_id=account_id,
                                    doc_type=doc_type,
                                    content=parsed_doc,
                                    user_id=user_id,
                                )
                                if result:
                                    logger.info(
                                        f"[SAVE] Successfully saved {doc_type} to Firestore"
                                    )
                                else:
                                    logger.error(
                                        f"[SAVE] Failed to save {doc_type}: save returned False"
                                    )
                            except Exception as e:
                                logger.error(f"[SAVE] Failed to save {doc_type}: {e}")

        # Also check event.state as a fallback (some events might use this)
        if hasattr(event, "state") and event.state:
            # Check for documents in state with unique keys
            for doc_key, doc_type in DOCUMENT_KEY_MAPPING.items():
                if (
                    doc_key in event.state
                    and event.state[doc_key]
                    and doc_type not in generated_documents
                ):
                    doc_content = event.state[doc_key]
                    logger.info(f"[DOCUMENT] Found {doc_type} in event.state")

                    # Parse the document
                    parsed_doc = parse_document_content(doc_content)

                    if parsed_doc:
                        # Complete performance tracking for this agent
                        if (
                            performance_profiler
                            and hasattr(event, "author")
                            and event.author in agent_start_times
                        ):
                            performance_profiler.end_operation(
                                agent_start_times[event.author], success=True
                            )
                            del agent_start_times[event.author]

                        # Save to memory
                        generated_documents[doc_type] = parsed_doc
                        logger.info(
                            f"[DOCUMENT] Captured {doc_type} from event.state - {len(json.dumps(parsed_doc))} bytes"
                        )

                        # Save to Firestore immediately
                        try:
                            result = firestore_client.save_strategy_document_sync(
                                account_id=account_id,
                                doc_type=doc_type,
                                content=parsed_doc,
                                user_id=user_id,
                            )
                            if result:
                                logger.info(
                                    f"[SAVE] Successfully saved {doc_type} to Firestore"
                                )
                            else:
                                logger.error(
                                    f"[SAVE] Failed to save {doc_type}: save returned False"
                                )
                        except Exception as e:
                            logger.error(f"[SAVE] Failed to save {doc_type}: {e}")

    # Complete any remaining performance tracking
    if performance_profiler:
        for agent_name, operation in agent_start_times.items():
            performance_profiler.end_operation(
                operation, success=False, error="Incomplete"
            )

    return generated_documents


def process_and_save_documents(
    events, account_id: str, user_id: str, firestore_client: FirestoreClient
) -> dict[str, Any]:
    """
    Process execution events and save documents to Firestore.

    This function monitors the event stream from the agent execution,
    captures documents as they're generated, and saves them to Firestore.
    Now handles unique output keys for each document type.

    Args:
        events: Generator of execution events from Runner
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        firestore_client: Firestore client for saving documents

    Returns:
        Dictionary of generated documents
    """
    generated_documents = {}
    event_count = 0

    for event in events:
        event_count += 1

        # Log event details
        event_info = f"[EVENT #{event_count}]"
        if hasattr(event, "author"):
            event_info += f" author='{event.author}'"

            # Log specific agent transitions
            if "business_strategy_agent" in str(event.author):
                logger.info(
                    f"[BUSINESS AGENT] Event from business agent: {event.author}"
                )
            elif "competitive_strategy_agent" in str(event.author):
                logger.info(
                    f"[COMPETITIVE AGENT] Event from competitive agent: {event.author}"
                )
            elif "customer_strategy_agent" in str(event.author):
                logger.info(
                    f"[CUSTOMER AGENT] Event from customer agent: {event.author}"
                )
            elif "marketing_strategy_agent" in str(event.author):
                logger.info(
                    f"[MARKETING AGENT] Event from marketing agent: {event.author}"
                )
            elif "brand_" in str(event.author):
                logger.info(f"[BRAND AGENT] Event from brand agent: {event.author}")

        logger.info(event_info)

        # Check for documents in state delta
        if hasattr(event, "actions") and event.actions:
            if hasattr(event.actions, "state_delta") and event.actions.state_delta:
                state_delta = event.actions.state_delta

                # Log all keys in state_delta for debugging
                if state_delta:
                    logger.info(
                        f"[STATE_DELTA] Keys present: {list(state_delta.keys())[:10]}"
                    )  # Limit to first 10 keys

                # Check for each document type's unique key
                for doc_key, doc_type in DOCUMENT_KEY_MAPPING.items():
                    if doc_key in state_delta:
                        doc_content = state_delta[doc_key]
                        logger.info(
                            f"[DOCUMENT] Found {doc_key} in state_delta for {doc_type}"
                        )

                        # Debug logging to see what we're actually getting
                        logger.info(
                            f"[DEBUG] Raw doc_content type: {type(doc_content)}"
                        )
                        logger.info(
                            f"[DEBUG] Raw doc_content value: {repr(doc_content)[:500]}"
                        )
                        if isinstance(doc_content, str):
                            logger.info(
                                f"[DEBUG] Doc content length: {len(doc_content)}"
                            )
                            logger.info(
                                f"[DEBUG] Doc content is empty: {not doc_content.strip()}"
                            )

                            # If we got empty markdown blocks, try to find JSON in event.content.parts
                            if doc_content.strip() in ["```\n```", "```json\n```", ""]:
                                logger.info(
                                    f"[DEBUG] Got empty content, checking event.content.parts for {doc_type}"
                                )
                                if hasattr(event, "content") and hasattr(
                                    event.content, "parts"
                                ):
                                    for part in event.content.parts:
                                        json_text = None
                                        if (
                                            isinstance(part, dict)
                                            and "text" in part
                                            and part["text"]
                                        ):
                                            json_text = part["text"]
                                        elif hasattr(part, "text") and part.text:
                                            json_text = part.text

                                        if json_text:
                                            text_preview = (
                                                str(json_text)[:200]
                                                if json_text
                                                else "None"
                                            )
                                            logger.info(
                                                f"[DEBUG] Found potential JSON in event.content.parts: {text_preview}"
                                            )
                                            # Try to parse this as JSON
                                            try:
                                                test_parse = json.loads(json_text)
                                                # If it parses, use this instead
                                                doc_content = json_text
                                                logger.info(
                                                    f"[DEBUG] Successfully extracted JSON from event.content.parts for {doc_type}"
                                                )
                                                break
                                            except:
                                                # Not valid JSON, continue searching
                                                pass

                        # Parse the document
                        parsed_doc = parse_document_content(doc_content)

                        if parsed_doc:
                            # Save to memory
                            generated_documents[doc_type] = parsed_doc
                            logger.info(
                                f"[DOCUMENT] Captured {doc_type} from key {doc_key} - {len(json.dumps(parsed_doc))} bytes"
                            )

                            # Save to Firestore immediately
                            try:
                                result = firestore_client.save_strategy_document_sync(
                                    account_id=account_id,
                                    doc_type=doc_type,
                                    content=parsed_doc,
                                    user_id=user_id,
                                )

                                if result:
                                    logger.info(
                                        f"[FIRESTORE] Successfully saved {doc_type}"
                                    )
                                else:
                                    logger.error(
                                        f"[FIRESTORE] Failed to save {doc_type}"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"[FIRESTORE] Error saving {doc_type}: {e}"
                                )
                        else:
                            logger.error(
                                f"[DOCUMENT] Failed to parse content for {doc_type} from key {doc_key}"
                            )

    # Log final summary
    logger.info(f"[EXECUTION SUMMARY] Total events processed: {event_count}")
    logger.info(
        f"[EXECUTION SUMMARY] Documents generated: {list(generated_documents.keys())}"
    )
    expected_docs = [
        "business_strategy",
        "competitive_strategy",
        "customer_strategy",
        "marketing_strategy",
        "brand_guidelines",
    ]
    missing_docs = [doc for doc in expected_docs if doc not in generated_documents]
    if missing_docs:
        logger.warning(f"[EXECUTION SUMMARY] Missing documents: {missing_docs}")

    return generated_documents


def parse_document_content(doc_content: Any) -> dict | None:
    """
    Parse document content from JSON string or dict.

    Args:
        doc_content: Raw document content (may be JSON string or dict)

    Returns:
        Parsed document dictionary or None if parsing fails
    """
    # If already a dict, return it
    if isinstance(doc_content, dict):
        return doc_content

    # If string, try to parse as JSON using BAML parser
    if isinstance(doc_content, str):
        # Try enhanced parser first - it handles markdown wrapping and other issues
        try:
            from .enhanced_json_parser import EnhancedJsonParser

            parser = EnhancedJsonParser()
            result = parser.parse_json(doc_content, schema=None)
            if result:
                logger.info("[DOCUMENT] Successfully parsed JSON using enhanced parser")
                return result
        except Exception as e:
            logger.warning(
                f"[DOCUMENT] Enhanced parsing failed, falling back to standard parsing: {e}"
            )

        # Fallback to original cleaning method
        doc_content = clean_json_string(doc_content)

        try:
            return json.loads(doc_content)
        except json.JSONDecodeError as e:
            logger.error(f"[DOCUMENT] Failed to parse JSON: {e}")
            return None

    # Unknown type
    logger.warning(f"[DOCUMENT] Unknown content type: {type(doc_content)}")
    return None


def clean_json_string(content: str) -> str:
    """
    Clean JSON string by removing markdown code blocks and fixing escape sequences.

    Args:
        content: Raw JSON string that may contain markdown or invalid escapes

    Returns:
        Cleaned JSON string
    """
    import re

    # Remove markdown code blocks if present
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]  # Remove ```json
    if content.endswith("```"):
        content = content[:-3]  # Remove ```

    # Fix common JSON issues
    # Replace single backslashes that aren't part of valid escape sequences
    # Valid escapes are: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", content.strip())

    return cleaned


# Create the main strategy agent for deployment
def create_strategy_agent_for_deployment():
    """
    Create a wrapper agent for deployment that handles strategy generation requests.
    """
    return Agent(
        name="strategy_orchestrator",
        model="gemini-2.0-flash",
        instruction="""You coordinate strategy document generation.

When you receive a request to generate strategy documents, you MUST use the execute_strategy_generation tool.

Look for messages that contain parameters like:
- company_name
- industry
- websites
- customer_regions
- account_id
- user_id
- annual_ad_budget
- project_id
- enabled_strategies (optional: list of strategies to generate)
- override_product_categories (optional: product categories for marketing strategy)
- dry_run (optional: true/false - if true, skips storage for evaluation runs)

Extract these parameters from the message and call execute_strategy_generation with them.

For example, if you receive:
"Please execute strategy generation with these parameters:
- company_name: Example Corp
- industry: Technology
- websites: example.com
- customer_regions: USA,Europe
- account_id: acc_123
- user_id: user_456
- annual_ad_budget: 100000
- project_id: ken-e-dev
- enabled_strategies: business_strategy,marketing_strategy
- override_product_categories: Core Products,Premium Services
- dry_run: true"

You should call execute_strategy_generation(
    company_name="Example Corp",
    industry="Technology",
    websites="example.com",
    customer_regions="USA,Europe",
    account_id="acc_123",
    user_id="user_456",
    annual_ad_budget=100000.0,
    project_id="ken-e-dev",
    enabled_strategies=["business_strategy", "marketing_strategy"],
    override_product_categories=["Core Products", "Premium Services"],
    dry_run=True
)

IMPORTANT:
- If enabled_strategies is provided, convert the comma-separated string to a list of strings
- If override_product_categories is provided, convert the comma-separated string to a list of strings
- If dry_run is provided as "true" or "True", convert to boolean True; if "false" or "False", convert to boolean False
- If enabled_strategies, override_product_categories, or dry_run are not present in the message, do NOT include them in the function call

ALWAYS use the execute_strategy_generation tool when asked to generate strategies.
Do NOT just respond with text - actually execute the tool.""",
        tools=[execute_strategy_generation],
    )


# Create the agent and app for deployment
strategy_agent = create_strategy_agent_for_deployment()

try:
    # Wrap with AdkApp for deployment
    # Disable Cloud Tracing due to OpenTelemetry instrumentation bug with Pydantic models
    # Weave tracing (via @weave.op decorators) is still fully functional
    app = reasoning_engines.AdkApp(agent=strategy_agent, enable_tracing=False)
    logger.info("✅ Strategy Agent ready for deployment")
except Exception as e:
    logger.error(f"Failed to create Strategy Agent app: {e}")
    app = None


__all__ = [
    "app",
    "execute_strategy_generation",
    "execute_strategy_generation_direct",
    "extract_document_sections",
    "strategy_agent",
]

"""
Sub-agents for strategy document creation and refinement.
Implements the exact agents from KEN_E____ADK____Iterative_Strategy_Agent.ipynb
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import google_search, ToolContext, VertexAiSearchTool, AgentTool

from models import StrategyDocument, ReviewFeedback, EditRequest, StrategyRequest

logger = logging.getLogger(__name__)


# Configuration - will be loaded from environment or Firestore
DATASTORE_ID = "projects/ken-e-dev/locations/us-central1/collections/default_collection/dataStores/strategy-docs-acc-test-account_1755429117747"


def exit_loop(tool_context: ToolContext, final_document: str = ""):
    """Call this function ONLY when the document is approved, signaling the loop should end."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    
    # Print the final strategy document before exiting
    print("\n" + "="*60)
    print("🎯 FINAL APPROVED STRATEGY DOCUMENT:")
    print("="*60)
    
    if final_document:
        # TODO: Save the updated document back to Firestore
        print(final_document)
    else:
        print("⚠️ No final document provided to exit_loop function")
    
    print("="*60 + "\n")
    
    tool_context.actions.escalate = True
    return {"status": "Loop terminated successfully", "document_displayed": bool(final_document)}


def create_internal_search_agent() -> Agent:
    """
    Create the internal search agent that uses Vertex AI Search.
    """
    return Agent(
        name="internal_search_agent",
        model="gemini-2.0-flash",
        instruction="Answer questions using Vertex AI Search to find information from internal documents. Always cite sources when available.",
        description="Enterprise document search assistant with Vertex AI Search capabilities",
        tools=[VertexAiSearchTool(data_store_id=DATASTORE_ID)]
    )


def create_google_search_agent() -> Agent:
    """
    Create the Google search agent for external research.
    """
    return Agent(
        name="google_search_agent",
        model="gemini-2.0-flash",
        instruction="Answer questions using Google Search to find information on the Internet. Always cite sources when available.",
        description="Internet research assistant with Google Search capabilities",
        tools=[google_search]
    )


def create_strategist_agent() -> Agent:
    """
    Create the strategist agent that proposes an initial strategy doc.
    This agent uses an advanced model and takes time to think carefully.
    """
    # Create the search agents that strategist will use
    internal_search_agent = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="strategist_agent",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search_agent), AgentTool(agent=google_search_agent)],
        description="A strategic thinking expert that creates or updates marketing strategy documents based on new information and best practice guidelines.",
        instruction="""
# ROLE & GOAL
You are a Strategic Marketing Expert who may be given one of the two following tasks:
1. Create a comprehensive business strategy document
2. Update an existing business strategy document based on new information

CRITICAL:
- You MUST output a complete JSON strategy document that follows the provided BEST PRACTICES schema exactly.

# TOOLS
- internal_search_agent: Searches through internal business strategy documents (including the business plan)
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- A query describing what to do
- BEST PRACTICES: A JSON schema that defines the exact structure your output must follow
- NEW INFORMATION: Details about the company to research and analyze
- THE EXISTING STRATEGY DOCUMENT: You will only receive this if you are required to update an existing document. Otherwise you will know to create a new document.

# PERSONA
You are an expert strategist, meticulous in your analysis and precise in your writing. You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:

1. **Analyze All Inputs:** Begin by thoroughly reading and understanding the query and all provided documents (`NEW INFORMATION`, `BEST PRACTICES`, and `strategy_document` if available).

2. **Determine Workflow:** Evaluate whether an `strategy_document` was provided. This determines your next steps.

3.A. **Workflow A: Update Existing Document**
   - If an `strategy_document` is provided, your task is to update it.
   - Cross-reference the `NEW INFORMATION` with the `strategy_document`.
   - Identify all new concepts from the `NEW INFORMATION` that must be integrated.
   - Identify all concepts in the `strategy_document` that are now obsolete or irrelevant due to the `NEW INFORMATION` and must be removed.
   - Meticulously rewrite and restructure the document to integrate the new concepts and remove the obsolete ones, ensuring the final document is coherent and flows logically.

3.B. **Workflow B: Create New Document**
   - If no `strategy_document` is provided, your task is to create one from scratch.
   - **MANDATORY**: Use the `google_search` tool extensively to research each item defined in the BEST PRACTICES.
   - Search for multiple queries related to each section you need to complete.
   - Synthesize your research findings into a complete, new strategy document that is well referenced with the URL's of the sources.
   - **MANDATORY**: You MUST add references any time you insert information that was found through one of your search agents so that the source document can be reviewed later.

4. **Research Requirements:**
   - For EVERY section of the document that requires external information, you MUST search for it
   - **MANDATORY**: You MUST add references any time you insert information that was found through one of your search agents so that the source document can be reviewed later.
   - Use specific, targeted search queries like:
     * "[Company name] mission vision values"
     * "[Company name] financial performance revenue"
     * "[Company name] competitors industry analysis"
     * "[Industry] market size trends 2025"
   - If you cannot find information needed for a section, insert the text: "requires further research"

6. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the `BEST PRACTICES`.
   - Ensure every section, heading, and requirement from the guide is perfectly represented in your output document.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document
- Your final output MUST be the complete and final strategy document with ALL sections filled out based on your research.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the specifications in the `BEST PRACTICES`.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT leave any placeholder text or "requires further research" statements.

Remember: Your sole job is to output the complete JSON strategy document. Nothing else.
""",
        output_key="updated_strategy_doc"
    )


def create_reviewer_agent() -> Agent:
    """
    Create the reviewer agent that critiques the strategy doc based on reviewer guidelines.
    This agent uses a smaller, faster model.
    """
    return Agent(
        name="reviewer_agent",
        model="gemini-2.0-flash",
        tools=[],
        description="An expert content editor that reviews a strategy document against a set of guidelines to ensure completeness and quality.",
        instruction="""
# ROLE & GOAL
You are an experienced and meticulous Content Editor. Your primary goal is to review a draft strategy document against a provided set of guidelines and determine if all criteria are met.

# INPUTS
You will receive three key pieces of information:
- BEST PRACTICES: A JSON schema that defines the exact structure your output must follow.
- updated_strategy_doc: The draft strategy document that requires your review.
- REVIEWER GUIDELINES: A document containing the specific rules and criteria you must use for the review.

# PROCESS
1.  Thoroughly read and completely understand all criteria listed in the `REVIEWER GUIDELINES` and `BEST PRACTICES`.
2.  Systematically compare the `updated_strategy_doc` against each guideline.
3.  For each guideline, determine if the document satisfies the requirement. If information is unavailble for a section, the text should read: "requires further research"
4.  After checking all guidelines, make a final decision.

# OUTPUT REQUIREMENTS
Your response must strictly follow one of two formats:

- **IF** any of the guidelines are not met, you MUST provide a constructive critique with specific, actionable instructions for what needs to be fixed.
    - Example: 'This document is missing a required section. Include a short summary of the objective.'
    - Example: 'The "Key Metrics" section lacks quantifiable KPIs. Please add at least three measurable key performance indicators.'

- **ELSE**, if the document perfectly meets all criteria in the guidelines, you MUST respond with the exact phrase: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_editor_agent() -> Agent:
    """
    Create the editor agent that refines the strategy doc or exits the loop.
    This agent uses a fast model for making careful edits.
    """
    # Create the search agents that editor will use
    internal_search_agent = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="editor_agent",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search_agent), AgentTool(agent=google_search_agent), exit_loop],
        description="An expert marketing agent that refines and edits strategy documents based on specific criticism to ensure they meet best practice standards.",
        instruction="""
# ROLE & GOAL
You are a Senior Marketing Strategist at a top-tier marketing agency. Your primary goal is to meticulously edit a draft marketing strategy document based on feedback from a reviewer.

# TOOLS
- internal_search_agent: Searches through internal business strategy documents (including the business plan)
- google_search_agent: Uses Google search to find relevant information on the Internet
- exit_loop: A tool that signals the loop should terminate

# CRITICAL INSTRUCTION
You MUST check the criticism first. If the criticism is exactly "The document meets all criteria." then you MUST immediately call the exit_loop tool with the current document and provide NO other text output.

# PROCESS
1. **Review the Strategy Document**: Begin by thoroughly reading and understanding the provided strategy document (`updated_strategy_doc`).

2. **Check Criticism First**: Read the criticism input carefully.

3. **Exit Condition**:
   - IF the criticism is exactly the text "The document meets all criteria." (without quotes), then:
     * Call the exit_loop tool immediately and pass the current updated_strategy_doc as the final_document parameter
     * Provide NO text output at all
     * Do NOT edit the document

3. **Edit Condition**:
   - IF the criticism contains any other text, then:
     * Attempt to apply the requested changes to the document
     * Use the BEST PRACTICES to understand the description for each section
     * **MANDATORY**: Use the `google_search_agent` tool extensively to find new information on the Internet where necessary. Search for multiple queries related to each section you need to complete and synthesize your findings. If you cannot find information needed for a section, YOU MUST insert the text: "requires further research". Do NOT add information to the document unless you are certain that it is correct.
     * Use the 'internal_search_agent' tool to review the businesses internal strategy documents (including the business plan).
     * **MANDATORY**: You MUST add references any time you insert information that was found through one of your search agents so that the source document can be reviewed later.
     * Return the fully revised document

# INPUTS
You will receive:
- `updated_strategy_doc`: The current version of the document
- `BEST PRACTICES`: The JSON schema guide for structure
- `criticism`: The feedback to address

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call exit_loop(final_document=updated_strategy_doc) and provide NO text output
- If editing: Return ONLY the complete revised document (no explanations)
""",
        output_key="updated_strategy_doc"
    )


def create_refinement_loop() -> LoopAgent:
    """
    Create the LoopAgent that orchestrates the critique-refine cycle.
    """
    reviewer_agent = create_reviewer_agent()
    editor_agent = create_editor_agent()
    
    return LoopAgent(
        name="refinement_loop",
        sub_agents=[reviewer_agent, editor_agent],
        description="Passes the 'updated_strategy_doc' generated by the strategist_agent to the reviewer agent and enables up to 3 rounds of edits.",
        max_iterations=3
    )


def create_iterative_strategy_agent() -> SequentialAgent:
    """
    Create the main SequentialAgent that puts it all together.
    """
    strategist_agent = create_strategist_agent()
    refinement_loop = create_refinement_loop()
    
    return SequentialAgent(
        name="iterative_strategy_agent",
        sub_agents=[strategist_agent, refinement_loop],
        description="A workflow that iteratively creates and refines a strategy document."
    )


# Export the main strategy agent
strategy_agent = create_iterative_strategy_agent()
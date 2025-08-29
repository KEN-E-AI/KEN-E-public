# Google ADK (Agent Developer Kit) Deployment Guidelines

## Executive Summary

This document provides comprehensive guidelines for developing agents that successfully deploy to Google's Vertex AI Agent Engine (ADK). It is based on extensive analysis of deployment failures encountered when attempting to enhance the `strategy-supervisor-20250826-171439` agent with advanced ADK patterns.

**Key Finding**: Many advanced ADK patterns that work locally fail in the deployed environment. Success requires using simpler, more direct patterns that avoid complex agent orchestration features.

---

## Table of Contents

1. [Patterns That Work in Deployment](#patterns-that-work-in-deployment)
2. [Patterns That Fail in Deployment](#patterns-that-fail-in-deployment)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Recommended Architecture](#recommended-architecture)
5. [Incremental Enhancement Strategy](#incremental-enhancement-strategy)
6. [Testing Guidelines](#testing-guidelines)
7. [Troubleshooting Deployment Issues](#troubleshooting-deployment-issues)

---

## Patterns That Work in Deployment ✅

### 1. Simple Agent Creation
```python
# ✅ GOOD: Simple agent with basic configuration
agent = Agent(
    name="business_strategist",
    model="gemini-2.5-pro",
    instruction="Create a business strategy document",
    tools=[google_search],
    description="Business strategy expert"
)
```

### 2. Direct Tool Usage
```python
# ✅ GOOD: Direct tool functions
from google.adk.tools import google_search, AgentTool

def my_tool(tool_context: ToolContext):
    """Simple tool function."""
    return {"result": "success"}
```

### 3. AgentTool Wrapping
```python
# ✅ GOOD: Wrapping agents as tools
search_agent = Agent(name="searcher", model="gemini-2.5-flash", ...)
tool = AgentTool(agent=search_agent)
```

### 4. Sequential Agent (Basic)
```python
# ✅ GOOD: Simple sequential execution
agents = [agent1, agent2, agent3]
sequential = SequentialAgent(
    name="orchestrator",
    sub_agents=agents,
    description="Sequential execution"
)
```

### 5. Generate Content Config
```python
# ✅ GOOD: Configuration via generate_content_config
agent = Agent(
    name="agent",
    model="gemini-2.5-pro",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=65535
    )
)
```

### 6. Simple State Management
```python
# ✅ GOOD: Basic output_key for state passing
agent = Agent(
    name="agent",
    output_key="strategy_doc",
    instruction="Access previous: {state['previous_doc']}"
)
```

### 7. Firestore Integration
```python
# ✅ GOOD: Direct Firestore operations
from google.cloud import firestore

def save_document(doc_id: str, content: dict):
    db = firestore.Client()
    db.collection("docs").document(doc_id).set(content)
```

---

## Patterns That Fail in Deployment ❌

### 1. BuiltInPlanner with Thinking Config
```python
# ❌ BAD: Planner with thinking_config fails in deployment
from google.adk.planners import BuiltInPlanner

agent = Agent(
    name="agent",
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            thinking_budget=16000
        )
    )
)
# Error: "Thinking config should be set via LlmAgent.planner"
```

### 2. Complex LoopAgent Patterns
```python
# ❌ BAD: LoopAgent with refinement cycles fails
loop_agent = LoopAgent(
    name="refiner",
    agent=base_agent,
    max_iterations=3,
    loop_condition="quality < threshold"
)
# Error: Agent initialization fails in deployment
```

### 3. Runner Class Usage
```python
# ❌ BAD: Runner requires complex initialization
from google.adk import Runner

runner = Runner(
    app_name="strategy_app",  # Required but unclear
    session_service=InMemorySessionService()  # Complex setup
)
runner.run(user_id="user", session_id="session", new_message=message)
# Error: Missing required parameters or initialization fails
```

### 4. Nested Agent Creation
```python
# ❌ BAD: Creating agents inside other agents
def create_parent_agent():
    def create_child():
        return Agent(...)  # Agent creation inside parent

    return Agent(
        tools=[create_child()]  # Dynamic agent creation
    )
# Error: Agent creation fails during deployment initialization
```

### 5. Complex State Dependencies
```python
# ❌ BAD: Complex state manipulation
agent = Agent(
    instruction="Modify {state['complex_nested']['deep']['value']}"
)
# Error: State access patterns fail in deployment
```

### 6. Direct Thinking Config
```python
# ❌ BAD: Thinking config in generate_content_config
agent = Agent(
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(...)  # Fails
    )
)
```

### 7. Session-Based Patterns
```python
# ❌ BAD: Session management patterns
from google.adk.session import InMemorySessionService

session_service = InMemorySessionService()
session_id = session_service.create_session()
# Error: Session services not properly initialized in deployment
```

---

## Root Cause Analysis

### Why These Patterns Fail

1. **Environment Differences**
   - Local development has full Python runtime
   - Deployment environment has restricted execution context
   - Some ADK features are experimental or not fully supported

2. **Initialization Order**
   - Complex patterns require specific initialization sequences
   - Deployment environment may not support dynamic agent creation
   - Circular dependencies cause initialization failures

3. **Model Configuration Conflicts**
   - Newer model features (thinking, planning) have specific requirements
   - Configuration must be done through proper channels (planner vs generate_content_config)
   - Version mismatches between local and deployment ADK

4. **State Management Limitations**
   - Complex state transformations don't serialize properly
   - Nested state access patterns fail in distributed execution
   - Session management requires infrastructure not available in deployment

5. **Import and Module Resolution**
   - Relative imports fail in deployment
   - Dynamic imports during execution not supported
   - Module aliasing causes resolution issues

---

## Recommended Architecture

### 1. Flat Agent Structure
```python
# Create all agents at module level
business_agent = create_business_agent()
competitive_agent = create_competitive_agent()
customer_agent = create_customer_agent()

# Simple orchestrator
orchestrator = SequentialAgent(
    sub_agents=[business_agent, competitive_agent, customer_agent]
)
```

### 2. Tool-Based Composition
```python
# Wrap complex logic in tool functions
def process_strategy_request(query: str) -> str:
    """Main entry point as a tool."""
    data = json.loads(query)
    # Direct processing logic
    return json.dumps(result)

# Simple agent with tool
supervisor = Agent(
    tools=[process_strategy_request],
    instruction="Route requests appropriately"
)
```

### 3. Synchronous Firestore Operations
```python
# Use sync versions for agent context
def save_document_sync(doc_id: str, content: dict):
    """Synchronous save for use in agents."""
    db = firestore.Client()
    db.collection("docs").document(doc_id).set(content)
    return True
```

### 4. Configuration Management
```python
# Centralize configuration
CONFIG = {
    "model": "gemini-2.5-pro",
    "temperature": 0.2,
    "max_tokens": 65535
}

def create_agent(name: str) -> Agent:
    return Agent(
        name=name,
        model=CONFIG["model"],
        generate_content_config=types.GenerateContentConfig(
            temperature=CONFIG["temperature"],
            max_output_tokens=CONFIG["max_tokens"]
        )
    )
```

---

## Incremental Enhancement Strategy

### Phase 1: Baseline Deployment ✅
1. Start with working `strategy-supervisor-20250826-171439`
2. Verify deployment succeeds
3. Test all existing functionality
4. Document current capabilities

### Phase 2: Model Upgrades 🔄
1. Update models from `gemini-2.0-flash` to `gemini-2.5-flash`
2. Update from `gemini-2.0-pro` to `gemini-2.5-pro`
3. Test each model change individually
4. Deploy and verify after each change

### Phase 3: Instruction Improvements 📝
1. Enhance agent instructions for better output
2. Add specific formatting requirements
3. Include research guidance
4. Test locally first, then deploy

### Phase 4: Tool Enhancements 🔧
1. Add new search tools if needed
2. Enhance existing tool functions
3. Add error handling and retries
4. Deploy incrementally

### Phase 5: Simple Orchestration 🎯
1. Add basic sequential patterns
2. Implement simple state passing
3. Add output validation
4. Avoid complex loops or planners

### What NOT to Do ⛔
- Don't add BuiltInPlanner or thinking_config
- Don't use LoopAgent for refinement
- Don't create nested agent structures
- Don't use Runner class
- Don't implement complex state management
- Don't use session-based patterns

---

## Testing Guidelines

### 1. Local Testing
```bash
# Test locally first
cd app/adk
python test_supervisor.py

# Check for import errors
python -c "from supervisor_enhanced import *"
```

### 2. Deployment Testing
```bash
# Deploy to development first
./deploy_supervisor_enhanced.sh

# Test with minimal request
python test_deployed_agent.py

# Check logs for errors
gcloud logging read "resource.type=aiplatform.googleapis.com/ReasoningEngine"
```

### 3. Error Patterns to Watch
- "Thinking config should be set via LlmAgent.planner"
- "No module named 'google.adk'"
- "Failed to initialize agent"
- "Complex agents not available"
- Empty responses from API

---

## Troubleshooting Deployment Issues

### Issue: Agent Returns Empty Response
**Cause**: Agent creation failed during deployment
**Solution**: Simplify agent creation, remove complex patterns

### Issue: "Thinking config should be set via LlmAgent.planner"
**Cause**: Using thinking_config incorrectly
**Solution**: Remove thinking_config entirely or use older model without it

### Issue: "Complex agents not available"
**Cause**: Import errors or initialization failures
**Solution**: Check imports, use absolute paths, simplify agent structure

### Issue: JSON Wrapped in Markdown
**Cause**: Agent returning formatted output
**Solution**: Update instructions to return raw JSON, add parsing in API

### Issue: Nested Response Structure
**Cause**: Tool wrapping adds layers
**Solution**: Unwrap response in API, check for wrapped keys

---

## Best Practices Summary

### DO ✅
1. Use simple, flat agent structures
2. Test locally before deploying
3. Deploy incrementally with small changes
4. Use direct tool functions
5. Handle errors gracefully
6. Use synchronous operations in agents
7. Keep state management simple
8. Use absolute imports

### DON'T ❌
1. Use BuiltInPlanner or thinking_config
2. Create agents dynamically
3. Use complex orchestration patterns
4. Rely on session management
5. Use nested state structures
6. Mix async/sync operations
7. Use relative imports
8. Deploy without testing

---

## Conclusion

Success with Google ADK deployment requires restraint and simplicity. While the platform supports advanced features locally, the deployment environment has significant limitations. By following these guidelines and using incremental enhancement, you can build reliable, deployed agents that provide value without encountering deployment failures.

The key insight: **Start simple, test everything, enhance gradually.**

---

## Next Steps

1. Delete all changes in the current branch
2. Create new branch from main
3. Start with working `strategy-supervisor-20250826-171439`
4. Apply enhancements following these guidelines
5. Test each change thoroughly
6. Deploy only proven patterns

Remember: A working simple agent is infinitely more valuable than a complex agent that won't deploy.

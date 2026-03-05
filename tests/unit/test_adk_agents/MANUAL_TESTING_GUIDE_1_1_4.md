# Manual Testing Guide: Story 1.1.4 - Eliminate Per-Message Context Injection

## Prerequisites
- API server running: `cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend running: `cd frontend && npm run dev:development`
- Access to Weave dashboard (W&B) for trace inspection
- A valid user account with at least one organization/account in Neo4j
- App URL: http://localhost:8080

## Test 1: Company News Query Works Correctly (AC 6)

**Steps:**
1. Navigate to http://localhost:8080 and log in
2. Select an account that has company news data
3. Open the chat interface
4. Type: "What are the latest company news updates?"
5. Wait for the response

**Expected Results:**
- [ ] KEN-E responds with relevant company news information
- [ ] Response includes specific news items from the knowledge graph
- [ ] No error messages or "context not found" errors appear
- [ ] Response time is under 5 seconds

## Test 2: Google Analytics Query Works Correctly (AC 6)

**Steps:**
1. In the same or new chat session, select an account with GA credentials configured
2. Type: "What is our website traffic this month?"
3. Wait for the response

**Expected Results:**
- [ ] KEN-E responds with GA data (traffic metrics, page views, etc.)
- [ ] No "cancel scope" or MCP session errors in the response
- [ ] GA property ID is correctly passed to the GA sub-agent
- [ ] Response time is under 5 seconds

## Test 3: Organization Context in Weave Trace (AC 1, 2, 5)

**Steps:**
1. After completing Tests 1 and 2, open the Weave dashboard
2. Find the trace for the most recent chat interaction
3. Inspect the LLM call's system/instruction prompt
4. Inspect the user messages in the conversation history

**Expected Results:**
- [ ] Organization context (company name, industry, brand info) appears in the agent's **instruction/system prompt** (dynamic instruction callable)
- [ ] Organization context does NOT appear prepended to the **user message** content
- [ ] For multi-turn conversations, the org context appears only once in the instruction, NOT duplicated in each user message
- [ ] The instruction includes sections like company overview, brand guidelines, customer regions (from Neo4j)

## Test 4: Multi-Turn Conversation Token Efficiency (AC 5)

**Steps:**
1. Start a new chat session
2. Send message 1: "Tell me about our company"
3. Wait for response
4. Send message 2: "What about our competitors?"
5. Wait for response
6. Send message 3: "Summarize our marketing strategy"
7. Check Weave traces for all 3 messages

**Expected Results:**
- [ ] Message 1 trace shows org context in instruction, NOT in user message
- [ ] Message 2 trace shows the same org context in instruction; user message 2 does NOT contain org context
- [ ] Message 3 trace shows the same; no org context duplication in message history
- [ ] Total token count for message 3 should be ~3,000 tokens less than it would be if context were injected per-message (3 messages x ~1,500 tokens)

## Verification Checklist Summary

| Test | What It Validates | AC |
|------|-------------------|----|
| Test 1 | Company news queries still work after context injection changes | AC 6 |
| Test 2 | GA queries still work, no cancel scope errors | AC 6 |
| Test 3 | Context delivered via dynamic instruction, not user messages | AC 1, 2 |
| Test 4 | Token savings across multi-turn conversations | AC 5 |

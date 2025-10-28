# Plan: Use Firestore Instructions in OpenAI Fallback

## Problem Statement

When the Gemini formatter fails and falls back to OpenAI, the Firestore instructions that were successfully loaded are discarded. The OpenAI fallback uses hardcoded generic instructions instead.

**Current Flow:**
1. Formatter agent loads instructions from Firestore ✅
2. Gemini formatter executes but fails ❌
3. Falls back to OpenAI with hardcoded instructions ❌
4. Firestore instructions are lost ❌

**Desired Flow:**
1. Formatter agent loads instructions from Firestore ✅
2. Gemini formatter executes but fails ❌
3. Falls back to OpenAI with Firestore instructions ✅
4. Only use hardcoded instructions if Firestore returned nothing ✅

## Root Cause Analysis

### orchestrator.py (lines 639-724)

**Line 639**: Formatter agent is created with Firestore config loaded
```python
formatter = strategy_config["create_formatter"]()
```

**Line 712**: OpenAI fallback is called without Firestore instructions
```python
formatted_output = format_with_openai(
    research_data=research_data,
    model_class=model_class,
    strategy_type=strategy_name,
    source_urls=source_urls,
)
```

**Problem**: The `formatter` object contains the Firestore instructions in `formatter.system_instructions`, but this is not passed to `format_with_openai()`.

### openai_formatter.py (lines 34-91)

**Line 75**: Hardcoded instructions are always used
```python
messages=[
    {
        "role": "system",
        "content": f"You are a {strategy_type} formatter. Format the research into a structured {strategy_type} document matching the provided schema exactly..."
    }
]
```

**Problem**: No parameter to accept custom instructions from Firestore.

## Solution Design

### Phase 1: Extract Firestore Instructions Before Failure

**File**: `orchestrator.py`
**Location**: Around line 639, after formatter creation

**Change**:
```python
# Create the formatter agent (loads Firestore config)
formatter = strategy_config["create_formatter"]()

# Extract Firestore instructions immediately after creation
# This ensures we have them even if the formatter fails
firestore_instructions = getattr(formatter, 'system_instructions', None)
```

**Rationale**:
- Extract instructions immediately after formatter creation
- Store them before any potential failures
- Use getattr with default None for safety

### Phase 2: Pass Instructions to OpenAI Fallback

**File**: `orchestrator.py`
**Location**: Line 712, OpenAI fallback call

**Change**:
```python
formatted_output = format_with_openai(
    research_data=research_data,
    model_class=model_class,
    strategy_type=strategy_name,
    source_urls=source_urls,
    custom_instructions=firestore_instructions,  # NEW: Pass Firestore instructions
)
```

**Rationale**:
- Pass the extracted instructions to OpenAI fallback
- If None, function will use hardcoded fallback

### Phase 3: Modify OpenAI Formatter to Accept Custom Instructions

**File**: `openai_formatter.py`
**Location**: Lines 34-91

**Changes**:

1. Update function signature (line 34):
```python
def format_with_openai(
    research_data: str,
    model_class: type[BaseModel],
    strategy_type: str,
    source_urls: list[str] | None = None,
    custom_instructions: str | None = None,  # NEW parameter
) -> BaseModel:
```

2. Update system message logic (around line 75):
```python
# Use custom instructions if provided (from Firestore), otherwise use hardcoded fallback
if custom_instructions:
    system_content = custom_instructions
    logger.info(f"Using custom instructions from Firestore for {strategy_type} OpenAI fallback")
else:
    system_content = (
        f"You are a {strategy_type} formatter. Format the research into a structured "
        f"{strategy_type} document matching the provided schema exactly. "
        f"Extract relevant information from the research and map it to the appropriate fields. "
        f"Ensure all required fields are populated with meaningful content."
    )
    logger.warning(f"No custom instructions available, using hardcoded fallback for {strategy_type}")

messages = [
    {
        "role": "system",
        "content": system_content,
    },
    # ... rest of messages
]
```

**Rationale**:
- Accept optional custom_instructions parameter
- Use custom instructions if provided (priority)
- Fall back to hardcoded instructions only if None
- Add logging to track which instructions are used

## Implementation Checklist

### Step 1: Update openai_formatter.py
- [ ] Add `custom_instructions: str | None = None` parameter to function signature
- [ ] Add conditional logic to use custom_instructions vs hardcoded
- [ ] Add logger.info when using custom instructions
- [ ] Add logger.warning when using hardcoded fallback
- [ ] Run formatter to ensure signature change doesn't break anything

### Step 2: Update orchestrator.py
- [ ] Extract `firestore_instructions = getattr(formatter, 'system_instructions', None)` after formatter creation (around line 639)
- [ ] Pass `custom_instructions=firestore_instructions` to format_with_openai call (line 712)
- [ ] Add logger.info to show when Firestore instructions are extracted

### Step 3: Testing
- [ ] Test with valid Firestore config: Should use custom instructions
- [ ] Test with no Firestore config: Should use hardcoded fallback
- [ ] Test all four strategy types: business, competitive, marketing, brand
- [ ] Check Weave traces to confirm correct instructions are being used
- [ ] Verify formatted output quality with Firestore instructions

### Step 4: Restart Services
- [ ] Restart API server to load updated code
- [ ] Test complete flow: research → format → graph creation

## Expected Outcomes

### Success Criteria

1. **With Firestore Config (Normal Case)**:
   - Formatter loads instructions from Firestore
   - Gemini fails (simulated or real failure)
   - OpenAI fallback uses Firestore instructions
   - Weave trace shows custom instructions being used
   - Output quality matches Firestore instruction guidance

2. **Without Firestore Config (Fallback Case)**:
   - Formatter doesn't find config in Firestore
   - firestore_instructions is None
   - OpenAI uses hardcoded instructions
   - Logger warning about using hardcoded fallback
   - System still functions (degraded but working)

3. **All Strategy Types**:
   - business_strategy ✅
   - competitive_strategy ✅
   - marketing_strategy ✅
   - brand_strategy ✅

### Log Messages to Verify

```
INFO: Extracted Firestore instructions for marketing_strategy formatter
INFO: Using custom instructions from Firestore for marketing_strategy OpenAI fallback
```

OR

```
INFO: No Firestore instructions found for business_strategy formatter
WARNING: No custom instructions available, using hardcoded fallback for business_strategy
```

## Potential Issues and Mitigations

### Issue 1: system_instructions Attribute Missing
**Symptom**: AttributeError when accessing formatter.system_instructions
**Mitigation**: Use getattr with None default
**Code**: `firestore_instructions = getattr(formatter, 'system_instructions', None)`

### Issue 2: Instructions Format Mismatch
**Symptom**: OpenAI doesn't understand Firestore instructions format
**Mitigation**: Log the instructions being used, verify format in Weave traces
**Code**: Add logger.debug to show first 200 chars of instructions

### Issue 3: Breaking Existing Functionality
**Symptom**: OpenAI formatter breaks for cases that were working
**Mitigation**: Make custom_instructions optional with None default
**Code**: `custom_instructions: str | None = None`

## Testing Strategy

### Unit Tests (Optional)
Could add tests to `test_openai_formatter.py`:
- Test with custom_instructions provided
- Test with custom_instructions as None
- Verify correct instructions are used in each case

### Integration Tests (Required)
1. Run full strategy agent with marketing_strategy
2. Check Weave traces for:
   - Firestore config load ✅
   - Custom instructions extraction ✅
   - OpenAI fallback with custom instructions ✅
3. Verify output matches expected schema
4. Compare quality with/without Firestore instructions

### Manual Testing Steps
1. Ensure Firestore has marketing_formatter config
2. Run strategy agent for marketing_strategy
3. Check API logs for "Using custom instructions from Firestore"
4. Review Weave trace to confirm instructions content
5. Validate output has expected quality improvements

## Rollback Plan

If issues arise:
1. Revert openai_formatter.py changes
2. Revert orchestrator.py changes
3. Restart API server
4. System returns to hardcoded instruction behavior

Git commands:
```bash
git checkout HEAD -- app/adk/agents/strategy_agent/openai_formatter.py
git checkout HEAD -- app/adk/agents/strategy_agent/orchestrator.py
```

## Alignment with CLAUDE.md

### Best Practices Followed
- **BP-1**: No clarifying questions needed - requirements are clear
- **C-1**: Following TDD - plan before implementation
- **C-4**: Simple, composable changes to existing functions
- **C-7**: Minimal comments - code is self-explanatory
- **PY-1**: Type hints maintained throughout
- **PY-7**: Exception handling with getattr for safety

### Implementation Guidelines
- **O-1**: Changes isolated to agent logic in `app/`
- **T-4**: Integration tests required (check Weave traces)
- **G-1**: Will pass make lint after implementation

## Next Steps

Once this plan is approved:
1. Implement changes to openai_formatter.py
2. Implement changes to orchestrator.py
3. Run linting and type checking
4. Restart API server
5. Test with marketing_strategy
6. Verify Weave traces show correct behavior
7. Test with other strategy types
8. Document findings

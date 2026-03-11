# API Gateway & Multi-Channel Architecture

**Version:** 1.0
**Date:** March 2026
**Status:** Current API is canonical; multi-channel is [PLANNED]

---

## 1. Current API Architecture

The KEN-E API is a FastAPI application deployed on Google Cloud Run.

### Key Files

| File | Role |
|------|------|
| `api/src/kene_api/main.py` | FastAPI app, CORS middleware, router registration |
| `api/src/kene_api/routers/chat.py` | Main chat endpoint, session management, Agent Engine integration |
| `api/src/kene_api/routers/mcp.py` | MCP health and admin endpoints |
| `api/src/kene_api/routers/auth.py` | Authentication endpoints |

### Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat/completions` | POST | Send message to Agent Engine, get response |
| `/api/v1/chat/health` | GET | Check Agent Engine connectivity |
| `/api/v1/conversations` | POST | Create new conversation (returns `pending_*` session ID) |
| `/api/v1/mcp/health` | GET | MCP server health status |

### Session Management

1. Frontend creates `pending_*` session IDs via `POST /conversations`
2. API resolves pending to real ADK session ID on first message
3. Frontend syncs session ID from chat completion response
4. Session formats: `pending_*`, `chat_*`, `fallback_*`, `manual_*` are non-ADK — trigger new ADK session creation
5. Session cache: in-memory dict + Redis (survives restarts)
6. `APP_NAME = "ken_e_chatbot"` — must be consistent across all ADK session operations

### Authentication Flow

- Firebase Auth tokens from frontend
- Token validated on every request
- GA credentials stored in ADK session state (cached per-user)
- Background reauth check with cache (non-blocking)

## 2. Channel-Agnostic API Design

The current chat endpoint is **channel-agnostic**:
- Accepts a standard message format (role, content, timestamp)
- Routes to Agent Engine regardless of message source
- Returns a standard response format (role, content, session_id)
- Session management is user-based, not channel-based

Any new channel only needs to:
1. Authenticate the user (map channel identity to KEN-E user)
2. Format its input into the standard chat request
3. Parse the standard chat response for its output format

The core Agent Engine call path does not change.

## 3. [PLANNED] Multi-Channel Vision

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│     Web UI          │  │     Slack Bot        │  │     Voice           │
│  (React SPA)        │  │  (Bolt SDK)          │  │  (Pipecat)          │
│  Port 8080          │  │  Separate Cloud Run  │  │  Phase 4            │
└─────────┬───────────┘  └─────────┬───────────┘  └─────────┬───────────┘
          │                        │                         │
          ▼                        ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       KEN-E API (FastAPI, Cloud Run)                     │
│                    POST /api/v1/chat/completions                        │
│                    (Same endpoint for all channels)                      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Vertex AI Agent Engine                                │
│                    (KEN-E Agent Hierarchy)                               │
└─────────────────────────────────────────────────────────────────────────┘
```

All channels normalize to the same `POST /api/v1/chat/completions` call. The agent system is completely channel-unaware.

## 4. [PLANNED] Slack Integration Approach

- **Framework:** Slack Bolt SDK for Python
- **Deployment:** Separate Cloud Run service (not embedded in the API)
- **User mapping:** Slack user ID → KEN-E user via Firestore lookup
- **Interaction model:** @mention in channels, DM for private conversation
- **Response format:** Slack Block Kit (converted from agent's markdown response)
- **Threading:** Map Slack threads to KEN-E sessions

The Slack service is a thin adapter — it authenticates the Slack user, maps to KEN-E identity, calls the standard chat API, and formats the response as Block Kit.

## 5. [PLANNED] Voice Integration Approach

- **Framework:** Pipecat for voice pipeline orchestration
- **Meeting access:** Recall.ai or Meeting BaaS for joining Zoom/Teams/Meet
- **STT:** Deepgram (sub-300ms streaming latency)
- **TTS:** Cartesia (sub-100ms TTFB) or Deepgram Aura (sub-200ms TTFB)
- **Timeline:** Phase 4 — after core functionality is stable

Key considerations:
- Voice responses must be concise (< 30 seconds)
- Target < 2 seconds end-to-end response time
- Need speaker diarization to identify who is speaking
- Estimated cost: ~$1.20/hour per meeting

## 6. Stable Components Across Channels

| Component | Changes Needed? |
|-----------|----------------|
| Chat API endpoint | No — already channel-agnostic |
| Agent Engine integration | No — unaware of channels |
| Session management | No — already user-based |
| Context loading | No — keyed by account/user |
| Agent hierarchy | No — same agents for all channels |
| Firestore/Neo4j data model | No |
| Authentication core | No — but need per-channel auth adapters |

The only new code needed per channel is: auth adapter, input normalizer, output formatter, and a deployment target.

## References

- Chat router: `api/src/kene_api/routers/chat.py`
- API main: `api/src/kene_api/main.py`
- Agent hierarchy: `docs/design/agent-hierarchy.md`

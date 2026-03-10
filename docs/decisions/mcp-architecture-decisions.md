# MCP Architecture: Consolidated Questions & Decisions

> **This document is superseded.** The final MCP architecture decisions are captured in:
>
> - **Design doc:** `docs/design/mcp-architecture.md` — canonical architecture reference
> - **Notion design brief:** [MCP Server Architecture: Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463) — original source material
>
> This document was created during Sprint 3b investigation (March 6, 2026) to
> consolidate open questions about MCP management. The questions have since been
> resolved and the decisions are reflected in the design doc above.
>
> **Key decisions made:**
> 1. MCPServerManager's pooling/LRU deprecated — ADK handles natively
> 2. Specialist routing solves token budgets — each agent sees only its domain tools
> 3. Platform integration: HubSpot=provider MCP, Google Ads=self-host MCP, Meta Ads=SDK tools, Mailchimp=SDK tools
> 4. Config-driven agent factory planned for Sprint 5-6
> 5. YAML config evolves to Firestore config registry

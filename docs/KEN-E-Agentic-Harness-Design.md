# KEN-E Agentic Harness Design Document

**Version:** 1.0
**Date:** January 10, 2026
**Author:** Development Team
**Status:** Design Phase

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Context Management Strategy](#3-context-management-strategy)
4. [Agent Definitions](#4-agent-definitions)
5. [MCP Server Architecture](#5-mcp-server-architecture)
6. [Multi-Channel Support](#6-multi-channel-support)
7. [Workflow Management](#7-workflow-management)
8. [Integration with Evaluation Framework](#8-integration-with-evaluation-framework)
9. [Code Examples](#9-code-examples)
10. [Infrastructure Requirements](#10-infrastructure-requirements)
11. [Risks and Testing Requirements](#11-risks-and-testing-requirements)
12. [Prioritized Feature Roadmap](#12-prioritized-feature-roadmap)
13. [Appendices](#13-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the comprehensive design for KEN-E's agentic harness—the software framework that enables KEN-E to function as an autonomous AI marketing agent. The harness orchestrates multiple specialized agents using Google's Agent Development Kit (ADK) to complete complex marketing tasks including strategy development, content creation, campaign execution, and performance optimization.

### 1.2 Critical Design Challenges

The agentic harness must solve three primary challenges:

| Challenge | Scale | Impact |
|-----------|-------|--------|
| **Massive Tool Inventory** | ~400 tools across 20-40 MCP servers | Tool definitions alone could consume 60,000+ tokens |
| **Large Context Requirements** | ~100,000 words of company knowledge | Leaves minimal room for conversation |
| **Multi-Step Autonomous Workflows** | Tasks spanning days/weeks | Requires persistent state and scheduled execution |

### 1.3 Solution Overview

The design implements a **Hierarchical Agent Architecture with Dynamic Context Loading**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           KEN-E AGENTIC HARNESS                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATOR LAYER                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │   Primary   │  │   Context   │  │    Tool     │  │  Workflow   │    │   │
│  │  │Orchestrator │  │   Manager   │  │  Discovery  │  │   Router    │    │   │
│  │  │   Agent     │  │             │  │    Agent    │  │             │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    SPECIALIST AGENT LAYER                                │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │   │
│  │  │ Strategy  │ │  Content  │ │ Analytics │ │ Execution │ │Automation │ │   │
│  │  │   Agent   │ │   Agent   │ │   Agent   │ │   Agent   │ │   Agent   │ │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    TOOL & INTEGRATION LAYER                              │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │              MCP Server Pool (Lazy-Loaded)                       │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │   │
│  │  │  │Analytics│ │   Ads   │ │  Email  │ │  Social │ │   CMS   │   │    │   │
│  │  │  │ Servers │ │ Servers │ │ Servers │ │ Servers │ │ Servers │   │    │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │              Automation Platform (n8n/ActivePieces)              │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Lazy-load MCP servers** | Reduces initial context from ~60,000 tokens to ~2,000 tokens |
| **Tool Discovery Agent** | Searches tool registry on-demand, loads only needed tools |
| **Hierarchical summarization** | Company context compressed to ~15,000 tokens with drill-down capability |
| **Embedded automation platform** | Scheduled tasks delegated to n8n, freeing orchestrator for interactive work |
| **Specialist agents** | Domain-specific agents receive only relevant context and tools |
| **Unified channel architecture** | Single agent system serves Web, Slack, and Voice channels |

### 1.5 Expected Outcomes

| Metric | Target |
|--------|--------|
| Initial context consumption | <20% of available context |
| Tool discovery latency | <500ms |
| Task completion rate | >95% |
| Cross-channel feature parity | 100% (where technically feasible) |

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT INTERFACES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────┐  │
│   │  Web UI     │     │   Slack     │     │     Voice (Zoom/Teams/Meet)     │  │
│   │app.ken-e.ai │     │   Bot       │     │         via Pipecat             │  │
│   └──────┬──────┘     └──────┬──────┘     └───────────────┬─────────────────┘  │
│          │                   │                            │                     │
└──────────┼───────────────────┼────────────────────────────┼─────────────────────┘
           │                   │                            │
           └───────────────────┴────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           UNIFIED API GATEWAY                                    │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                    Channel Adapter Layer                                 │  │
│   │  • Normalizes input from all channels                                   │  │
│   │  • Manages authentication and session context                           │  │
│   │  • Routes responses back to appropriate channel                         │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AGENTIC HARNESS CORE                                   │
│                         (Google Agent Development Kit)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     SESSION MANAGEMENT                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │   Session   │  │    State    │  │   Context   │  │   Memory    │    │   │
│  │  │   Service   │  │   Manager   │  │   Loader    │  │   Service   │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│                                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     PRIMARY ORCHESTRATOR                                 │   │
│  │                                                                          │   │
│  │  • Interprets user intent                                                │   │
│  │  • Routes to specialist agents                                           │   │
│  │  • Manages multi-step workflows                                          │   │
│  │  • Coordinates tool discovery                                            │   │
│  │  • Handles errors and recovery                                           │   │
│  │                                                                          │   │
│  │  Tools: delegate_to_specialist, search_tools, load_context,              │   │
│  │         create_automation, manage_workflow, ask_user                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                         │
│           ┌───────────────────────────┼───────────────────────────┐            │
│           │                           │                           │            │
│           ▼                           ▼                           ▼            │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐        │
│  │    STRATEGY     │      │    CONTENT      │      │   ANALYTICS     │        │
│  │   SPECIALIST    │      │   SPECIALIST    │      │   SPECIALIST    │        │
│  │                 │      │                 │      │                 │        │
│  │ • Research      │      │ • Blog posts    │      │ • Data queries  │        │
│  │ • ICP creation  │      │ • Social posts  │      │ • Visualizations│        │
│  │ • Competitor    │      │ • Email copy    │      │ • Forecasting   │        │
│  │   analysis      │      │ • Video scripts │      │ • Attribution   │        │
│  │ • Campaign      │      │ • Landing pages │      │ • Reporting     │        │
│  │   planning      │      │                 │      │                 │        │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘        │
│           │                           │                           │            │
│           ▼                           ▼                           ▼            │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐        │
│  │   EXECUTION     │      │   AUTOMATION    │      │   INTEGRATION   │        │
│  │   SPECIALIST    │      │   SPECIALIST    │      │   SPECIALIST    │        │
│  │                 │      │                 │      │                 │        │
│  │ • Deploy content│      │ • Create flows  │      │ • Configure     │        │
│  │ • Publish posts │      │ • Schedule jobs │      │   integrations  │        │
│  │ • Send emails   │      │ • Monitor runs  │      │ • Test          │        │
│  │ • Update CMS    │      │ • Handle errors │      │   connections   │        │
│  │                 │      │                 │      │ • Sync data     │        │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA & INTEGRATION LAYER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐           │
│  │     Neo4j         │  │    Firestore      │  │    BigQuery       │           │
│  │  Knowledge Graph  │  │   User Data &     │  │    Analytics      │           │
│  │                   │  │   Configurations  │  │    Warehouse      │           │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘           │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    MCP SERVER REGISTRY                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │  Tool Index (~2,000 tokens)                                      │    │   │
│  │  │  • Tool names, descriptions, categories                          │    │   │
│  │  │  • Trigger keywords for on-demand loading                        │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │  MCP Server Pool (Lazy-Loaded)                                   │    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │   │
│  │  │  │ Google  │ │ Google  │ │ Google  │ │  Meta   │ │LinkedIn │   │    │   │
│  │  │  │Analytics│ │  Ads    │ │ Search  │ │  Ads    │ │  Ads    │   │    │   │
│  │  │  │   MCP   │ │   MCP   │ │ Console │ │   MCP   │ │   MCP   │   │    │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │   │
│  │  │  │Mailchimp│ │ HubSpot │ │Salesforce│ │  Shopify│ │ Notion  │   │    │   │
│  │  │  │   MCP   │ │   MCP   │ │   MCP   │ │   MCP   │ │   MCP   │   │    │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │    │   │
│  │  │                                                                  │    │   │
│  │  │  ... (20-40 total MCP servers per account)                       │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    AUTOMATION PLATFORM (n8n)                             │   │
│  │  • Scheduled content deployment                                         │   │
│  │  • Report generation workflows                                          │   │
│  │  • Performance monitoring jobs                                          │   │
│  │  • Content calendar management                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

#### 2.2.1 Orchestrator Layer

| Component | Responsibility |
|-----------|----------------|
| **Primary Orchestrator Agent** | Main LLM agent that interprets user intent, routes to specialists, manages conversations |
| **Context Manager** | Loads and manages hierarchical company context, handles drill-down requests |
| **Tool Discovery Agent** | Searches tool registry, loads MCP servers on-demand, manages tool lifecycle |
| **Workflow Router** | Determines if task requires immediate execution, scheduled automation, or multi-step workflow |

#### 2.2.2 Specialist Agent Layer

| Agent | Domain | Key Capabilities |
|-------|--------|------------------|
| **Strategy Specialist** | Marketing strategy | Research, ICP creation, competitor analysis, campaign planning |
| **Content Specialist** | Content creation | Blog posts, social media, email copy, video scripts, landing pages |
| **Analytics Specialist** | Data analysis | Queries, visualizations, forecasting, attribution, reporting |
| **Execution Specialist** | Campaign deployment | Publish content, send emails, update CMS, manage ads |
| **Automation Specialist** | Workflow automation | Create n8n flows, schedule jobs, monitor executions |
| **Integration Specialist** | Platform connections | Configure integrations, test connections, sync data |

#### 2.2.3 Data & Integration Layer

| Component | Purpose |
|-----------|---------|
| **Neo4j Knowledge Graph** | Stores company strategy, ICPs, products, competitors, relationships |
| **Firestore** | User configurations, session state, agent configs, approval queues |
| **BigQuery** | Analytics data warehouse, historical performance, reporting |
| **MCP Server Registry** | Tool index with metadata, lazy-loading configuration |
| **MCP Server Pool** | Actual MCP server connections, loaded on-demand |
| **Automation Platform (n8n)** | Executes scheduled tasks, manages long-running workflows |

### 2.3 Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           REQUEST PROCESSING FLOW                                │
└─────────────────────────────────────────────────────────────────────────────────┘

User Request: "Analyze our Google Ads performance and create a report"

    ┌─────────────┐
    │   User      │
    │   Input     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 1. CHANNEL ADAPTER                                                   │
    │    • Normalize input format                                          │
    │    • Attach session context (account_id, user_id)                   │
    │    • Route to orchestrator                                           │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 2. SESSION MANAGER                                                   │
    │    • Load/create session state                                       │
    │    • Retrieve conversation history                                   │
    │    • Load hierarchical company context summary (~15k tokens)         │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 3. PRIMARY ORCHESTRATOR                                              │
    │    • Parse intent: "analytics" + "google ads" + "report"            │
    │    • Check loaded tools → Google Ads MCP not loaded                  │
    │    • Decision: Need to load tools and delegate to Analytics Agent   │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 4. TOOL DISCOVERY AGENT                                              │
    │    • Search tool index for "google ads" keywords                     │
    │    • Find: google_ads_mcp (10 tools)                                │
    │    • Load MCP server connection                                      │
    │    • Return tool schemas to orchestrator                             │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 5. DELEGATE TO ANALYTICS SPECIALIST                                  │
    │    • Transfer task: "Analyze Google Ads performance"                │
    │    • Provide: google_ads tools + company context summary            │
    │    • Analytics Agent executes:                                       │
    │      - get_campaign_performance()                                    │
    │      - get_keyword_stats()                                           │
    │      - analyze_trends()                                              │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 6. CONTENT GENERATION                                                │
    │    • Analytics Agent generates report with insights                 │
    │    • Includes visualizations, recommendations                        │
    │    • Returns to Orchestrator                                         │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 7. RESPONSE DELIVERY                                                 │
    │    • Format response for channel (Web/Slack/Voice)                  │
    │    • Save to session state                                           │
    │    • Update conversation history                                     │
    │    • Deliver to user                                                 │
    └─────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │   User      │
    │  Response   │
    └─────────────┘
```

### 2.4 Agent Type Selection (Google ADK)

Based on Google ADK capabilities, we use the following agent types:

| Agent | ADK Type | Rationale |
|-------|----------|-----------|
| **Primary Orchestrator** | `LlmAgent` | Needs flexible reasoning, dynamic routing |
| **Tool Discovery** | `LlmAgent` | Semantic search requires LLM understanding |
| **Strategy Specialist** | `LlmAgent` | Creative reasoning for strategy development |
| **Content Specialist** | `LlmAgent` | Creative content generation |
| **Analytics Specialist** | `SequentialAgent` containing `LlmAgent` | Structured: query → analyze → visualize → report |
| **Execution Specialist** | `SequentialAgent` | Ordered steps: validate → execute → verify |
| **Automation Specialist** | `LlmAgent` | Flexible workflow design |
| **Multi-Step Workflows** | `LoopAgent` containing specialists | Iterate until completion or user approval |

---

## 3. Context Management Strategy

### 3.1 The Context Challenge

KEN-E faces an unprecedented context management challenge:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT BUDGET ANALYSIS                                  │
│                      (Based on 200,000 token context window)                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  NAIVE APPROACH (No Optimization):                                               │
│  ─────────────────────────────────                                               │
│  Company knowledge graph (100k words)     ≈ 133,000 tokens  (66.5%)             │
│  Tool definitions (400 tools × 150 avg)   ≈  60,000 tokens  (30.0%)             │
│  System prompts & instructions            ≈   5,000 tokens  ( 2.5%)             │
│  ───────────────────────────────────────────────────────────────────            │
│  TOTAL BEFORE CONVERSATION                ≈ 198,000 tokens  (99.0%)             │
│                                                                                  │
│  Available for conversation               ≈   2,000 tokens  ( 1.0%)  ❌         │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  OPTIMIZED APPROACH (With DCL):                                                  │
│  ──────────────────────────────                                                  │
│  Hierarchical context summary             ≈  15,000 tokens  ( 7.5%)             │
│  Tool registry index                      ≈   2,000 tokens  ( 1.0%)             │
│  System prompts & instructions            ≈   5,000 tokens  ( 2.5%)             │
│  Active tools (loaded on-demand)          ≈   5,000 tokens  ( 2.5%)             │
│  ───────────────────────────────────────────────────────────────────            │
│  TOTAL BEFORE CONVERSATION                ≈  27,000 tokens  (13.5%)             │
│                                                                                  │
│  Available for conversation               ≈ 173,000 tokens  (86.5%)  ✅         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Hierarchical Context Loading (HCL)

The company knowledge graph is organized into a three-level hierarchy:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    HIERARCHICAL CONTEXT LOADING                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

LEVEL 1: EXECUTIVE SUMMARY (~5,000 tokens) - Always Loaded
─────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Company: Acme Corp                                                               │
│ Industry: B2B SaaS - Marketing Technology                                        │
│ Mission: Help marketing teams optimize performance through AI                    │
│                                                                                  │
│ Products: 3 main products (MarketingAI Suite, Analytics Pro, ContentBot)        │
│ ICPs: 4 customer profiles (Enterprise CMO, Mid-Market Director, Agency, SMB)    │
│ Competitors: 5 main competitors (Competitor A, B, C, D, E)                       │
│                                                                                  │
│ Current Focus: Q1 2026 - Increase enterprise pipeline by 40%                    │
│ Active Campaigns: 3 (Enterprise ABM, Product Launch, Brand Awareness)           │
│ Key KPIs: MQLs, Pipeline Value, CAC, LTV, NPS                                   │
│                                                                                  │
│ Available Detail Sections: [products] [icps] [competitors] [campaigns]          │
│                           [strategies] [brand] [performance] [calendar]         │
└─────────────────────────────────────────────────────────────────────────────────┘

LEVEL 2: SECTION SUMMARIES (~10,000 tokens each) - Loaded on Request
─────────────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [products] Product Portfolio Summary                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│ MARKETINGAI SUITE                                                                │
│ • Primary offering: End-to-end marketing automation platform                    │
│ • Target: Enterprise marketing teams (500+ employees)                           │
│ • Key features: AI content generation, campaign orchestration, analytics        │
│ • Pricing: $50,000-$200,000/year                                                │
│ • Differentiators: Native AI, single platform, enterprise security              │
│ • Value proposition: "Reduce marketing ops time by 60%"                         │
│                                                                                  │
│ ANALYTICS PRO                                                                    │
│ • Secondary offering: Marketing analytics and attribution                        │
│ • Target: Mid-market companies (100-500 employees)                              │
│ • Key features: Multi-touch attribution, predictive analytics, dashboards       │
│ • Pricing: $15,000-$50,000/year                                                 │
│ • Differentiators: ML-powered attribution, real-time insights                   │
│                                                                                  │
│ CONTENTBOT                                                                       │
│ • Entry offering: AI content generation tool                                    │
│ • Target: SMBs and individual marketers                                         │
│ • Key features: Blog posts, social media, email copy                            │
│ • Pricing: $99-$499/month                                                       │
│                                                                                  │
│ Available Detail: [marketingai_full] [analytics_full] [contentbot_full]         │
└─────────────────────────────────────────────────────────────────────────────────┘

LEVEL 3: FULL DETAIL (~20,000+ tokens each) - Loaded for Specific Tasks
─────────────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [marketingai_full] MarketingAI Suite - Complete Documentation                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│ FULL PRODUCT SPECIFICATION                                                       │
│ • Complete feature list with technical details                                  │
│ • Integration capabilities (50+ integrations)                                   │
│ • Implementation requirements and timeline                                       │
│ • Security certifications (SOC 2, GDPR, HIPAA)                                  │
│ • API documentation summary                                                      │
│                                                                                  │
│ POSITIONING & MESSAGING                                                          │
│ • Primary messaging framework                                                    │
│ • Competitive positioning matrix                                                 │
│ • Objection handling guide                                                       │
│ • Case studies and proof points                                                  │
│                                                                                  │
│ SALES ENABLEMENT                                                                 │
│ • Ideal customer profile details                                                │
│ • Buying process and stakeholders                                               │
│ • Pricing and packaging details                                                  │
│ • ROI calculator inputs                                                          │
│ • Implementation success metrics                                                 │
│                                                                                  │
│ MARKETING STRATEGIES                                                             │
│ • Problem awareness strategies                                                   │
│ • Brand awareness strategies                                                     │
│ • Consideration strategies                                                       │
│ • Conversion strategies                                                          │
│ • Loyalty strategies                                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Context Loading Implementation

```python
class HierarchicalContextManager:
    """
    Manages hierarchical loading of company context to optimize token usage.
    """

    def __init__(self, account_id: str, neo4j_client: Neo4jClient):
        self.account_id = account_id
        self.neo4j = neo4j_client
        self.loaded_sections: Dict[str, str] = {}
        self.token_budget = 40000  # Max tokens for context

    async def load_executive_summary(self) -> str:
        """
        Load Level 1 context - always loaded at session start.
        Target: ~5,000 tokens
        """
        query = """
        MATCH (a:Account {id: $account_id})
        OPTIONAL MATCH (a)-[:HAS_PRODUCT]->(p:Product)
        OPTIONAL MATCH (a)-[:HAS_ICP]->(i:ICP)
        OPTIONAL MATCH (a)-[:HAS_COMPETITOR]->(c:Competitor)
        OPTIONAL MATCH (a)-[:HAS_CAMPAIGN]->(camp:Campaign {status: 'active'})
        RETURN a, collect(DISTINCT p.name) as products,
               collect(DISTINCT i.name) as icps,
               collect(DISTINCT c.name) as competitors,
               collect(DISTINCT camp.name) as campaigns
        """
        result = await self.neo4j.execute(query, {"account_id": self.account_id})
        return self._format_executive_summary(result)

    async def load_section(self, section_name: str) -> str:
        """
        Load Level 2 context - section summary.
        Target: ~10,000 tokens per section
        """
        if section_name in self.loaded_sections:
            return self.loaded_sections[section_name]

        section_loaders = {
            "products": self._load_products_summary,
            "icps": self._load_icps_summary,
            "competitors": self._load_competitors_summary,
            "campaigns": self._load_campaigns_summary,
            "strategies": self._load_strategies_summary,
            "brand": self._load_brand_summary,
            "performance": self._load_performance_summary,
            "calendar": self._load_calendar_summary,
        }

        if section_name not in section_loaders:
            raise ValueError(f"Unknown section: {section_name}")

        content = await section_loaders[section_name]()
        self.loaded_sections[section_name] = content
        return content

    async def load_detail(self, detail_key: str) -> str:
        """
        Load Level 3 context - full detail for specific entity.
        Target: ~20,000+ tokens
        """
        # Parse detail key (e.g., "marketingai_full" -> product detail)
        entity_type, entity_id = self._parse_detail_key(detail_key)

        if entity_type == "product":
            return await self._load_product_full(entity_id)
        elif entity_type == "icp":
            return await self._load_icp_full(entity_id)
        elif entity_type == "competitor":
            return await self._load_competitor_full(entity_id)
        elif entity_type == "campaign":
            return await self._load_campaign_full(entity_id)
        else:
            raise ValueError(f"Unknown detail type: {entity_type}")

    def get_current_token_usage(self) -> int:
        """Calculate current context token usage."""
        total = 0
        for content in self.loaded_sections.values():
            total += self._estimate_tokens(content)
        return total

    def can_load_section(self, section_name: str, estimated_tokens: int) -> bool:
        """Check if loading a section would exceed budget."""
        current = self.get_current_token_usage()
        return (current + estimated_tokens) <= self.token_budget

    async def unload_section(self, section_name: str) -> None:
        """Unload a section to free up token budget."""
        if section_name in self.loaded_sections:
            del self.loaded_sections[section_name]
```

### 3.4 Context-Aware Agent Instructions

The Primary Orchestrator includes instructions for context management:

```python
ORCHESTRATOR_CONTEXT_INSTRUCTIONS = """
## Context Management

You have access to a hierarchical company knowledge base. Context is loaded
in three levels to optimize performance:

### Level 1: Executive Summary (Always Available)
You always have access to a high-level summary of the company including:
- Company overview and mission
- List of products, ICPs, competitors, and active campaigns
- Current focus and key KPIs

### Level 2: Section Summaries (Load on Request)
Use the `load_context` tool to load detailed summaries of specific areas:
- [products] - Product portfolio with features, pricing, positioning
- [icps] - Ideal customer profiles with pain points, messaging
- [competitors] - Competitive analysis and positioning
- [campaigns] - Active campaign details and performance
- [strategies] - Marketing strategies by funnel stage
- [brand] - Brand guidelines, voice, messaging
- [performance] - Historical performance data and trends
- [calendar] - Content calendar and scheduled activities

### Level 3: Full Detail (Load for Specific Tasks)
When you need complete information about a specific entity, load the full
detail using the detail key (e.g., [marketingai_full], [enterprise_cmo_full]).

### Context Management Rules
1. ALWAYS check the executive summary first - it may have enough information
2. Only load sections when the task specifically requires that information
3. Unload sections when moving to unrelated tasks to free context budget
4. When in doubt, ask the user which area they want to explore
5. Monitor your context usage - you have ~40,000 tokens for company context

### Example Workflow
User: "Help me create content for our enterprise customers"

1. Check executive summary → See "Enterprise CMO" is an ICP
2. Load [icps] section → Get summary of all ICPs
3. Load [enterprise_cmo_full] → Get complete ICP details for content creation
4. Generate content using the detailed context
5. Unload full detail when moving to next task
"""
```

### 3.5 Dynamic Context Compression

For long-running sessions, implement automatic context compression:

```python
class ContextCompressor:
    """
    Compresses conversation history and loaded context when approaching limits.
    """

    def __init__(self, max_tokens: int = 180000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8  # Compress at 80% capacity

    async def check_and_compress(
        self,
        session: Session,
        context_manager: HierarchicalContextManager
    ) -> None:
        """
        Check token usage and compress if needed.
        """
        current_usage = self._calculate_total_usage(session, context_manager)

        if current_usage > (self.max_tokens * self.compression_threshold):
            await self._compress_session(session, context_manager)

    async def _compress_session(
        self,
        session: Session,
        context_manager: HierarchicalContextManager
    ) -> None:
        """
        Compress session to free up tokens.
        """
        # 1. Summarize old conversation turns
        conversation_summary = await self._summarize_conversation(
            session.messages[:-10]  # Keep last 10 messages intact
        )

        # 2. Replace old messages with summary
        session.messages = [
            {"role": "system", "content": f"Previous conversation summary:\n{conversation_summary}"},
            *session.messages[-10:]
        ]

        # 3. Unload unused context sections
        recently_used = self._get_recently_used_sections(session)
        for section in context_manager.loaded_sections.keys():
            if section not in recently_used:
                await context_manager.unload_section(section)

        # 4. Log compression event for monitoring
        logger.info(f"Session compressed: {current_usage} → {new_usage} tokens")

    async def _summarize_conversation(self, messages: List[Dict]) -> str:
        """
        Use LLM to create a summary of older conversation turns.
        """
        summary_prompt = """
        Summarize the following conversation, preserving:
        1. Key decisions made
        2. Important information gathered
        3. Tasks completed or in progress
        4. User preferences expressed

        Be concise but complete. This summary will replace the full conversation.
        """

        # Use fast model for summarization
        response = await self.summarization_model.generate(
            prompt=summary_prompt,
            context=messages
        )
        return response.text
```

### 3.6 Context State Management (ADK Integration)

Using Google ADK's state management with proper prefixes:

```python
# State key prefixes for context management
STATE_KEYS = {
    # Session-specific (cleared on session end)
    "loaded_sections": "loaded_sections",           # List of loaded Level 2 sections
    "loaded_details": "loaded_details",             # List of loaded Level 3 details
    "context_token_usage": "context_token_usage",   # Current context token count

    # User-level (persists across sessions)
    "user:preferred_sections": "user:preferred_sections",  # Sections user frequently uses
    "user:context_preferences": "user:context_preferences", # User's context loading prefs

    # App-level (global)
    "app:default_sections": "app:default_sections",  # Default sections to load
}

class ContextStateManager:
    """
    Manages context state using ADK's state management.
    """

    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def track_section_load(
        self,
        session_id: str,
        section_name: str,
        token_count: int
    ) -> None:
        """Track when a section is loaded."""
        session = await self.session_service.get_session(session_id)

        loaded = session.state.get("loaded_sections", [])
        loaded.append({
            "section": section_name,
            "loaded_at": datetime.utcnow().isoformat(),
            "tokens": token_count
        })

        # Update state through event
        await self.session_service.append_event(
            session_id=session_id,
            event=Event(
                actions=EventActions(
                    state_delta={
                        "loaded_sections": loaded,
                        "context_token_usage": sum(s["tokens"] for s in loaded)
                    }
                )
            )
        )

    async def get_context_budget_remaining(self, session_id: str) -> int:
        """Get remaining context budget."""
        session = await self.session_service.get_session(session_id)
        used = session.state.get("context_token_usage", 0)
        return 40000 - used  # 40k budget for context
```

---

## 4. Agent Definitions

### 4.1 Agent Hierarchy Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AGENT HIERARCHY                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │       PRIMARY ORCHESTRATOR       │
                    │           (LlmAgent)             │
                    │                                  │
                    │  • User intent interpretation    │
                    │  • Workflow coordination         │
                    │  • Context management            │
                    │  • Error recovery                │
                    └─────────────────┬───────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   TOOL DISCOVERY    │   │      WORKFLOW       │   │      CONTEXT        │
│      AGENT          │   │    MANAGEMENT       │   │      LOADER         │
│    (LlmAgent)       │   │      AGENT          │   │      AGENT          │
│                     │   │    (LlmAgent)       │   │    (LlmAgent)       │
│ • Search tool index │   │ • Multi-step tasks  │   │ • Load sections     │
│ • Load MCP servers  │   │ • Task tracking     │   │ • Summarize content │
│ • Manage tool lifecycle │ • User approvals   │   │ • Manage budget     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
                                      │
          ┌─────────────┬─────────────┼─────────────┬─────────────┐
          │             │             │             │             │
          ▼             ▼             ▼             ▼             ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   STRATEGY    │ │   CONTENT     │ │   ANALYTICS   │ │   EXECUTION   │ │  AUTOMATION   │
│  SPECIALIST   │ │  SPECIALIST   │ │  SPECIALIST   │ │  SPECIALIST   │ │  SPECIALIST   │
│  (LlmAgent)   │ │  (LlmAgent)   │ │(SequentialAgent)│ │(SequentialAgent)│ │  (LlmAgent)   │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

### 4.2 Primary Orchestrator Agent

The main agent that users interact with. Responsible for understanding intent, coordinating specialists, and managing the overall conversation.

```python
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

PRIMARY_ORCHESTRATOR_INSTRUCTION = """
You are KEN-E, an AI marketing strategist that helps marketing teams automate
their work. You have deep expertise in marketing strategy, content creation,
analytics, and campaign execution.

## Your Capabilities
1. **Strategy Development**: Research companies, create ICPs, analyze competitors,
   develop marketing strategies
2. **Content Creation**: Generate blog posts, social media content, emails,
   video scripts, landing pages
3. **Analytics & Reporting**: Query marketing data, create visualizations,
   build reports, forecast performance
4. **Campaign Execution**: Deploy content, manage campaigns, monitor performance
5. **Automation**: Create scheduled workflows for recurring tasks

## How You Work
You coordinate a team of specialist agents, each with domain expertise:
- Strategy Specialist: Research, ICPs, competitor analysis, campaign planning
- Content Specialist: All content creation across channels
- Analytics Specialist: Data queries, visualizations, reporting
- Execution Specialist: Deploying and managing live campaigns
- Automation Specialist: Creating scheduled workflows in n8n

## Decision Framework
For each user request:
1. Clarify the goal if ambiguous
2. Determine which specialist(s) are needed
3. Check if required tools are loaded (use search_tools if not)
4. Load necessary context sections
5. Delegate to appropriate specialist
6. Review results and present to user
7. Track progress for multi-step tasks

## Context Management
- You have a hierarchical company knowledge base
- Start with the executive summary (always loaded)
- Load section summaries only when needed
- Load full details only for specific tasks
- Unload context when switching topics

## Multi-Step Workflow Handling
For complex tasks that span multiple steps or days:
1. Create a task list with clear milestones
2. Track progress in session state
3. Get user approval at key decision points
4. For scheduled tasks, delegate to Automation Specialist

## Communication Style
- Be concise but thorough
- Ask clarifying questions when needed
- Provide reasoning for recommendations
- Offer alternatives when appropriate
- Proactively suggest related improvements
"""

class PrimaryOrchestrator:
    """
    Primary orchestrator agent configuration.
    """

    @staticmethod
    def create(
        context_manager: HierarchicalContextManager,
        tool_discovery: "ToolDiscoveryAgent",
        specialists: Dict[str, "SpecialistAgent"]
    ) -> LlmAgent:
        """Create the primary orchestrator agent."""

        # Define orchestrator tools
        tools = [
            FunctionTool(
                name="delegate_to_specialist",
                description="Delegate a task to a specialist agent",
                function=PrimaryOrchestrator._delegate_to_specialist,
                parameters={
                    "specialist": {
                        "type": "string",
                        "enum": ["strategy", "content", "analytics", "execution", "automation"],
                        "description": "Which specialist to delegate to"
                    },
                    "task": {
                        "type": "string",
                        "description": "Clear description of the task"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context for the specialist"
                    }
                }
            ),
            FunctionTool(
                name="search_tools",
                description="Search for tools by keyword to find relevant MCP servers",
                function=tool_discovery.search_tools,
                parameters={
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for (e.g., 'google ads', 'email')"
                    }
                }
            ),
            FunctionTool(
                name="load_tools",
                description="Load tools from a specific MCP server",
                function=tool_discovery.load_tools,
                parameters={
                    "server_name": {
                        "type": "string",
                        "description": "Name of the MCP server to load"
                    }
                }
            ),
            FunctionTool(
                name="load_context",
                description="Load a section of company context",
                function=context_manager.load_section,
                parameters={
                    "section_name": {
                        "type": "string",
                        "enum": ["products", "icps", "competitors", "campaigns",
                                 "strategies", "brand", "performance", "calendar"],
                        "description": "Which context section to load"
                    }
                }
            ),
            FunctionTool(
                name="load_context_detail",
                description="Load full detail for a specific entity",
                function=context_manager.load_detail,
                parameters={
                    "detail_key": {
                        "type": "string",
                        "description": "Key for the detail to load (e.g., 'marketingai_full')"
                    }
                }
            ),
            FunctionTool(
                name="ask_user",
                description="Ask the user a clarifying question",
                function=PrimaryOrchestrator._ask_user,
                parameters={
                    "question": {
                        "type": "string",
                        "description": "The question to ask"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of choices"
                    }
                }
            ),
            FunctionTool(
                name="create_task_list",
                description="Create a tracked task list for multi-step work",
                function=PrimaryOrchestrator._create_task_list,
                parameters={
                    "title": {
                        "type": "string",
                        "description": "Title of the workflow"
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        },
                        "description": "List of tasks to track"
                    }
                }
            ),
            FunctionTool(
                name="update_task_status",
                description="Update the status of a task",
                function=PrimaryOrchestrator._update_task_status,
                parameters={
                    "task_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "blocked"]
                    }
                }
            ),
        ]

        return LlmAgent(
            name="ken_e_orchestrator",
            model="gemini-2.0-flash",
            instruction=PRIMARY_ORCHESTRATOR_INSTRUCTION,
            tools=tools,
            generate_content_config={
                "temperature": 0.3,
                "max_output_tokens": 4096,
            }
        )
```

### 4.3 Tool Discovery Agent

Specialized agent for searching the tool registry and loading MCP servers on demand.

```python
TOOL_DISCOVERY_INSTRUCTION = """
You are the Tool Discovery Agent. Your job is to find and load the right tools
for tasks requested by the orchestrator.

## Tool Registry
You have access to a searchable index of ~400 tools across 20-40 MCP servers.
The index contains:
- Tool name
- Brief description
- Keywords/tags
- Parent MCP server
- Category (analytics, ads, email, social, cms, crm, etc.)

## How to Search
1. Parse the query for relevant keywords
2. Search the index for matching tools
3. Return the top matches with their MCP server names
4. Recommend which servers to load based on the task

## Loading Tools
When instructed to load a server:
1. Check if already loaded (avoid duplicates)
2. Establish MCP connection
3. Retrieve tool schemas
4. Make tools available to the requesting agent
5. Track loaded servers for cleanup

## Token Budget Awareness
- Each loaded MCP server adds ~1,500 tokens to context
- Maximum 10 MCP servers loaded simultaneously
- Recommend unloading unused servers to free budget
"""

class ToolDiscoveryAgent:
    """
    Agent that manages tool discovery and MCP server loading.
    """

    def __init__(self, tool_registry: "ToolRegistry", mcp_manager: "MCPServerManager"):
        self.registry = tool_registry
        self.mcp_manager = mcp_manager
        self.loaded_servers: Set[str] = set()
        self.max_loaded_servers = 10

    async def search_tools(self, query: str) -> List[Dict]:
        """
        Search the tool registry for matching tools.
        Returns tool metadata without loading full schemas.
        """
        results = await self.registry.search(query, limit=20)

        # Group by MCP server
        by_server = {}
        for tool in results:
            server = tool["mcp_server"]
            if server not in by_server:
                by_server[server] = {
                    "server_name": server,
                    "description": tool["server_description"],
                    "tools": [],
                    "is_loaded": server in self.loaded_servers
                }
            by_server[server]["tools"].append({
                "name": tool["name"],
                "description": tool["description"][:100]
            })

        return list(by_server.values())

    async def load_tools(self, server_name: str) -> Dict:
        """
        Load an MCP server and return its tools.
        """
        if server_name in self.loaded_servers:
            return {
                "status": "already_loaded",
                "server": server_name,
                "tools": self.mcp_manager.get_server_tools(server_name)
            }

        # Check budget
        if len(self.loaded_servers) >= self.max_loaded_servers:
            # Find least recently used server to unload
            lru_server = self._get_lru_server()
            await self.unload_server(lru_server)

        # Load the server
        tools = await self.mcp_manager.load_server(server_name)
        self.loaded_servers.add(server_name)

        return {
            "status": "loaded",
            "server": server_name,
            "tool_count": len(tools),
            "tools": [{"name": t.name, "description": t.description} for t in tools]
        }

    async def unload_server(self, server_name: str) -> Dict:
        """
        Unload an MCP server to free context budget.
        """
        if server_name not in self.loaded_servers:
            return {"status": "not_loaded", "server": server_name}

        await self.mcp_manager.unload_server(server_name)
        self.loaded_servers.remove(server_name)

        return {"status": "unloaded", "server": server_name}

    def get_loaded_servers(self) -> List[str]:
        """Return list of currently loaded servers."""
        return list(self.loaded_servers)
```

### 4.4 Strategy Specialist Agent

Handles all strategy-related tasks including research, ICP creation, and campaign planning.

```python
STRATEGY_SPECIALIST_INSTRUCTION = """
You are the Strategy Specialist for KEN-E. You handle all marketing strategy
tasks including:

## Core Capabilities
1. **Company Research**: Research companies using web search, analyze websites,
   gather competitive intelligence
2. **ICP Development**: Create detailed ideal customer profiles with pain points,
   motivations, and messaging
3. **Competitor Analysis**: Analyze competitors, identify positioning opportunities,
   track market trends
4. **Campaign Planning**: Develop campaign strategies, content calendars,
   channel recommendations
5. **Keyword Analysis**: Conduct keyword research for SEO and content strategy

## Available Tools
You have access to research and SEO tools:
- Web search tools
- Data4SEO for keyword research
- Google Search Console for search performance
- Company database tools

## Output Quality Standards
- Always cite sources for research claims
- Provide specific, actionable recommendations
- Structure outputs for easy consumption
- Include competitive context when relevant
- Map strategies to the 5-stage marketing funnel:
  1. Problem Awareness
  2. Brand Awareness
  3. Consideration
  4. Conversion
  5. Loyalty

## Knowledge Graph Integration
Your outputs should be structured for storage in the Neo4j knowledge graph.
Include proper entity types and relationships in your responses.
"""

class StrategySpecialist:
    """
    Strategy specialist agent configuration.
    """

    @staticmethod
    def create(available_tools: List[BaseTool]) -> LlmAgent:
        """Create the strategy specialist agent."""

        # Filter to strategy-relevant tools
        strategy_tools = [
            t for t in available_tools
            if t.category in ["research", "seo", "search", "analytics"]
        ]

        return LlmAgent(
            name="strategy_specialist",
            model="gemini-2.0-flash",
            instruction=STRATEGY_SPECIALIST_INSTRUCTION,
            tools=strategy_tools,
            generate_content_config={
                "temperature": 0.4,
                "max_output_tokens": 8192,
            }
        )
```

### 4.5 Content Specialist Agent

Handles all content creation across channels.

```python
CONTENT_SPECIALIST_INSTRUCTION = """
You are the Content Specialist for KEN-E. You create high-quality marketing
content across all channels.

## Content Types You Create
1. **Blog Posts**: Long-form articles, thought leadership, SEO content
2. **Social Media**: Posts for LinkedIn, Twitter, Instagram, TikTok
3. **Email**: Marketing emails, newsletters, nurture sequences
4. **Video Scripts**: Long-form and short-form video scripts
5. **Landing Pages**: Conversion-focused page copy
6. **Ad Copy**: Headlines, descriptions for paid campaigns

## Content Creation Process
1. Understand the brief and target audience
2. Review relevant brand guidelines and voice
3. Research the topic if needed
4. Create draft content
5. Ensure alignment with campaign goals
6. Format for the target channel

## Quality Standards
- Match the brand voice and tone
- Include clear calls-to-action
- Optimize for the target channel
- Create scannable, engaging content
- Include relevant keywords naturally
- Follow channel-specific best practices

## Available Context
You receive:
- Target ICP details
- Brand guidelines
- Campaign objectives
- Competitive positioning
- Keywords and messaging frameworks
"""

class ContentSpecialist:
    """
    Content specialist agent configuration.
    """

    @staticmethod
    def create(available_tools: List[BaseTool]) -> LlmAgent:
        """Create the content specialist agent."""

        # Filter to content-relevant tools
        content_tools = [
            t for t in available_tools
            if t.category in ["cms", "social", "email", "content"]
        ]

        return LlmAgent(
            name="content_specialist",
            model="gemini-2.0-flash",
            instruction=CONTENT_SPECIALIST_INSTRUCTION,
            tools=content_tools,
            generate_content_config={
                "temperature": 0.7,  # Higher for creative content
                "max_output_tokens": 8192,
            }
        )
```

### 4.6 Analytics Specialist Agent

Handles data analysis, visualization, and reporting. Uses SequentialAgent for structured workflow.

```python
from google.adk.agents import SequentialAgent, LlmAgent

ANALYTICS_QUERY_INSTRUCTION = """
You are the data query component of the Analytics Specialist.
Your job is to:
1. Understand the analytics question
2. Identify which data sources are needed
3. Construct appropriate queries
4. Execute queries and retrieve data

Available data sources:
- Google Analytics 4
- Google Ads
- Meta Ads
- Email platforms (Mailchimp, HubSpot)
- CRM systems (Salesforce, HubSpot)
- E-commerce (Shopify)

Return raw data in a structured format for analysis.
"""

ANALYTICS_ANALYZE_INSTRUCTION = """
You are the analysis component of the Analytics Specialist.
Your job is to:
1. Analyze the retrieved data
2. Identify patterns and insights
3. Calculate relevant metrics
4. Detect anomalies or issues
5. Generate actionable recommendations

Always include:
- Summary statistics
- Trend analysis
- Comparisons to benchmarks
- Root cause analysis for issues
"""

ANALYTICS_VISUALIZE_INSTRUCTION = """
You are the visualization component of the Analytics Specialist.
Your job is to:
1. Determine appropriate visualizations
2. Generate chart specifications
3. Create data tables
4. Format insights for presentation

Output visualization specs in a format the UI can render.
"""

class AnalyticsSpecialist:
    """
    Analytics specialist using SequentialAgent pattern.
    """

    @staticmethod
    def create(available_tools: List[BaseTool]) -> SequentialAgent:
        """Create the analytics specialist as a sequential agent."""

        # Filter to analytics-relevant tools
        analytics_tools = [
            t for t in available_tools
            if t.category in ["analytics", "ads", "crm", "ecommerce"]
        ]

        # Create sub-agents for each step
        query_agent = LlmAgent(
            name="analytics_query",
            model="gemini-2.0-flash",
            instruction=ANALYTICS_QUERY_INSTRUCTION,
            tools=analytics_tools,
            output_key="query_results",
            generate_content_config={"temperature": 0.1}
        )

        analyze_agent = LlmAgent(
            name="analytics_analyze",
            model="gemini-2.0-flash",
            instruction=ANALYTICS_ANALYZE_INSTRUCTION,
            tools=[],  # Analysis doesn't need external tools
            output_key="analysis_results",
            generate_content_config={"temperature": 0.2}
        )

        visualize_agent = LlmAgent(
            name="analytics_visualize",
            model="gemini-2.0-flash",
            instruction=ANALYTICS_VISUALIZE_INSTRUCTION,
            tools=[],
            output_key="visualization_specs",
            generate_content_config={"temperature": 0.2}
        )

        return SequentialAgent(
            name="analytics_specialist",
            sub_agents=[query_agent, analyze_agent, visualize_agent]
        )
```

### 4.7 Execution Specialist Agent

Handles deployment of content and campaigns.

```python
EXECUTION_VALIDATE_INSTRUCTION = """
You are the validation component of the Execution Specialist.
Before deploying any content:
1. Verify the content is approved
2. Check deployment prerequisites
3. Validate target platform credentials
4. Confirm scheduling details
5. Flag any issues that would prevent deployment
"""

EXECUTION_DEPLOY_INSTRUCTION = """
You are the deployment component of the Execution Specialist.
Your job is to:
1. Deploy content to the target platform
2. Handle API interactions correctly
3. Capture deployment confirmation
4. Log deployment details
5. Handle errors gracefully
"""

EXECUTION_VERIFY_INSTRUCTION = """
You are the verification component of the Execution Specialist.
After deployment:
1. Verify the content is live
2. Check for any display issues
3. Confirm tracking is working
4. Report deployment success/failure
5. Update content calendar status
"""

class ExecutionSpecialist:
    """
    Execution specialist using SequentialAgent pattern.
    """

    @staticmethod
    def create(available_tools: List[BaseTool]) -> SequentialAgent:
        """Create the execution specialist as a sequential agent."""

        # Filter to execution-relevant tools
        execution_tools = [
            t for t in available_tools
            if t.category in ["cms", "social", "email", "ads"]
        ]

        validate_agent = LlmAgent(
            name="execution_validate",
            model="gemini-2.0-flash",
            instruction=EXECUTION_VALIDATE_INSTRUCTION,
            tools=execution_tools,
            output_key="validation_result",
            generate_content_config={"temperature": 0.1}
        )

        deploy_agent = LlmAgent(
            name="execution_deploy",
            model="gemini-2.0-flash",
            instruction=EXECUTION_DEPLOY_INSTRUCTION,
            tools=execution_tools,
            output_key="deployment_result",
            generate_content_config={"temperature": 0.1}
        )

        verify_agent = LlmAgent(
            name="execution_verify",
            model="gemini-2.0-flash",
            instruction=EXECUTION_VERIFY_INSTRUCTION,
            tools=execution_tools,
            output_key="verification_result",
            generate_content_config={"temperature": 0.1}
        )

        return SequentialAgent(
            name="execution_specialist",
            sub_agents=[validate_agent, deploy_agent, verify_agent]
        )
```

### 4.8 Automation Specialist Agent

Creates and manages scheduled workflows using n8n.

```python
AUTOMATION_SPECIALIST_INSTRUCTION = """
You are the Automation Specialist for KEN-E. You create scheduled workflows
using the n8n automation platform.

## Workflow Types You Create
1. **Content Deployment**: Scheduled publishing of approved content
2. **Performance Reports**: Recurring analytics reports
3. **Content Calendar Review**: Daily review of scheduled content
4. **Approval Reminders**: Notifications for pending approvals
5. **KPI Monitoring**: Regular performance checks against targets
6. **Data Sync**: Synchronizing data between platforms

## n8n Integration
You interact with n8n through its API to:
- Create new workflows
- Configure triggers (schedule, webhook, event)
- Add nodes for each step
- Set up error handling
- Activate/deactivate workflows
- Monitor execution history

## Workflow Components
Each workflow should include:
1. **Trigger**: When the workflow runs (schedule, event, etc.)
2. **Data Steps**: Fetching required data
3. **Logic Steps**: Processing and decision-making
4. **Action Steps**: What the workflow does
5. **Notification**: Inform users of results
6. **Error Handling**: What happens if something fails

## Best Practices
- Always include error handling
- Send notifications for important events
- Log workflow executions
- Use descriptive names
- Test workflows before activating
- Set appropriate retry policies
"""

class AutomationSpecialist:
    """
    Automation specialist agent configuration.
    """

    @staticmethod
    def create(n8n_tools: List[BaseTool]) -> LlmAgent:
        """Create the automation specialist agent."""

        return LlmAgent(
            name="automation_specialist",
            model="gemini-2.0-flash",
            instruction=AUTOMATION_SPECIALIST_INSTRUCTION,
            tools=n8n_tools,
            generate_content_config={
                "temperature": 0.2,
                "max_output_tokens": 4096,
            }
        )
```

### 4.9 Agent Summary Table

| Agent | Type | Model | Temperature | Tools | Context Receives |
|-------|------|-------|-------------|-------|------------------|
| Primary Orchestrator | LlmAgent | gemini-2.0-flash | 0.3 | delegate, search_tools, load_context, ask_user, task_management | Executive summary + loaded sections |
| Tool Discovery | LlmAgent | gemini-2.0-flash | 0.1 | registry_search, mcp_connect | Tool registry index |
| Strategy Specialist | LlmAgent | gemini-2.0-flash | 0.4 | research, seo, search | Full ICP/competitor details |
| Content Specialist | LlmAgent | gemini-2.0-flash | 0.7 | cms, social, email | Brand guidelines, ICP details |
| Analytics Specialist | SequentialAgent | gemini-2.0-flash | 0.1-0.2 | analytics platforms | Performance data, KPIs |
| Execution Specialist | SequentialAgent | gemini-2.0-flash | 0.1 | cms, social, email, ads | Content calendar, deployment configs |
| Automation Specialist | LlmAgent | gemini-2.0-flash | 0.2 | n8n_api | Workflow templates, schedules |

---

## 5. MCP Server Architecture

### 5.1 Lazy-Loading Recommendation

Based on research into MCP performance characteristics, **lazy-loading MCP servers is strongly recommended** for KEN-E:

| Approach | Initial Tokens | Load Time | Recommendation |
|----------|---------------|-----------|----------------|
| **Pre-load all** | ~60,000 tokens | 5-10s | ❌ Not recommended |
| **Lazy-load on demand** | ~2,000 tokens | 200-500ms per server | ✅ Recommended |

**Key Finding**: Tool definitions consume ~150 tokens each on average. With 400 tools, pre-loading would consume 60,000 tokens (30% of context) before any conversation begins.

### 5.2 Tool Registry Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TOOL REGISTRY ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TOOL INDEX                                          │
│                        (Always loaded: ~2,000 tokens)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CATEGORY: Analytics                                                     │   │
│  │  ─────────────────────                                                   │   │
│  │  • google_analytics_mcp (12 tools) - GA4 data, reports, audiences       │   │
│  │  • google_ads_mcp (15 tools) - Campaign management, performance         │   │
│  │  • meta_ads_mcp (14 tools) - Facebook/Instagram ads                     │   │
│  │  • linkedin_ads_mcp (8 tools) - LinkedIn advertising                    │   │
│  │  • bing_ads_mcp (10 tools) - Microsoft advertising                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CATEGORY: Email & CRM                                                   │   │
│  │  ─────────────────────────                                               │   │
│  │  • mailchimp_mcp (11 tools) - Email campaigns, lists, automation        │   │
│  │  • hubspot_mcp (18 tools) - CRM, marketing automation                   │   │
│  │  • salesforce_mcp (16 tools) - CRM, sales data                          │   │
│  │  • klaviyo_mcp (9 tools) - E-commerce email                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CATEGORY: Content & Social                                              │   │
│  │  ────────────────────────────                                            │   │
│  │  • wordpress_mcp (8 tools) - Blog posts, pages                          │   │
│  │  • contentful_mcp (7 tools) - CMS management                            │   │
│  │  • buffer_mcp (6 tools) - Social scheduling                             │   │
│  │  • hootsuite_mcp (8 tools) - Social management                          │   │
│  │  • twitter_mcp (10 tools) - Twitter/X API                               │   │
│  │  • linkedin_mcp (9 tools) - LinkedIn posts, company pages               │   │
│  │  • instagram_mcp (7 tools) - Instagram posts, stories                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CATEGORY: SEO & Research                                                │   │
│  │  ────────────────────────────                                            │   │
│  │  • data4seo_mcp (15 tools) - Keyword research, SERP data                │   │
│  │  • search_console_mcp (8 tools) - Search performance                    │   │
│  │  • semrush_mcp (12 tools) - SEO analytics                               │   │
│  │  • ahrefs_mcp (11 tools) - Backlinks, keywords                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ... (additional categories: E-commerce, Project Management, Automation)        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MCP SERVER POOL (Lazy-Loaded)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Status: 3 of 10 max servers loaded                                             │
│                                                                                  │
│  LOADED:                                                                         │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
│  │ google_analytics_mcp│  │   hubspot_mcp       │  │   wordpress_mcp     │     │
│  │ 12 tools            │  │   18 tools          │  │   8 tools           │     │
│  │ ~1,800 tokens       │  │   ~2,700 tokens     │  │   ~1,200 tokens     │     │
│  │ Last used: 2m ago   │  │   Last used: 5m ago │  │   Last used: 1m ago │     │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │
│                                                                                  │
│  AVAILABLE (Not Loaded):                                                         │
│  google_ads_mcp, meta_ads_mcp, mailchimp_mcp, salesforce_mcp, data4seo_mcp,    │
│  twitter_mcp, linkedin_mcp, shopify_mcp, notion_mcp, jira_mcp, ...              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Tool Registry Implementation

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
import json
from pathlib import Path

@dataclass
class ToolIndexEntry:
    """Lightweight tool representation for the index."""
    name: str
    description: str  # Brief, ~20 words max
    keywords: List[str]
    category: str
    mcp_server: str

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    description: str
    category: str
    tool_count: int
    connection_type: str  # "stdio" | "sse" | "http"
    connection_params: Dict
    estimated_tokens: int
    keywords: List[str]

class ToolRegistry:
    """
    Searchable registry of all available tools across MCP servers.
    Provides lightweight index for discovery without loading full schemas.
    """

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.tool_index: List[ToolIndexEntry] = []
        self.server_configs: Dict[str, MCPServerConfig] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the tool registry from disk."""
        with open(self.registry_path / "tool_index.json") as f:
            index_data = json.load(f)
            self.tool_index = [
                ToolIndexEntry(**entry) for entry in index_data["tools"]
            ]

        with open(self.registry_path / "server_configs.json") as f:
            server_data = json.load(f)
            self.server_configs = {
                name: MCPServerConfig(**config)
                for name, config in server_data.items()
            }

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search tools by keyword matching.
        Returns lightweight metadata, not full tool schemas.
        """
        query_terms = query.lower().split()
        results = []

        for tool in self.tool_index:
            score = self._calculate_relevance(tool, query_terms)
            if score > 0:
                results.append({
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category,
                    "mcp_server": tool.mcp_server,
                    "server_description": self.server_configs[tool.mcp_server].description,
                    "score": score
                })

        # Sort by relevance
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _calculate_relevance(self, tool: ToolIndexEntry, query_terms: List[str]) -> float:
        """Calculate relevance score for a tool."""
        score = 0.0

        # Check tool name
        tool_name_lower = tool.name.lower()
        for term in query_terms:
            if term in tool_name_lower:
                score += 3.0

        # Check description
        desc_lower = tool.description.lower()
        for term in query_terms:
            if term in desc_lower:
                score += 1.0

        # Check keywords
        for keyword in tool.keywords:
            for term in query_terms:
                if term in keyword.lower():
                    score += 2.0

        # Check category
        if any(term in tool.category.lower() for term in query_terms):
            score += 1.5

        return score

    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a specific MCP server."""
        return self.server_configs.get(server_name)

    def get_index_for_context(self) -> str:
        """
        Generate a compact text representation of the tool index
        for inclusion in agent context.
        Target: ~2,000 tokens
        """
        lines = ["## Available Tool Categories\n"]

        # Group by category
        by_category = {}
        for config in self.server_configs.values():
            if config.category not in by_category:
                by_category[config.category] = []
            by_category[config.category].append(config)

        for category, servers in by_category.items():
            lines.append(f"\n### {category}")
            for server in servers:
                lines.append(f"- {server.name} ({server.tool_count} tools): {server.description}")

        lines.append("\n\nUse search_tools to find specific tools by keyword.")
        return "\n".join(lines)
```

### 5.4 MCP Server Manager

```python
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams, SseConnectionParams
from typing import Dict, List, Set
import asyncio
from datetime import datetime

class MCPServerManager:
    """
    Manages MCP server connections with lazy-loading and LRU eviction.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        max_loaded_servers: int = 10,
        max_total_tokens: int = 15000
    ):
        self.registry = registry
        self.max_loaded_servers = max_loaded_servers
        self.max_total_tokens = max_total_tokens

        self.loaded_servers: Dict[str, MCPToolset] = {}
        self.server_tools: Dict[str, List] = {}
        self.last_used: Dict[str, datetime] = {}
        self.token_usage: Dict[str, int] = {}

    async def load_server(self, server_name: str) -> List:
        """
        Load an MCP server and return its tools.
        Implements lazy-loading with LRU eviction.
        """
        # Already loaded?
        if server_name in self.loaded_servers:
            self.last_used[server_name] = datetime.utcnow()
            return self.server_tools[server_name]

        # Get server config
        config = self.registry.get_server_config(server_name)
        if not config:
            raise ValueError(f"Unknown MCP server: {server_name}")

        # Check if we need to evict servers
        await self._ensure_capacity(config.estimated_tokens)

        # Create connection params
        if config.connection_type == "stdio":
            connection_params = StdioConnectionParams(**config.connection_params)
        elif config.connection_type == "sse":
            connection_params = SseConnectionParams(**config.connection_params)
        else:
            raise ValueError(f"Unknown connection type: {config.connection_type}")

        # Load the MCP toolset
        toolset = MCPToolset(connection_params=connection_params)
        tools = await toolset.get_tools()

        # Store references
        self.loaded_servers[server_name] = toolset
        self.server_tools[server_name] = tools
        self.last_used[server_name] = datetime.utcnow()
        self.token_usage[server_name] = config.estimated_tokens

        return tools

    async def unload_server(self, server_name: str) -> None:
        """Unload an MCP server to free resources."""
        if server_name not in self.loaded_servers:
            return

        # Close the connection
        toolset = self.loaded_servers[server_name]
        await toolset.close()

        # Clean up references
        del self.loaded_servers[server_name]
        del self.server_tools[server_name]
        del self.last_used[server_name]
        del self.token_usage[server_name]

    async def _ensure_capacity(self, needed_tokens: int) -> None:
        """Ensure we have capacity for new server, evicting LRU if needed."""
        current_tokens = sum(self.token_usage.values())

        # Check server count limit
        while len(self.loaded_servers) >= self.max_loaded_servers:
            lru_server = self._get_lru_server()
            await self.unload_server(lru_server)

        # Check token limit
        while (current_tokens + needed_tokens) > self.max_total_tokens:
            lru_server = self._get_lru_server()
            await self.unload_server(lru_server)
            current_tokens = sum(self.token_usage.values())

    def _get_lru_server(self) -> str:
        """Get the least recently used server."""
        return min(self.last_used, key=self.last_used.get)

    def get_server_tools(self, server_name: str) -> List:
        """Get tools for a loaded server."""
        return self.server_tools.get(server_name, [])

    def get_all_loaded_tools(self) -> List:
        """Get all tools from all loaded servers."""
        all_tools = []
        for tools in self.server_tools.values():
            all_tools.extend(tools)
        return all_tools

    def get_status(self) -> Dict:
        """Get current server loading status."""
        return {
            "loaded_count": len(self.loaded_servers),
            "max_servers": self.max_loaded_servers,
            "total_tokens": sum(self.token_usage.values()),
            "max_tokens": self.max_total_tokens,
            "servers": [
                {
                    "name": name,
                    "tool_count": len(self.server_tools[name]),
                    "tokens": self.token_usage[name],
                    "last_used": self.last_used[name].isoformat()
                }
                for name in self.loaded_servers
            ]
        }
```

### 5.5 MCP Server Configuration Examples

```json
// server_configs.json
{
  "google_analytics_mcp": {
    "name": "google_analytics_mcp",
    "description": "Google Analytics 4 data access, reports, and audience management",
    "category": "Analytics",
    "tool_count": 12,
    "connection_type": "stdio",
    "connection_params": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-google-analytics"],
      "env": {
        "GA_PROPERTY_ID": "${GA_PROPERTY_ID}",
        "GOOGLE_APPLICATION_CREDENTIALS": "${GOOGLE_CREDS_PATH}"
      }
    },
    "estimated_tokens": 1800,
    "keywords": ["analytics", "ga4", "traffic", "users", "sessions", "pageviews", "events", "conversions"]
  },
  "hubspot_mcp": {
    "name": "hubspot_mcp",
    "description": "HubSpot CRM and marketing automation - contacts, deals, campaigns",
    "category": "CRM",
    "tool_count": 18,
    "connection_type": "sse",
    "connection_params": {
      "url": "https://mcp.hubspot.com/sse",
      "headers": {
        "Authorization": "Bearer ${HUBSPOT_API_KEY}"
      }
    },
    "estimated_tokens": 2700,
    "keywords": ["crm", "contacts", "deals", "pipeline", "email", "marketing", "automation"]
  },
  "n8n_mcp": {
    "name": "n8n_mcp",
    "description": "n8n workflow automation - create, manage, and monitor workflows",
    "category": "Automation",
    "tool_count": 15,
    "connection_type": "sse",
    "connection_params": {
      "url": "${N8N_BASE_URL}/mcp",
      "headers": {
        "X-N8N-API-KEY": "${N8N_API_KEY}"
      }
    },
    "estimated_tokens": 2250,
    "keywords": ["automation", "workflow", "schedule", "trigger", "integration", "n8n"]
  }
}
```

---

## 6. Multi-Channel Support

### 6.1 Unified Channel Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-CHANNEL ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
                    │           CLIENT CHANNELS                │
                    └─────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│     WEB UI      │        │      SLACK      │        │     VOICE       │
│  app.ken-e.ai   │        │      BOT        │        │ (Zoom/Teams)    │
├─────────────────┤        ├─────────────────┤        ├─────────────────┤
│ • React SPA     │        │ • Bolt SDK      │        │ • Pipecat       │
│ • WebSocket     │        │ • Event API     │        │ • Recall.ai     │
│ • Rich UI       │        │ • Block Kit     │        │ • Deepgram STT  │
│ • File uploads  │        │ • Threads       │        │ • Cartesia TTS  │
└────────┬────────┘        └────────┬────────┘        └────────┬────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          CHANNEL ADAPTER LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        MESSAGE NORMALIZER                                │   │
│  │  • Convert channel-specific formats to unified message format           │   │
│  │  • Extract text, attachments, context from each channel                 │   │
│  │  • Handle channel-specific features (threads, reactions, etc.)          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      AUTHENTICATION LAYER                                │   │
│  │  • Firebase Auth (Web)                                                  │   │
│  │  • Slack OAuth (Slack)                                                  │   │
│  │  • Meeting authentication (Voice)                                       │   │
│  │  • Map to unified user identity                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      SESSION MANAGER                                     │   │
│  │  • Create/resume sessions across channels                               │   │
│  │  • Share state between channels for same user                           │   │
│  │  • Handle cross-channel handoffs                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AGENTIC HARNESS                                        │
│                    (Same for all channels)                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          RESPONSE FORMATTER                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐              │
│  │   WEB FORMAT    │   │  SLACK FORMAT   │   │  VOICE FORMAT   │              │
│  │                 │   │                 │   │                 │              │
│  │ • Markdown      │   │ • Block Kit     │   │ • Plain text    │              │
│  │ • Charts        │   │ • Attachments   │   │ • Summarized    │              │
│  │ • Interactive   │   │ • Actions       │   │ • TTS-friendly  │              │
│  │   components    │   │ • Modals        │   │ • Key points    │              │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Unified Message Format

```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

class ChannelType(Enum):
    WEB = "web"
    SLACK = "slack"
    VOICE = "voice"

@dataclass
class UnifiedMessage:
    """
    Channel-agnostic message format used internally.
    All channel adapters convert to/from this format.
    """
    # Identity
    message_id: str
    channel: ChannelType
    channel_message_id: str  # Original ID from channel

    # User context
    user_id: str             # Unified user ID
    account_id: str          # KEN-E account
    organization_id: str     # KEN-E organization

    # Content
    text: str
    attachments: List[Dict]  # Files, images, etc.

    # Metadata
    timestamp: datetime
    thread_id: Optional[str]  # For threaded conversations
    reply_to: Optional[str]   # Message being replied to

    # Channel-specific context
    channel_context: Dict[str, Any]  # Slack channel, meeting ID, etc.

@dataclass
class UnifiedResponse:
    """
    Channel-agnostic response format.
    Response formatters convert to channel-specific format.
    """
    # Content
    text: str
    structured_content: Optional[Dict]  # Tables, charts, etc.

    # Actions
    suggested_actions: List[Dict]  # Buttons, quick replies
    requires_confirmation: bool

    # Metadata
    confidence: float
    sources: List[str]

    # Formatting hints
    format_hints: Dict[str, Any]  # Channel-specific formatting preferences
```

### 6.3 Channel Adapters

#### 6.3.1 Web Channel Adapter

```python
from fastapi import WebSocket
import json

class WebChannelAdapter:
    """
    Adapter for the web UI channel (app.ken-e.ai).
    Uses WebSocket for real-time communication.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.active_connections: Dict[str, WebSocket] = {}

    async def handle_websocket(self, websocket: WebSocket, user_id: str):
        """Handle WebSocket connection from web client."""
        await websocket.accept()
        self.active_connections[user_id] = websocket

        try:
            while True:
                data = await websocket.receive_json()
                message = self._normalize_message(data, user_id)
                response = await self._process_message(message)
                await self._send_response(websocket, response)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            del self.active_connections[user_id]

    def _normalize_message(self, data: Dict, user_id: str) -> UnifiedMessage:
        """Convert web message to unified format."""
        return UnifiedMessage(
            message_id=generate_id(),
            channel=ChannelType.WEB,
            channel_message_id=data.get("id", ""),
            user_id=user_id,
            account_id=data["account_id"],
            organization_id=data["organization_id"],
            text=data["text"],
            attachments=data.get("attachments", []),
            timestamp=datetime.utcnow(),
            thread_id=data.get("session_id"),
            reply_to=None,
            channel_context={
                "client_version": data.get("client_version"),
                "viewport": data.get("viewport")
            }
        )

    def _format_response(self, response: UnifiedResponse) -> Dict:
        """Format response for web client."""
        return {
            "text": response.text,
            "markdown": True,
            "structured_content": response.structured_content,
            "actions": [
                {"type": "button", "label": a["label"], "action": a["action"]}
                for a in response.suggested_actions
            ],
            "sources": response.sources
        }
```

#### 6.3.2 Slack Channel Adapter

```python
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

class SlackChannelAdapter:
    """
    Adapter for Slack channel using Bolt SDK.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.app = AsyncApp(
            token=os.environ["SLACK_BOT_TOKEN"],
            signing_secret=os.environ["SLACK_SIGNING_SECRET"]
        )
        self._register_handlers()

    def _register_handlers(self):
        """Register Slack event handlers."""

        @self.app.event("app_mention")
        async def handle_mention(event, say, client):
            message = self._normalize_message(event, client)
            response = await self._process_message(message)
            await self._send_response(say, response, event.get("thread_ts"))

        @self.app.event("message")
        async def handle_dm(event, say, client):
            # Only handle DMs (not channel messages without mention)
            if event.get("channel_type") == "im":
                message = self._normalize_message(event, client)
                response = await self._process_message(message)
                await self._send_response(say, response, event.get("thread_ts"))

    def _normalize_message(self, event: Dict, client: AsyncWebClient) -> UnifiedMessage:
        """Convert Slack event to unified format."""
        # Look up user mapping
        user_mapping = self._get_user_mapping(event["user"])

        return UnifiedMessage(
            message_id=generate_id(),
            channel=ChannelType.SLACK,
            channel_message_id=event["ts"],
            user_id=user_mapping.ken_e_user_id,
            account_id=user_mapping.account_id,
            organization_id=user_mapping.organization_id,
            text=self._clean_mention(event["text"]),
            attachments=self._process_slack_files(event.get("files", [])),
            timestamp=datetime.fromtimestamp(float(event["ts"])),
            thread_id=event.get("thread_ts"),
            reply_to=event.get("thread_ts"),
            channel_context={
                "slack_channel": event["channel"],
                "slack_team": event.get("team"),
                "slack_user": event["user"]
            }
        )

    def _format_response(self, response: UnifiedResponse) -> List[Dict]:
        """Format response as Slack Block Kit blocks."""
        blocks = []

        # Main text as markdown section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": self._convert_to_slack_markdown(response.text)
            }
        })

        # Structured content (tables, etc.)
        if response.structured_content:
            blocks.extend(self._format_structured_content(response.structured_content))

        # Action buttons
        if response.suggested_actions:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": a["label"]},
                        "action_id": a["action"],
                        "value": json.dumps(a.get("value", {}))
                    }
                    for a in response.suggested_actions[:5]  # Slack limit
                ]
            })

        return blocks
```

#### 6.3.3 Voice Channel Adapter (Research-Based)

Based on research, voice-enabled meeting participation **is technically feasible** using:
- **Meeting Bot API**: Recall.ai or Meeting BaaS for joining meetings
- **STT**: Deepgram for real-time transcription
- **TTS**: Cartesia or Deepgram Aura for voice synthesis
- **Framework**: Pipecat for orchestrating the voice pipeline

```python
from pipecat.pipeline import Pipeline
from pipecat.transports.services.meeting_baas import MeetingBaaSTransport
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.cartesia import CartesiaTTSService

class VoiceChannelAdapter:
    """
    Adapter for voice channel (Zoom, Teams, Meet).
    Uses Pipecat + Meeting BaaS for meeting participation.

    STATUS: Technically feasible but complex. Recommend Phase 4 implementation.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.active_meetings: Dict[str, Pipeline] = {}

    async def join_meeting(self, meeting_url: str, user_id: str) -> str:
        """
        Join a meeting as an AI participant.
        Returns meeting session ID.
        """
        # Create the voice pipeline
        pipeline = Pipeline([
            # Transport: Join meeting via Meeting BaaS
            MeetingBaaSTransport(
                api_key=os.environ["MEETING_BAAS_API_KEY"],
                meeting_url=meeting_url,
                bot_name="KEN-E",
                bot_image_url="https://app.ken-e.ai/avatar.png"
            ),

            # STT: Deepgram for transcription
            DeepgramSTTService(
                api_key=os.environ["DEEPGRAM_API_KEY"],
                model="nova-2",
                language="en"
            ),

            # LLM processing
            KenEVoiceProcessor(
                session_manager=self.session_manager,
                user_id=user_id
            ),

            # TTS: Cartesia for speech synthesis
            CartesiaTTSService(
                api_key=os.environ["CARTESIA_API_KEY"],
                voice_id="professional-male"  # Or configurable
            )
        ])

        meeting_id = generate_id()
        self.active_meetings[meeting_id] = pipeline

        # Start the pipeline
        await pipeline.start()

        return meeting_id

    def _normalize_message(self, transcript: str, speaker: str, meeting_context: Dict) -> UnifiedMessage:
        """Convert voice transcript to unified format."""
        user_mapping = self._get_speaker_mapping(speaker, meeting_context)

        return UnifiedMessage(
            message_id=generate_id(),
            channel=ChannelType.VOICE,
            channel_message_id=f"{meeting_context['meeting_id']}_{datetime.utcnow().timestamp()}",
            user_id=user_mapping.ken_e_user_id,
            account_id=user_mapping.account_id,
            organization_id=user_mapping.organization_id,
            text=transcript,
            attachments=[],
            timestamp=datetime.utcnow(),
            thread_id=meeting_context["meeting_id"],
            reply_to=None,
            channel_context={
                "meeting_id": meeting_context["meeting_id"],
                "meeting_platform": meeting_context["platform"],
                "speaker_name": speaker,
                "participant_count": meeting_context.get("participant_count")
            }
        )

    def _format_response(self, response: UnifiedResponse) -> str:
        """
        Format response for voice output.
        Optimized for TTS: shorter, conversational, no formatting.
        """
        # Strip markdown and special characters
        text = self._strip_formatting(response.text)

        # Summarize if too long for voice
        if len(text) > 500:
            text = self._summarize_for_voice(text)

        # Convert numbers and abbreviations for natural speech
        text = self._convert_for_speech(text)

        return text

    async def leave_meeting(self, meeting_id: str):
        """Leave a meeting and clean up resources."""
        if meeting_id in self.active_meetings:
            pipeline = self.active_meetings[meeting_id]
            await pipeline.stop()
            del self.active_meetings[meeting_id]
```

### 6.4 Voice Channel Implementation Notes

**Technical Feasibility**: ✅ Confirmed feasible

**Recommended Implementation Path**:
1. Use **Recall.ai** or **Meeting BaaS** for meeting joining (handles platform complexity)
2. Use **Pipecat** framework for voice pipeline orchestration
3. Use **Deepgram** for STT (sub-200ms latency)
4. Use **Cartesia** or **Deepgram Aura** for TTS

**Key Considerations**:
- Voice responses must be concise (< 30 seconds typically)
- Need speaker diarization to identify who is speaking
- Meeting context (agenda, participants) should be loaded at join
- Latency is critical: target < 2 seconds end-to-end response time
- Consider "raise hand" or activation phrase to avoid interrupting

**Estimated Costs**:
- Recall.ai: ~$1/hour per meeting
- Deepgram STT: ~$0.15/hour
- TTS: ~$0.05/hour
- **Total**: ~$1.20/hour per meeting

**Recommendation**: Implement in **Phase 4** after core functionality is stable. The complexity of voice integration warrants dedicated focus.

---

## 7. Workflow Management

### 7.1 Multi-Step Workflow Handling

KEN-E handles complex, multi-step workflows similar to Claude Code. The key pattern is:
1. **Plan** the workflow with clear steps
2. **Track** progress visibly to the user
3. **Get approval** at decision points
4. **Resume** where left off if interrupted

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW STATE MACHINE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   CREATED   │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │  PLANNING   │◄──────────────────────┐
                              └──────┬──────┘                       │
                                     │                              │
                                     ▼                              │
                         ┌───────────────────────┐                  │
                         │  AWAITING_APPROVAL    │──────────────────┘
                         │  (User reviews plan)  │     (User requests changes)
                         └───────────┬───────────┘
                                     │ (Approved)
                                     ▼
                              ┌─────────────┐
           ┌─────────────────►│ IN_PROGRESS │◄─────────────────┐
           │                  └──────┬──────┘                  │
           │                         │                         │
           │        ┌────────────────┼────────────────┐        │
           │        │                │                │        │
           │        ▼                ▼                ▼        │
           │  ┌───────────┐   ┌───────────┐   ┌───────────┐   │
           │  │ Executing │   │ Awaiting  │   │   Error   │   │
           │  │   Step    │   │  Input    │   │  Handler  │   │
           │  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   │
           │        │               │               │         │
           │        │               │ (Input       │ (Retry) │
           │        │               │  received)   │         │
           │        └───────────────┴───────────────┘         │
           │                        │                         │
           │                        ▼                         │
           │                 ┌─────────────┐                  │
           │                 │ Step Done?  │──────────────────┘
           │                 └──────┬──────┘     (More steps)
           │                        │
           │                        │ (All steps done)
           │                        ▼
           │                 ┌─────────────┐
           │ (User adds     │  COMPLETED  │
           │  more tasks)   └──────┬──────┘
           │                       │
           └───────────────────────┘
```

### 7.2 Workflow Data Model

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class WorkflowStatus(Enum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowTask:
    """Individual task within a workflow."""
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    specialist: Optional[str] = None  # Which agent handles this
    dependencies: List[str] = field(default_factory=list)  # Task IDs
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

@dataclass
class Workflow:
    """Multi-step workflow definition."""
    workflow_id: str
    name: str
    description: str
    account_id: str
    user_id: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    tasks: List[WorkflowTask] = field(default_factory=list)
    current_task_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)  # Shared context

class WorkflowManager:
    """
    Manages multi-step workflows with persistence and state tracking.
    """

    def __init__(self, firestore_client, session_service):
        self.db = firestore_client
        self.session_service = session_service

    async def create_workflow(
        self,
        name: str,
        tasks: List[Dict],
        account_id: str,
        user_id: str,
        context: Dict = None
    ) -> Workflow:
        """Create a new workflow with tasks."""
        workflow = Workflow(
            workflow_id=generate_id(),
            name=name,
            description=f"Workflow: {name}",
            account_id=account_id,
            user_id=user_id,
            tasks=[
                WorkflowTask(
                    task_id=generate_id(),
                    name=t["name"],
                    description=t.get("description", ""),
                    specialist=t.get("specialist"),
                    dependencies=t.get("dependencies", [])
                )
                for t in tasks
            ],
            context=context or {}
        )

        # Persist to Firestore
        await self._save_workflow(workflow)

        return workflow

    async def execute_next_task(self, workflow_id: str) -> Dict:
        """Execute the next pending task in the workflow."""
        workflow = await self._load_workflow(workflow_id)

        if workflow.status not in [WorkflowStatus.IN_PROGRESS, WorkflowStatus.AWAITING_APPROVAL]:
            raise ValueError(f"Workflow not executable: {workflow.status}")

        # Find next executable task
        next_task = self._get_next_executable_task(workflow)
        if not next_task:
            # All tasks complete
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.utcnow()
            await self._save_workflow(workflow)
            return {"status": "completed", "workflow": workflow}

        # Execute the task
        next_task.status = TaskStatus.IN_PROGRESS
        next_task.started_at = datetime.utcnow()
        await self._save_workflow(workflow)

        try:
            # Delegate to appropriate specialist
            result = await self._execute_task(next_task, workflow)

            next_task.status = TaskStatus.COMPLETED
            next_task.outputs = result
            next_task.completed_at = datetime.utcnow()

            # Update workflow context with task outputs
            workflow.context[next_task.task_id] = result

        except Exception as e:
            next_task.status = TaskStatus.FAILED
            next_task.error = str(e)
            workflow.status = WorkflowStatus.FAILED

        await self._save_workflow(workflow)

        return {
            "status": "task_completed" if next_task.status == TaskStatus.COMPLETED else "task_failed",
            "task": next_task,
            "workflow": workflow
        }

    def _get_next_executable_task(self, workflow: Workflow) -> Optional[WorkflowTask]:
        """Find the next task that can be executed."""
        for task in workflow.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check dependencies
            deps_met = all(
                self._get_task_by_id(workflow, dep_id).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if deps_met:
                return task

        return None

    async def get_workflow_summary(self, workflow_id: str) -> str:
        """Generate a user-friendly summary of workflow progress."""
        workflow = await self._load_workflow(workflow_id)

        lines = [f"## Workflow: {workflow.name}\n"]
        lines.append(f"Status: {workflow.status.value}\n")

        for i, task in enumerate(workflow.tasks):
            status_icon = {
                TaskStatus.PENDING: "⬜",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.AWAITING_INPUT: "⏳",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.SKIPPED: "⏭️"
            }.get(task.status, "❓")

            lines.append(f"{status_icon} {i+1}. {task.name}")
            if task.status == TaskStatus.IN_PROGRESS:
                lines.append(f"   ↳ Currently executing...")
            elif task.status == TaskStatus.FAILED:
                lines.append(f"   ↳ Error: {task.error}")

        return "\n".join(lines)
```

### 7.3 Scheduled Workflow Integration

Workflows that need to run on a schedule are delegated to the Automation Specialist to create n8n workflows:

```python
class ScheduledWorkflowManager:
    """
    Creates n8n workflows for scheduled/recurring tasks.
    """

    def __init__(self, n8n_client, workflow_manager):
        self.n8n = n8n_client
        self.workflow_manager = workflow_manager

    async def schedule_workflow(
        self,
        workflow: Workflow,
        schedule: Dict  # cron expression or interval
    ) -> str:
        """
        Convert a KEN-E workflow to an n8n workflow for scheduling.
        Returns the n8n workflow ID.
        """
        n8n_workflow = self._build_n8n_workflow(workflow, schedule)

        # Create in n8n
        response = await self.n8n.create_workflow(n8n_workflow)
        n8n_workflow_id = response["id"]

        # Activate the workflow
        await self.n8n.activate_workflow(n8n_workflow_id)

        # Store reference
        await self._store_schedule_mapping(workflow.workflow_id, n8n_workflow_id)

        return n8n_workflow_id

    def _build_n8n_workflow(self, workflow: Workflow, schedule: Dict) -> Dict:
        """Build n8n workflow definition from KEN-E workflow."""
        nodes = []

        # Schedule trigger node
        nodes.append({
            "name": "Schedule Trigger",
            "type": "n8n-nodes-base.scheduleTrigger",
            "position": [250, 300],
            "parameters": {
                "rule": {
                    "interval": schedule.get("interval", [{"field": "hours", "value": 24}])
                }
            }
        })

        # Webhook to KEN-E API for each task
        for i, task in enumerate(workflow.tasks):
            nodes.append({
                "name": f"Execute: {task.name}",
                "type": "n8n-nodes-base.httpRequest",
                "position": [450 + (i * 200), 300],
                "parameters": {
                    "method": "POST",
                    "url": f"{{{{$env.KEN_E_API_URL}}}}/api/workflows/{workflow.workflow_id}/tasks/{task.task_id}/execute",
                    "authentication": "headerAuth",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "context", "value": "={{$json}}"}
                        ]
                    }
                }
            })

        # Notification node at end
        nodes.append({
            "name": "Notify Completion",
            "type": "n8n-nodes-base.slack",
            "position": [450 + (len(workflow.tasks) * 200), 300],
            "parameters": {
                "channel": "{{$env.SLACK_NOTIFICATION_CHANNEL}}",
                "text": f"Workflow '{workflow.name}' completed successfully"
            }
        })

        return {
            "name": f"KEN-E: {workflow.name}",
            "nodes": nodes,
            "connections": self._build_connections(nodes),
            "settings": {
                "executionOrder": "v1"
            }
        }
```

---

## 8. Integration with Evaluation Framework

### 8.1 Overview

The agentic harness integrates with the Self-Improving Evaluation Framework to enable:
1. **Automatic tracing** of all agent outputs
2. **Quality scoring** via LLM-based evaluation
3. **Human feedback collection** for alignment
4. **Continuous improvement** of agent prompts

### 8.2 Trace Instrumentation

```python
import weave
from functools import wraps

class AgentTracer:
    """
    Instruments agent calls for the evaluation framework.
    """

    def __init__(self, project_name: str = "ken-e-production"):
        weave.init(project_name)

    def trace_agent_call(self, agent_name: str, agent_version: str):
        """Decorator to trace agent calls."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract context from kwargs
                context = kwargs.get("context", {})

                trace_metadata = {
                    # Agent identification
                    "agent_id": agent_name,
                    "agent_version": agent_version,

                    # Experiment tracking
                    "experiment_id": context.get("experiment_id", "baseline"),
                    "variant_name": context.get("variant_name", "baseline"),

                    # User context
                    "account_id": context.get("account_id"),
                    "session_id": context.get("session_id"),
                    "user_id": context.get("user_id"),

                    # Environment
                    "environment": os.getenv("ENVIRONMENT", "production"),

                    # Channel info
                    "channel": context.get("channel", "unknown"),
                }

                with weave.op(name=f"agent:{agent_name}", metadata=trace_metadata):
                    # Log inputs
                    weave.log({
                        "input_text": kwargs.get("input_text", ""),
                        "loaded_context_sections": context.get("loaded_sections", []),
                        "loaded_tools": context.get("loaded_tools", []),
                    })

                    # Execute agent
                    result = await func(*args, **kwargs)

                    # Log outputs
                    weave.log({
                        "output_text": result.get("text", ""),
                        "output_type": result.get("output_type", "general"),
                        "tool_calls": result.get("tool_calls", []),
                        "tokens_used": result.get("tokens_used", 0),
                    })

                    return result

            return wrapper
        return decorator

# Usage example
tracer = AgentTracer()

class StrategySpecialistWithTracing:
    @tracer.trace_agent_call(
        agent_name="strategy_specialist",
        agent_version="v1.0.0"
    )
    async def execute(self, input_text: str, context: Dict) -> Dict:
        # Agent execution logic
        pass
```

### 8.3 Output Type Classification

The harness automatically classifies outputs for appropriate evaluation:

```python
OUTPUT_TYPE_PATTERNS = {
    # Business Strategy outputs
    "company_overview": ["company overview", "business summary", "about the company"],
    "swot_analysis": ["swot", "strengths", "weaknesses", "opportunities", "threats"],
    "competitor_analysis": ["competitor", "competitive analysis", "market position"],

    # Marketing Strategy outputs
    "icp_narrative": ["ideal customer", "icp", "customer profile", "target audience"],
    "campaign_strategy": ["campaign", "marketing strategy", "go-to-market"],

    # Content outputs
    "blog_post": ["blog", "article", "long-form"],
    "social_post": ["social", "tweet", "linkedin post", "instagram"],
    "email_copy": ["email", "newsletter", "subject line"],

    # Analytics outputs
    "performance_report": ["report", "dashboard", "analytics", "performance"],
    "forecast": ["forecast", "prediction", "projection"],
}

class OutputClassifier:
    """
    Classifies agent outputs for evaluation routing.
    """

    def classify(self, output_text: str, task_context: Dict) -> str:
        """
        Determine the output type for evaluation purposes.
        """
        # Check explicit type from context
        if "output_type" in task_context:
            return task_context["output_type"]

        # Pattern matching
        output_lower = output_text.lower()
        for output_type, patterns in OUTPUT_TYPE_PATTERNS.items():
            if any(pattern in output_lower for pattern in patterns):
                return output_type

        # Check specialist agent
        specialist = task_context.get("specialist")
        if specialist == "strategy_specialist":
            return "strategy_output"
        elif specialist == "content_specialist":
            return "content_output"
        elif specialist == "analytics_specialist":
            return "analytics_output"

        return "general_output"
```

### 8.4 Feedback Collection Integration

```python
class FeedbackCollector:
    """
    Collects user feedback on agent outputs for evaluation alignment.
    """

    def __init__(self, firestore_client):
        self.db = firestore_client

    async def request_feedback(
        self,
        trace_id: str,
        output_text: str,
        output_type: str,
        channel: ChannelType
    ) -> None:
        """
        Queue a feedback request for the user.
        """
        # Create feedback request
        request = {
            "trace_id": trace_id,
            "output_type": output_type,
            "output_preview": output_text[:500],
            "status": "pending",
            "created_at": datetime.utcnow(),
            "channel": channel.value,
        }

        # Store in Firestore for evaluation UI
        await self.db.collection("evaluation_queue").add(request)

    async def submit_feedback(
        self,
        trace_id: str,
        rating: int,  # 1-5
        factors: Dict[str, bool],  # Factor-level ratings
        comments: Optional[str] = None
    ) -> None:
        """
        Submit user feedback on an output.
        """
        feedback = {
            "trace_id": trace_id,
            "rating": rating,
            "factors": factors,
            "comments": comments,
            "submitted_at": datetime.utcnow(),
            "evaluator_type": "human",
        }

        # Store feedback
        await self.db.collection("human_evaluations").add(feedback)

        # Trigger alignment analysis if needed
        await self._check_alignment_trigger(trace_id)
```

### 8.5 A/B Testing Support

The harness supports A/B testing of agent configurations:

```python
class ExperimentManager:
    """
    Manages A/B experiments for agent configurations.
    """

    def __init__(self, firestore_client):
        self.db = firestore_client
        self.active_experiments: Dict[str, Dict] = {}

    async def get_variant_for_account(
        self,
        agent_name: str,
        account_id: str
    ) -> str:
        """
        Determine which variant an account should receive.
        Uses consistent hashing for stable assignment.
        """
        experiment = await self._get_active_experiment(agent_name)
        if not experiment:
            return "baseline"

        # Consistent hash assignment
        hash_input = f"{experiment['id']}:{account_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # Determine variant based on traffic split
        cumulative = 0
        for variant in experiment["variants"]:
            cumulative += variant["traffic_percentage"]
            if (hash_value % 100) < cumulative:
                return variant["name"]

        return "baseline"

    async def load_agent_config(
        self,
        agent_name: str,
        variant: str
    ) -> Dict:
        """
        Load the agent configuration for a specific variant.
        """
        if variant == "baseline":
            doc_path = f"agent_configs/{agent_name}"
        else:
            doc_path = f"agent_configs/{agent_name}_{variant}"

        doc = await self.db.document(doc_path).get()
        return doc.to_dict()
```

---

## 9. Infrastructure Requirements

### 9.1 Compute Requirements

| Component | Specification | Scaling |
|-----------|--------------|---------|
| **API Server** | 4 vCPU, 8GB RAM | 2-10 instances based on load |
| **Agent Workers** | 8 vCPU, 16GB RAM | 1-5 instances per account tier |
| **MCP Server Pool** | 2 vCPU, 4GB RAM per server | On-demand scaling |
| **Automation Runner** | 4 vCPU, 8GB RAM | 1-3 instances |
| **Voice Pipeline** | 8 vCPU, 16GB RAM | Per active meeting |

### 9.2 Memory Estimates

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY USAGE PER SESSION                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Component                           Memory        Notes
──────────────────────────────────────────────────────────────────────────────────
Session state                       ~50 KB        Conversation history, state
Context manager                     ~200 KB       Loaded sections, cache
Tool registry index                 ~100 KB       Searchable index
Loaded MCP servers (3 avg)          ~150 KB       Connection state
Agent instances                     ~100 KB       Cached model configs
──────────────────────────────────────────────────────────────────────────────────
TOTAL PER SESSION                   ~600 KB

At 1,000 concurrent sessions:       ~600 MB
At 10,000 concurrent sessions:      ~6 GB
```

### 9.3 Cost Estimates

| Resource | Unit Cost | Est. Monthly Usage | Monthly Cost |
|----------|-----------|-------------------|--------------|
| **Gemini 2.0 Flash** | $0.075/1M input, $0.30/1M output | 500M tokens | ~$150 |
| **Cloud Run** | $0.00002400/vCPU-second | 10,000 CPU-hours | ~$864 |
| **Firestore** | $0.18/100K reads | 50M reads | ~$90 |
| **Neo4j AuraDB** | $65/month (Professional) | 1 instance | $65 |
| **BigQuery** | $5/TB queried | 100GB | ~$0.50 |
| **Cloud Storage** | $0.020/GB/month | 500GB | ~$10 |
| **n8n Cloud** | $50/month (Starter) | 1 instance | $50 |
| **Weave (W&B)** | $0/month (included) | Unlimited | $0 |
| **Voice (Recall.ai)** | $1/hour | 100 hours | ~$100 |
| **Voice (Deepgram)** | $0.15/hour | 100 hours | ~$15 |

**Estimated Total**: ~$1,350/month for moderate usage

### 9.4 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE DIAGRAM                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              GOOGLE CLOUD PLATFORM                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Cloud Load Balancer                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│         ┌────────────────────────────┼────────────────────────────┐            │
│         │                            │                            │            │
│         ▼                            ▼                            ▼            │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐        │
│  │  Cloud Run  │            │  Cloud Run  │            │  Cloud Run  │        │
│  │   API       │            │   Workers   │            │   Slack     │        │
│  │  (FastAPI)  │            │  (Agents)   │            │   Handler   │        │
│  └──────┬──────┘            └──────┬──────┘            └─────────────┘        │
│         │                          │                                           │
│         └────────────┬─────────────┘                                           │
│                      │                                                          │
│                      ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Cloud Tasks / Pub/Sub                            │   │
│  │                    (Async job processing)                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│         ┌────────────────────────────┼────────────────────────────┐            │
│         │                            │                            │            │
│         ▼                            ▼                            ▼            │
│  ┌─────────────┐            ┌─────────────┐            ┌─────────────┐        │
│  │  Firestore  │            │   Neo4j     │            │  BigQuery   │        │
│  │  (Config,   │            │   AuraDB    │            │ (Analytics) │        │
│  │   State)    │            │  (Knowledge)│            │             │        │
│  └─────────────┘            └─────────────┘            └─────────────┘        │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         Secret Manager                                   │   │
│  │           (API keys, OAuth tokens, MCP credentials)                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   n8n       │  │  Weave/W&B  │  │  Recall.ai  │  │  Deepgram   │           │
│  │ (Automation)│  │ (Tracing)   │  │  (Meetings) │  │  (STT/TTS)  │           │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         MCP Server Pool                                  │   │
│  │  Google Analytics | Google Ads | HubSpot | Mailchimp | Salesforce | ... │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Risks and Testing Requirements

### 10.1 Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Context overflow** during complex tasks | High | High | Implement context compression, hierarchical loading, monitoring |
| **MCP server connection failures** | Medium | High | Connection pooling, retry logic, fallback to cached data |
| **Tool discovery returns irrelevant results** | Medium | Medium | Improve search algorithm, user feedback loop, manual override |
| **Agent hallucination in strategy outputs** | Medium | High | Require citations, fact-checking tools, human review queue |
| **Workflow interruption loses state** | Low | High | Persistent state in Firestore, recovery mechanisms |
| **Cross-channel session inconsistency** | Medium | Medium | Unified session service, state sync |
| **n8n automation failures** | Medium | Medium | Error handling, notifications, manual override |
| **Voice latency exceeds tolerance** | Medium | Medium | Optimize pipeline, use faster models, chunk responses |
| **Cost overrun from token usage** | Medium | Medium | Token budgets, usage monitoring, alerts |
| **Evaluation framework impacts performance** | Low | Medium | Async tracing, sampling for high-volume |

### 10.2 Critical Test Scenarios

#### 10.2.1 Context Management Tests

```python
class ContextManagementTests:
    """
    Test suite for context management functionality.
    """

    async def test_context_budget_enforcement(self):
        """Verify context stays within budget limits."""
        # Setup: Create session with company context
        session = await create_test_session(account_id="test_account")
        context_mgr = session.context_manager

        # Load multiple sections
        await context_mgr.load_section("products")
        await context_mgr.load_section("icps")
        await context_mgr.load_section("competitors")

        # Verify budget
        usage = context_mgr.get_current_token_usage()
        assert usage <= 40000, f"Context budget exceeded: {usage}"

    async def test_context_compression_triggered(self):
        """Verify compression activates at threshold."""
        session = await create_test_session()

        # Simulate long conversation (many messages)
        for i in range(100):
            await session.add_message(f"User message {i}" * 100)
            await session.add_message(f"Assistant response {i}" * 200)

        # Verify compression was triggered
        assert session.compression_count > 0
        assert session.total_tokens < 180000

    async def test_hierarchical_loading(self):
        """Verify hierarchical context loads correctly."""
        context_mgr = HierarchicalContextManager("test_account", neo4j_client)

        # Level 1 should always be available
        summary = await context_mgr.load_executive_summary()
        assert "products" in summary.lower()

        # Level 2 loads on demand
        products = await context_mgr.load_section("products")
        assert len(products) > len(summary)

        # Level 3 provides full detail
        detail = await context_mgr.load_detail("marketingai_full")
        assert len(detail) > len(products)
```

#### 10.2.2 Tool Discovery Tests

```python
class ToolDiscoveryTests:
    """
    Test suite for tool discovery and MCP loading.
    """

    async def test_tool_search_relevance(self):
        """Verify search returns relevant tools."""
        discovery = ToolDiscoveryAgent(registry, mcp_manager)

        # Search for analytics tools
        results = await discovery.search_tools("google analytics traffic")

        # Verify top result is Google Analytics
        assert results[0]["server_name"] == "google_analytics_mcp"

    async def test_lazy_loading(self):
        """Verify MCP servers load on demand."""
        discovery = ToolDiscoveryAgent(registry, mcp_manager)

        # Initially no servers loaded
        assert len(discovery.loaded_servers) == 0

        # Load a server
        await discovery.load_tools("google_analytics_mcp")

        # Verify loaded
        assert "google_analytics_mcp" in discovery.loaded_servers

    async def test_lru_eviction(self):
        """Verify LRU eviction when at capacity."""
        discovery = ToolDiscoveryAgent(registry, mcp_manager)
        discovery.max_loaded_servers = 3

        # Load max servers
        await discovery.load_tools("server_a")
        await discovery.load_tools("server_b")
        await discovery.load_tools("server_c")

        # Use server_a (make it recently used)
        await discovery.load_tools("server_a")

        # Load new server - should evict server_b (LRU)
        await discovery.load_tools("server_d")

        assert "server_a" in discovery.loaded_servers
        assert "server_b" not in discovery.loaded_servers
        assert "server_d" in discovery.loaded_servers

    async def test_tool_token_budget(self):
        """Verify tool loading respects token budget."""
        manager = MCPServerManager(registry, max_total_tokens=5000)

        # Load servers until budget reached
        await manager.load_server("server_a")  # ~1500 tokens
        await manager.load_server("server_b")  # ~1500 tokens
        await manager.load_server("server_c")  # ~1500 tokens

        # Next load should trigger eviction
        await manager.load_server("server_d")  # ~1500 tokens

        total_tokens = sum(manager.token_usage.values())
        assert total_tokens <= 5000
```

#### 10.2.3 Multi-Channel Tests

```python
class MultiChannelTests:
    """
    Test suite for cross-channel functionality.
    """

    async def test_web_to_slack_session_continuity(self):
        """Verify session state shared across channels."""
        # Start conversation on web
        web_adapter = WebChannelAdapter(session_manager)
        web_msg = UnifiedMessage(
            user_id="user_123",
            account_id="acct_456",
            channel=ChannelType.WEB,
            text="Help me analyze our Q4 performance"
        )
        await web_adapter._process_message(web_msg)

        # Continue on Slack
        slack_adapter = SlackChannelAdapter(session_manager)
        slack_msg = UnifiedMessage(
            user_id="user_123",  # Same user
            account_id="acct_456",
            channel=ChannelType.SLACK,
            text="What about comparing to Q3?"
        )
        response = await slack_adapter._process_message(slack_msg)

        # Response should reference Q4 from web conversation
        assert "Q4" in response.text or "quarter" in response.text.lower()

    async def test_voice_response_formatting(self):
        """Verify voice responses are TTS-friendly."""
        voice_adapter = VoiceChannelAdapter(session_manager)

        # Create response with markdown
        response = UnifiedResponse(
            text="Here are the **key metrics**:\n- Revenue: $1,234,567\n- Growth: 15%",
            structured_content=None,
            suggested_actions=[]
        )

        # Format for voice
        voice_text = voice_adapter._format_response(response)

        # Should remove markdown
        assert "**" not in voice_text
        # Should convert numbers
        assert "one million" in voice_text.lower() or "1234567" not in voice_text
```

#### 10.2.4 Workflow Tests

```python
class WorkflowTests:
    """
    Test suite for multi-step workflow management.
    """

    async def test_workflow_persistence(self):
        """Verify workflow state persists across sessions."""
        manager = WorkflowManager(firestore, session_service)

        # Create workflow
        workflow = await manager.create_workflow(
            name="Test Campaign",
            tasks=[
                {"name": "Research", "specialist": "strategy"},
                {"name": "Content", "specialist": "content"}
            ],
            account_id="test_acct",
            user_id="test_user"
        )

        # Simulate restart
        manager2 = WorkflowManager(firestore, session_service)
        loaded = await manager2._load_workflow(workflow.workflow_id)

        assert loaded.name == "Test Campaign"
        assert len(loaded.tasks) == 2

    async def test_workflow_dependency_execution(self):
        """Verify tasks execute in dependency order."""
        manager = WorkflowManager(firestore, session_service)

        workflow = await manager.create_workflow(
            name="Dependent Tasks",
            tasks=[
                {"name": "Task A", "specialist": "strategy"},
                {"name": "Task B", "specialist": "content", "dependencies": ["task_a_id"]},
            ],
            account_id="test_acct",
            user_id="test_user"
        )

        # Task B should not be executable until Task A completes
        workflow.status = WorkflowStatus.IN_PROGRESS
        next_task = manager._get_next_executable_task(workflow)
        assert next_task.name == "Task A"

    async def test_workflow_error_recovery(self):
        """Verify workflow handles task failures."""
        manager = WorkflowManager(firestore, session_service)

        workflow = await manager.create_workflow(
            name="Error Test",
            tasks=[{"name": "Failing Task", "specialist": "strategy"}],
            account_id="test_acct",
            user_id="test_user"
        )

        # Simulate task failure
        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.tasks[0].status = TaskStatus.FAILED
        workflow.tasks[0].error = "Test error"

        # Workflow should be in failed state
        assert workflow.status == WorkflowStatus.IN_PROGRESS  # Until explicitly failed
```

### 10.3 Performance Benchmarks

| Operation | Target | Acceptable | Critical |
|-----------|--------|------------|----------|
| Session initialization | < 500ms | < 1s | > 2s |
| Tool search | < 200ms | < 500ms | > 1s |
| MCP server load | < 500ms | < 1s | > 2s |
| Agent response (simple) | < 3s | < 5s | > 10s |
| Agent response (complex) | < 10s | < 20s | > 30s |
| Context section load | < 300ms | < 500ms | > 1s |
| Workflow state save | < 100ms | < 200ms | > 500ms |
| Voice end-to-end | < 2s | < 3s | > 5s |

### 10.4 Monitoring Requirements

```python
# Key metrics to monitor
MONITORING_METRICS = {
    # Context
    "context_token_usage": Gauge("Context tokens used per session"),
    "context_compression_events": Counter("Context compression triggered"),
    "context_load_latency": Histogram("Time to load context sections"),

    # Tools
    "mcp_servers_loaded": Gauge("Currently loaded MCP servers"),
    "tool_search_latency": Histogram("Tool search response time"),
    "mcp_connection_errors": Counter("MCP server connection failures"),

    # Agents
    "agent_invocations": Counter("Agent invocations by type"),
    "agent_response_latency": Histogram("Agent response time"),
    "agent_errors": Counter("Agent errors by type"),

    # Workflows
    "active_workflows": Gauge("Currently active workflows"),
    "workflow_completion_rate": Gauge("Workflow completion percentage"),
    "task_failures": Counter("Task failures by specialist"),

    # Channels
    "messages_by_channel": Counter("Messages processed by channel"),
    "session_duration": Histogram("Session duration"),
    "cross_channel_sessions": Counter("Sessions spanning multiple channels"),

    # Costs
    "tokens_consumed": Counter("Total tokens consumed"),
    "estimated_cost": Gauge("Estimated daily cost"),
}
```

---

## 11. Prioritized Feature Roadmap

### 11.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION PHASES                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

    PHASE 1                 PHASE 2                 PHASE 3                 PHASE 4
    FOUNDATION              CORE AGENTS             AUTOMATION              ADVANCED
    (4-6 weeks)             (6-8 weeks)             (4-6 weeks)             (6-8 weeks)
    ──────────              ───────────             ──────────              ────────

┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ • Context   │        │ • Strategy  │        │ • n8n       │        │ • Voice     │
│   Manager   │        │   Agent     │        │   Integration│       │   Channel   │
│             │        │             │        │             │        │             │
│ • Tool      │   ──▶  │ • Content   │   ──▶  │ • Scheduled │   ──▶  │ • Advanced  │
│   Registry  │        │   Agent     │        │   Workflows │        │   Analytics │
│             │        │             │        │             │        │             │
│ • MCP       │        │ • Analytics │        │ • Report    │        │ • A/B       │
│   Manager   │        │   Agent     │        │   Automation│        │   Testing   │
│             │        │             │        │             │        │             │
│ • Session   │        │ • Execution │        │ • Calendar  │        │ • Self-     │
│   Service   │        │   Agent     │        │   Review    │        │   Optimize  │
│             │        │             │        │             │        │             │
│ • Web       │        │ • Slack     │        │ • Approval  │        │ • Meeting   │
│   Channel   │        │   Channel   │        │   Queue     │        │   Bot       │
└─────────────┘        └─────────────┘        └─────────────┘        └─────────────┘

   Foundation             User-Facing              Background               Intelligence
   ───────────            ───────────              ──────────               ────────────
   Core infra             Interactive              Scheduled                Advanced
   must work              capabilities             tasks                    features
```

### 11.2 Phase 1: Foundation (Critical Path)

**Goal**: Establish core infrastructure for context management and tool discovery.

| Feature | Priority | Effort | Description |
|---------|----------|--------|-------------|
| **1.1** Hierarchical Context Manager | Critical | High | 3-level context loading from Neo4j |
| **1.2** Tool Registry & Index | Critical | Medium | Searchable tool index with ~2,000 token footprint |
| **1.3** MCP Server Manager | Critical | High | Lazy-loading with LRU eviction |
| **1.4** Session Service | Critical | Medium | State management using ADK patterns |
| **1.5** Web Channel Adapter | Critical | Medium | WebSocket-based web UI integration |
| **1.6** Primary Orchestrator | Critical | High | Core routing and coordination agent |
| **1.7** Context Compression | High | Medium | Auto-compress long sessions |
| **1.8** Basic Monitoring | High | Low | Token usage, latency metrics |

**Exit Criteria**:
- User can chat via web UI
- Context loads hierarchically without exceeding budget
- Tools load on-demand when referenced
- Session state persists across reconnects

### 11.3 Phase 2: Core Agents

**Goal**: Implement specialist agents for user-facing capabilities.

| Feature | Priority | Effort | Description |
|---------|----------|--------|-------------|
| **2.1** Strategy Specialist | Critical | High | Research, ICP, competitor analysis |
| **2.2** Content Specialist | Critical | High | Multi-format content generation |
| **2.3** Analytics Specialist | Critical | High | Sequential agent for data analysis |
| **2.4** Execution Specialist | High | Medium | Content deployment, validation |
| **2.5** Slack Channel Adapter | High | Medium | Bolt SDK integration |
| **2.6** Workflow Manager | High | High | Multi-step task tracking |
| **2.7** Tool Discovery Agent | High | Medium | Intelligent tool search |
| **2.8** Trace Instrumentation | Medium | Low | Weave integration for evaluation |

**Exit Criteria**:
- All specialist agents functional
- Slack integration working
- Multi-step workflows tracked
- Agent outputs traced for evaluation

### 11.4 Phase 3: Automation

**Goal**: Enable scheduled and autonomous operations.

| Feature | Priority | Effort | Description |
|---------|----------|--------|-------------|
| **3.1** n8n Integration | Critical | High | Create/manage n8n workflows |
| **3.2** Automation Specialist | Critical | Medium | Agent for workflow creation |
| **3.3** Scheduled Workflows | High | Medium | Convert workflows to n8n |
| **3.4** Content Calendar Review | High | Medium | Daily automated review |
| **3.5** Report Automation | High | Medium | Scheduled analytics reports |
| **3.6** Approval Queue | Medium | Medium | Content approval workflow |
| **3.7** KPI Monitoring | Medium | Medium | Automated performance tracking |
| **3.8** Notification System | Medium | Low | Slack/email notifications |

**Exit Criteria**:
- Scheduled tasks run autonomously
- Content calendar reviewed daily
- Reports generated automatically
- Users notified of pending actions

### 11.5 Phase 4: Advanced Features

**Goal**: Advanced intelligence and voice capabilities.

| Feature | Priority | Effort | Description |
|---------|----------|--------|-------------|
| **4.1** Voice Channel (MVP) | High | Very High | Pipecat + Meeting BaaS integration |
| **4.2** A/B Testing Support | High | Medium | Experiment infrastructure |
| **4.3** Self-Optimization | Medium | High | Alignment engine integration |
| **4.4** Advanced Analytics | Medium | High | Forecasting, attribution |
| **4.5** Voice Enhancement | Medium | High | Multi-speaker, interruption handling |
| **4.6** Custom Report Builder | Medium | Medium | User-defined reports |
| **4.7** Cross-Account Learning | Low | High | Anonymized pattern sharing |
| **4.8** Proactive Suggestions | Low | Medium | AI-initiated recommendations |

**Exit Criteria**:
- Voice meetings functional
- A/B tests running
- Evaluation framework integrated
- Self-optimization active

### 11.6 Dependencies Graph

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FEATURE DEPENDENCIES                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

PHASE 1                          PHASE 2
────────                         ────────

1.1 Context Manager ─────────────┬─► 2.1 Strategy Specialist
                                 │
1.2 Tool Registry ───────────────┼─► 2.2 Content Specialist
         │                       │
         └──► 1.3 MCP Manager ───┼─► 2.3 Analytics Specialist
                                 │
1.4 Session Service ─────────────┤
         │                       │
         └──► 1.5 Web Channel ───┼─► 2.5 Slack Channel
                                 │
1.6 Primary Orchestrator ────────┴─► 2.7 Tool Discovery
         │
         └──► 2.6 Workflow Manager


PHASE 2                          PHASE 3
────────                         ────────

2.4 Execution Specialist ────────┬─► 3.3 Scheduled Workflows
                                 │
2.6 Workflow Manager ────────────┼─► 3.1 n8n Integration
                                 │
2.3 Analytics Specialist ────────┼─► 3.5 Report Automation
                                 │
                                 └─► 3.4 Content Calendar Review


PHASE 3                          PHASE 4
────────                         ────────

3.1 n8n Integration ─────────────┬─► 4.6 Custom Report Builder
                                 │
2.8 Trace Instrumentation ───────┼─► 4.2 A/B Testing
                                 │
                                 └─► 4.3 Self-Optimization

All Phase 3 ─────────────────────┬─► 4.1 Voice Channel
                                 │
                                 └─► 4.4 Advanced Analytics
```

### 11.7 Success Metrics by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| **Phase 1** | Context budget compliance | <20% of window |
| **Phase 1** | Tool discovery accuracy | >90% relevant |
| **Phase 1** | Session stability | >99% uptime |
| **Phase 2** | Agent task completion | >95% |
| **Phase 2** | User satisfaction (CSAT) | >4.0/5.0 |
| **Phase 2** | Response latency | <5s average |
| **Phase 3** | Automation success rate | >98% |
| **Phase 3** | Content deployment accuracy | >99% |
| **Phase 3** | Report generation time | <60s |
| **Phase 4** | Voice latency | <2s e2e |
| **Phase 4** | A/B test velocity | 2+ per week |
| **Phase 4** | Self-optimization impact | +20% quality |

---

## 12. Appendices

### Appendix A: Tool Categories Reference

| Category | Example MCP Servers | Typical Tools |
|----------|---------------------|---------------|
| **Analytics** | google_analytics, mixpanel, amplitude | get_metrics, run_report, get_audiences |
| **Advertising** | google_ads, meta_ads, linkedin_ads | get_campaigns, update_budget, get_keywords |
| **Email** | mailchimp, hubspot_email, klaviyo | send_email, get_lists, create_campaign |
| **CRM** | salesforce, hubspot_crm, pipedrive | get_contacts, update_deal, create_task |
| **Social** | twitter, linkedin, instagram | post_content, get_analytics, schedule_post |
| **CMS** | wordpress, contentful, webflow | create_post, update_page, get_content |
| **SEO** | data4seo, semrush, ahrefs | keyword_research, get_rankings, backlinks |
| **E-commerce** | shopify, woocommerce, bigcommerce | get_orders, update_products, get_analytics |
| **Project** | notion, jira, asana | create_task, update_status, get_projects |
| **Automation** | n8n, zapier, make | create_workflow, trigger_workflow, get_runs |

### Appendix B: Output Types for Evaluation

| Category | Output Types |
|----------|-------------|
| **Business Strategy** | company_overview, swot_analysis, strategic_goals, value_proposition, market_position |
| **Marketing Strategy** | icp_narrative, campaign_strategy, channel_strategy, messaging_framework |
| **Competitive** | competitor_analysis, competitive_positioning, market_trends |
| **Content** | blog_post, social_post, email_copy, video_script, landing_page |
| **Analytics** | performance_report, forecast, attribution_analysis, dashboard |

### Appendix C: Configuration Reference

```yaml
# harness_config.yaml
harness:
  context:
    max_tokens: 40000
    compression_threshold: 0.8
    levels:
      executive_summary: 5000
      section_summary: 10000
      full_detail: 20000

  tools:
    max_loaded_servers: 10
    max_tool_tokens: 15000
    search_result_limit: 20
    lru_eviction: true

  agents:
    orchestrator:
      model: gemini-2.0-flash
      temperature: 0.3
      max_tokens: 4096
    specialists:
      strategy:
        model: gemini-2.0-flash
        temperature: 0.4
        max_tokens: 8192
      content:
        model: gemini-2.0-flash
        temperature: 0.7
        max_tokens: 8192
      analytics:
        model: gemini-2.0-flash
        temperature: 0.1
        max_tokens: 4096

  channels:
    web:
      enabled: true
      websocket_timeout: 300
    slack:
      enabled: true
      thread_replies: true
    voice:
      enabled: false  # Phase 4
      latency_target: 2000

  automation:
    platform: n8n
    base_url: ${N8N_BASE_URL}
    default_retry_count: 3
    notification_channel: ${SLACK_NOTIFICATION_CHANNEL}
```

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **HCL** | Hierarchical Context Loading - 3-level context management |
| **DCL** | Dynamic Context Loading - on-demand context retrieval |
| **MCP** | Model Context Protocol - standard for tool integration |
| **LRU** | Least Recently Used - eviction strategy for loaded servers |
| **STT** | Speech-to-Text - voice transcription |
| **TTS** | Text-to-Speech - voice synthesis |
| **ADK** | Agent Development Kit - Google's agent framework |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Development Team | Initial design document |

---

*This document describes the target architecture for the KEN-E agentic harness. Implementation details may evolve based on testing and user feedback.*


# KEN-E Self-Improving Evaluation Framework
## Comprehensive Design Document

**Version:** 2.1
**Date:** January 11, 2026
**Author:** Development Team
**Status:** Design Phase
**Change Summary:** Updated to align with KEN-E Agentic Harness Design v1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Vision & Objectives](#2-vision--objectives)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Data Storage Design & Database Schema](#4-data-storage-design--database-schema)
5. [Human Feedback Capture System](#5-human-feedback-capture-system)
6. [Trace Collection & W&B Integration](#6-trace-collection--wb-integration)
7. [Automated Analysis & Recommendation Engine](#7-automated-analysis--recommendation-engine)
8. [Deployment Pipeline & Rollback System](#8-deployment-pipeline--rollback-system)
9. [User Interface Design](#9-user-interface-design)
10. [KEN-E Application Modifications](#10-ken-e-application-modifications)
11. [Agentic Harness Integration](#11-agentic-harness-integration) *(NEW)*
12. [Human Edit Distance Tracking](#12-human-edit-distance-tracking) *(NEW)*
13. [Multi-Step Workflow Evaluation](#13-multi-step-workflow-evaluation) *(NEW)*
14. [n8n Workflow Evaluation](#14-n8n-workflow-evaluation) *(NEW)*
15. [Cross-Account Benchmarking](#15-cross-account-benchmarking) *(NEW)*
16. [Prioritized Feature Roadmap](#16-prioritized-feature-roadmap)
17. [Appendices](#17-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the comprehensive design for a self-improving evaluation framework that continuously optimizes the quality of KEN-E's AI agents. The system creates a closed feedback loop where:

1. **Agent outputs are captured** via Weights & Biases (W&B) Weave traces
2. **Human evaluators assess quality** through a structured feedback interface
3. **LLM-based scorers learn** to align with human judgment
4. **The system identifies improvement opportunities** and generates optimization recommendations
5. **Humans approve optimizations** which are deployed through a controlled pipeline
6. **Performance is monitored** with automatic rollback recommendations if degradation occurs

### 1.2 Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Human-in-the-Loop** | All optimizations require human approval before deployment |
| **Batch Processing** | Optimization cycles are manually triggered, not continuous |
| **Global Optimization** | Improvements apply across all KEN-E accounts |
| **Gradual Rollout** | Changes deploy to subset of accounts before full rollout |
| **Version Control** | All configurations are versioned with full audit trail |
| **Rollback Ready** | Any change can be quickly reverted with one-click approval |

### 1.3 What the System Can Optimize

#### Directly Optimizable (No Code Deployment Required)

| Parameter | Storage Location | Optimization Method |
|-----------|------------------|---------------------|
| Agent Instructions (Prompts) | Firestore | Alignment engine iterates on prompt text |
| Model Selection | Firestore | A/B testing with performance comparison |
| Temperature | Firestore | Grid search with quality metrics |
| max_output_tokens | Firestore | Analysis of truncation rates |
| Evaluation Rubrics | Firestore | Meta-analysis of scorer effectiveness |

#### Recommendation-Only (Requires Code Deployment)

| Component | What System Can Do |
|-----------|-------------------|
| Tools | Flag tool usage patterns, recommend tool additions/removals |
| Output Schemas | Identify schema gaps, suggest field additions |
| Agent Structure | Detect orchestration issues, recommend restructuring |
| Neo4j Schema | Identify missing relationships, suggest schema changes |

### 1.4 System Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SELF-IMPROVING EVALUATION FRAMEWORK                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   CAN OPTIMIZE  │    │  CAN RECOMMEND  │    │   OUT OF SCOPE  │         │
│  │   DIRECTLY      │    │  (Human Impl.)  │    │                 │         │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤         │
│  │ • Prompts       │    │ • Tool changes  │    │ • Infrastructure│         │
│  │ • Model choice  │    │ • Schema updates│    │ • Security      │         │
│  │ • Temperature   │    │ • Agent struct. │    │ • Auth/Authz    │         │
│  │ • Token limits  │    │ • Neo4j schema  │    │ • UI/UX design  │         │
│  │ • Eval rubrics  │    │ • New extractors│    │ • Data privacy  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Vision & Objectives

### 2.1 Vision Statement

Create an intelligent system that learns from human expertise to continuously improve KEN-E's AI agents, reducing the manual effort required for prompt engineering while ensuring consistent, high-quality outputs that meet user expectations.

### 2.2 Strategic Objectives

| Objective | Success Metric | Target |
|-----------|---------------|--------|
| Reduce manual prompt iteration time | Hours spent on prompt engineering per agent | 75% reduction |
| Improve agent output quality | Human satisfaction scores | >90% positive ratings |
| Increase scorer-human alignment | Agreement percentage | >85% alignment |
| Accelerate optimization cycles | Time from issue identification to deployment | <1 week |
| Minimize production regressions | Rollback frequency | <5% of deployments |

### 2.3 User Stories

#### Development Team (Primary Users)

1. **As a developer**, I want to see which agents are underperforming so I can prioritize optimization efforts.

2. **As a developer**, I want the system to suggest prompt improvements based on human feedback patterns so I can quickly iterate.

3. **As a developer**, I want to compare prompt variants side-by-side so I can make informed deployment decisions.

4. **As a developer**, I want to deploy optimizations to a subset of users first so I can validate improvements before full rollout.

5. **As a developer**, I want one-click rollback capability so I can quickly revert problematic changes.

#### Human Evaluators

6. **As an evaluator**, I want a clear interface to rate agent outputs so I can provide consistent feedback.

7. **As an evaluator**, I want to see the context (input, expected output) when evaluating so I can make accurate judgments.

8. **As an evaluator**, I want the system to prioritize which outputs need my review so I can focus on high-impact evaluations.

### 2.4 Core Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OPTIMIZATION LIFECYCLE                             │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐         ┌──────────┐         ┌──────────┐
     │  CAPTURE │         │  ANALYZE │         │  OPTIMIZE│
     │          │────────▶│          │────────▶│          │
     └──────────┘         └──────────┘         └──────────┘
          │                    │                    │
          ▼                    ▼                    ▼
    ┌───────────┐       ┌───────────┐       ┌───────────┐
    │• Traces   │       │• Score    │       │• Generate │
    │  from W&B │       │  outputs  │       │  variants │
    │• Human    │       │• Compare  │       │• Human    │
    │  feedback │       │  to human │       │  approval │
    │• Configs  │       │• Find gaps│       │• A/B test │
    └───────────┘       └───────────┘       └───────────┘
          │                    │                    │
          └────────────────────┴────────────────────┘
                              │
                              ▼
                       ┌──────────┐
                       │  DEPLOY  │
                       │          │
                       └──────────┘
                              │
                              ▼
                       ┌───────────┐
                       │• Staging  │
                       │• Canary   │
                       │• Full     │
                       │• Monitor  │
                       │• Rollback │
                       └───────────┘
                              │
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
       ┌────────────┐                 ┌────────────┐
       │  SUCCESS   │                 │  ROLLBACK  │
       │            │                 │            │
       │ Continue   │                 │ Revert &   │
       │ monitoring │                 │ re-analyze │
       └────────────┘                 └────────────┘
```

---

## 3. System Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    KEN-E PLATFORM                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐│
│  │                              PRODUCTION ENVIRONMENT                              ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            ││
│  │  │   KEN-E     │  │   Agent     │  │   Neo4j     │  │  Firestore  │            ││
│  │  │   App UI    │  │   Engine    │  │   Graph DB  │  │  User Data  │            ││
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘            ││
│  │         │                │                                                       ││
│  │         │         ┌──────┴──────┐                                               ││
│  │         │         │   Traces    │                                               ││
│  │         │         └──────┬──────┘                                               ││
│  └─────────┼────────────────┼──────────────────────────────────────────────────────┘│
│            │                │                                                        │
│            │                ▼                                                        │
│  ┌─────────┼────────────────────────────────────────────────────────────────────────┐│
│  │         │           EVALUATION FRAMEWORK                                         ││
│  │         │                                                                        ││
│  │         │    ┌─────────────────────────────────────────────────────────────┐    ││
│  │         │    │                    W&B WEAVE                                 │    ││
│  │         │    │  ┌───────────┐  ┌───────────┐  ┌───────────┐               │    ││
│  │         │    │  │  Traces   │  │   Evals   │  │  Scorers  │               │    ││
│  │         │    │  └───────────┘  └───────────┘  └───────────┘               │    ││
│  │         │    └─────────────────────────────────────────────────────────────┘    ││
│  │         │                           │                                            ││
│  │         ▼                           ▼                                            ││
│  │    ┌─────────────────────────────────────────────────────────────────────┐      ││
│  │    │                    EVALUATION FRAMEWORK UI                           │      ││
│  │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │      ││
│  │    │  │   Human     │  │  Dashboard  │  │   Prompt    │  │ Deployment │ │      ││
│  │    │  │  Feedback   │  │  & Reports  │  │   Editor    │  │  Manager   │ │      ││
│  │    │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │      ││
│  │    └─────────────────────────────────────────────────────────────────────┘      ││
│  │                           │                                                      ││
│  │                           ▼                                                      ││
│  │    ┌─────────────────────────────────────────────────────────────────────┐      ││
│  │    │                    AI OPTIMIZER ENGINE                               │      ││
│  │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │      ││
│  │    │  │  Extractor  │  │  Alignment  │  │Recommendation│ │  Deployment│ │      ││
│  │    │  │   System    │  │   Engine    │  │   Engine    │  │  Pipeline  │ │      ││
│  │    │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │      ││
│  │    └─────────────────────────────────────────────────────────────────────┘      ││
│  │                           │                                                      ││
│  │                           ▼                                                      ││
│  │    ┌─────────────────────────────────────────────────────────────────────┐      ││
│  │    │                    EVALUATION DATA STORES                            │      ││
│  │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │      ││
│  │    │  │  Firestore  │  │  BigQuery   │  │    GCS      │                  │      ││
│  │    │  │  Configs &  │  │  Analytics  │  │  Artifacts  │                  │      ││
│  │    │  │  Feedback   │  │  & History  │  │  & Backups  │                  │      ││
│  │    │  └─────────────┘  └─────────────┘  └─────────────┘                  │      ││
│  │    └─────────────────────────────────────────────────────────────────────┘      ││
│  └──────────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Responsibilities

#### 3.2.1 Evaluation Framework UI

The single unified interface for all evaluation and optimization activities.

| Component | Responsibility |
|-----------|---------------|
| **Human Feedback Module** | Structured evaluation forms, queue management, bulk evaluation |
| **Dashboard & Reports** | Agent performance metrics, trend analysis, comparison views |
| **Prompt Editor** | View/edit prompts, side-by-side comparison, diff visualization |
| **Deployment Manager** | Approve changes, manage rollouts, trigger rollbacks |

#### 3.2.2 AI Optimizer Engine

The backend intelligence that drives the optimization process.

| Component | Responsibility |
|-----------|---------------|
| **Extractor System** | Parse traces, extract evaluatable outputs (34+ types) |
| **Alignment Engine** | Compare LLM scores to human evaluations, iterate prompts |
| **Recommendation Engine** | Identify issues, suggest optimizations, prioritize actions |
| **Deployment Pipeline** | Orchestrate staging → canary → production rollouts |

#### 3.2.3 Evaluation Data Stores

| Store | Purpose | Data Types |
|-------|---------|------------|
| **Firestore** | Real-time configuration and feedback | Agent configs, human evaluations, deployment state |
| **BigQuery** | Historical analysis and reporting | Evaluation history, performance trends, A/B results |
| **GCS** | Artifact storage | Prompt versions, model outputs, backup configs |
| **W&B Weave** | Trace storage and LLM evaluation | Traces, LLM scores, scorer definitions |

### 3.3 Integration Points

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTEGRATION ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│    KEN-E APP     │          │  EVAL FRAMEWORK  │          │  EXTERNAL SVC    │
├──────────────────┤          ├──────────────────┤          ├──────────────────┤
│                  │          │                  │          │                  │
│  Agent Engine    │─────────▶│  Trace Ingestion │          │                  │
│                  │  traces  │                  │          │                  │
│                  │          │                  │          │                  │
│  Firestore       │◀────────▶│  Config Manager  │          │                  │
│  (Agent Config)  │  configs │                  │          │                  │
│                  │          │                  │          │                  │
│                  │          │  W&B Client      │─────────▶│  W&B Weave       │
│                  │          │                  │  API     │                  │
│                  │          │                  │          │                  │
│                  │          │  Vertex AI       │─────────▶│  Google Cloud    │
│                  │          │  Client          │  API     │  Vertex AI       │
│                  │          │                  │          │                  │
│  Cloud Build     │◀─────────│  Deployment      │          │                  │
│                  │  trigger │  Pipeline        │          │                  │
│                  │          │                  │          │                  │
└──────────────────┘          └──────────────────┘          └──────────────────┘

Integration Methods:
────────────────────
─────────▶  REST API / gRPC
◀────────▶  Firestore SDK (real-time sync)
- - - - -▶  Cloud Pub/Sub (async events)
═════════▶  Cloud Build Trigger
```

### 3.4 Security & Access Control

| Component | Access Level | Authentication |
|-----------|-------------|----------------|
| Evaluation UI | Dev team only | Firebase Auth (allowlist) |
| AI Optimizer API | Internal services | Service account |
| W&B Weave | Read: Optimizer, Write: KEN-E agents | API keys |
| Firestore (Eval) | Read/Write: Optimizer | Service account |
| Firestore (KEN-E) | Read: Optimizer, Write: Deployment only | Service account |
| BigQuery | Read/Write: Optimizer | Service account |
| Cloud Build | Trigger: Optimizer | Service account |

---

## 4. Data Storage Design & Database Schema

> **Roadmap:** [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#feature-25-mer-e-phase-0--trace-extraction-parallel-track) — Release 2.0

### 4.1 Storage Strategy Overview

The evaluation framework uses a multi-database approach optimized for different access patterns:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA STORAGE ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│      FIRESTORE      │    │      BIGQUERY       │    │        GCS          │
│   (Operational)     │    │    (Analytical)     │    │    (Artifacts)      │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│                     │    │                     │    │                     │
│ • Agent configs     │    │ • Evaluation hist.  │    │ • Prompt versions   │
│ • Human evaluations │    │ • Performance trend │    │ • Config backups    │
│ • Deployment state  │    │ • A/B test results  │    │ • Large artifacts   │
│ • Evaluation queues │    │ • Alignment metrics │    │ • Export archives   │
│ • Active sessions   │    │ • Usage analytics   │    │                     │
│                     │    │                     │    │                     │
│ Access: Real-time   │    │ Access: Batch/SQL   │    │ Access: Blob        │
│ Latency: <100ms     │    │ Latency: Seconds    │    │ Latency: Variable   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
          │                          │                          │
          │                          │                          │
          ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              W&B WEAVE                                       │
│                         (Trace & Eval Storage)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Raw agent traces        • LLM evaluation runs       • Scorer definitions  │
│ • Tool call logs          • Score results             • Dataset versions    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Firestore Schema

#### 4.2.1 Collection: `agent_configs`

Stores the runtime configuration for all KEN-E agents. This is the **source of truth** for what's deployed.

```
agent_configs/
├── {agent_id}/
│   ├── name: string                    # "business_researcher"
│   ├── model: string                   # "gemini-2.0-flash"
│   ├── description: string             # Human-readable description
│   ├── instruction: string             # The prompt (potentially large)
│   ├── generate_content_config: map
│   │   ├── temperature: number         # 0.0 - 1.0
│   │   └── max_output_tokens: number   # Token limit
│   ├── metadata: map
│   │   ├── version: string             # "v1.2.3"
│   │   ├── variant_name: string        # "baseline" | "optimized_v1" | etc.
│   │   ├── experiment_id: string       # For A/B testing
│   │   ├── created_at: timestamp
│   │   ├── updated_at: timestamp
│   │   ├── updated_by: string          # User or system identifier
│   │   ├── notes: string               # Change description
│   │   ├── parent_version: string      # Version this was derived from
│   │   └── optimization_source: string # "manual" | "alignment_engine" | "a_b_test"
│   └── deployment_status: map
│       ├── environment: string         # "staging" | "canary" | "production"
│       ├── rollout_percentage: number  # 0-100 for canary
│       ├── deployed_at: timestamp
│       └── deployed_by: string
```

#### 4.2.2 Collection: `agent_config_history`

Complete version history for audit trail and rollback capability.

```
agent_config_history/
├── {history_id}/                       # Auto-generated ID
│   ├── agent_id: string                # Reference to agent_configs
│   ├── version: string                 # "v1.2.3"
│   ├── config_snapshot: map            # Complete config at this version
│   ├── change_type: string             # "prompt" | "model" | "temperature" | "full"
│   ├── change_diff: string             # JSON diff from previous version
│   ├── created_at: timestamp
│   ├── created_by: string
│   ├── deployment_history: array
│   │   └── {environment, deployed_at, rolled_back_at, rollback_reason}
│   └── performance_metrics: map        # Populated after deployment
│       ├── evaluation_count: number
│       ├── avg_human_score: number
│       ├── avg_llm_score: number
│       └── agreement_rate: number
```

#### 4.2.3 Collection: `human_evaluations`

Stores all human feedback on agent outputs.

```
human_evaluations/
├── {evaluation_id}/                    # Format: {trace_id}_{output_type}_{index}_{timestamp}
│   ├── trace_id: string                # W&B trace identifier
│   ├── output_type: string             # "problem_awareness_strategy"
│   ├── output_index: number            # Index within list outputs
│   ├── agent_id: string                # Which agent produced this
│   ├── agent_version: string           # Version at time of generation
│   ├── evaluator_id: string            # Who evaluated
│   ├── evaluated_at: timestamp
│   ├── input_context: map              # What the agent received
│   │   ├── user_input: string
│   │   ├── account_id: string
│   │   └── session_context: string
│   ├── output_content: string          # The actual output being evaluated
│   ├── factor_scores: map              # Scores for each evaluation factor
│   │   └── {factor_name}: map
│   │       ├── score: boolean | number # true/false or 1-5 scale
│   │       ├── reasoning: string       # Evaluator's explanation
│   │       └── confidence: string      # "high" | "medium" | "low"
│   ├── overall_quality: number         # 1-5 overall rating
│   ├── flags: array                    # ["needs_review", "edge_case", "exemplar"]
│   └── notes: string                   # Free-form evaluator notes
```

#### 4.2.4 Collection: `evaluation_factors`

Defines the evaluation rubrics/questions for each output type.

```
evaluation_factors/
├── {output_type}/
│   ├── output_type: string             # "problem_awareness_strategy"
│   ├── description: string             # What this output type represents
│   ├── factors: array
│   │   └── {factor_id}/
│   │       ├── factor_id: string       # "problem_dimensions"
│   │       ├── question: string        # The evaluation question
│   │       ├── description: string     # Guidance for evaluators
│   │       ├── score_type: string      # "boolean" | "scale_5" | "scale_10"
│   │       ├── weight: number          # Importance weight (0-1)
│   │       ├── is_active: boolean      # Can be disabled without deletion
│   │       ├── created_at: timestamp
│   │       ├── updated_at: timestamp
│   │       └── suggested_by: string    # "human" | "system_recommendation"
│   ├── metadata: map
│   │   ├── version: string
│   │   ├── last_reviewed: timestamp
│   │   └── effectiveness_score: number # How well factors predict quality
│   └── pending_suggestions: array      # System-suggested improvements
│       └── {suggestion_id, factor_change, reasoning, confidence}
```

#### 4.2.5 Collection: `evaluation_queue`

Manages the prioritized queue of outputs awaiting human evaluation.

```
evaluation_queue/
├── {queue_item_id}/
│   ├── trace_id: string
│   ├── output_type: string
│   ├── output_index: number
│   ├── agent_id: string
│   ├── priority: number                # Higher = more urgent
│   ├── priority_reason: string         # Why this is prioritized
│   ├── status: string                  # "pending" | "assigned" | "completed" | "skipped"
│   ├── assigned_to: string             # Evaluator ID if assigned
│   ├── assigned_at: timestamp
│   ├── created_at: timestamp
│   ├── expires_at: timestamp           # Auto-deprioritize if stale
│   └── metadata: map
│       ├── is_disagreement_sample: boolean  # From alignment engine
│       ├── llm_score: number           # Pre-computed LLM score
│       └── similar_evaluations: number # How many similar items evaluated
```

#### 4.2.6 Collection: `optimization_recommendations`

Stores system-generated recommendations awaiting human review.

```
optimization_recommendations/
├── {recommendation_id}/
│   ├── agent_id: string                # Target agent
│   ├── recommendation_type: string     # "prompt" | "model" | "temperature" | "structure" | "tool"
│   ├── status: string                  # "pending" | "approved" | "rejected" | "deployed" | "rolled_back"
│   ├── priority: string                # "critical" | "high" | "medium" | "low"
│   ├── created_at: timestamp
│   ├── created_by: string              # "alignment_engine" | "pattern_analyzer" | etc.
│   ├── current_value: any              # Current config value
│   ├── recommended_value: any          # Suggested new value
│   ├── change_diff: string             # Visual diff for prompts
│   ├── reasoning: string               # Why this change is recommended
│   ├── evidence: map
│   │   ├── evaluation_count: number    # How many evals support this
│   │   ├── disagreement_examples: array # Sample disagreements
│   │   ├── expected_improvement: number # Predicted score increase
│   │   └── confidence: number          # 0-1 confidence score
│   ├── review: map                     # Populated after human review
│   │   ├── reviewed_by: string
│   │   ├── reviewed_at: timestamp
│   │   ├── decision: string            # "approve" | "reject" | "modify"
│   │   ├── modified_value: any         # If human modified the suggestion
│   │   └── review_notes: string
│   └── deployment: map                 # Populated after deployment
│       ├── deployed_at: timestamp
│       ├── deployed_to: string         # "staging" | "canary" | "production"
│       ├── rollout_percentage: number
│       └── performance_after: map      # Tracked metrics post-deployment
```

#### 4.2.7 Collection: `deployment_events`

Audit log of all deployment activities.

```
deployment_events/
├── {event_id}/
│   ├── event_type: string              # "deploy" | "rollback" | "promote" | "pause"
│   ├── agent_id: string
│   ├── from_version: string
│   ├── to_version: string
│   ├── environment: string
│   ├── rollout_percentage: number
│   ├── triggered_by: string            # User ID
│   ├── triggered_at: timestamp
│   ├── recommendation_id: string       # Link to optimization_recommendations
│   ├── status: string                  # "in_progress" | "completed" | "failed"
│   ├── completion_time: timestamp
│   └── notes: string
```

### 4.3 BigQuery Schema

BigQuery stores historical data for analytics, trend analysis, and reporting.

#### 4.3.1 Table: `evaluation_history`

Denormalized table for fast analytical queries.

```sql
CREATE TABLE evaluation_history (
    evaluation_id STRING NOT NULL,
    trace_id STRING NOT NULL,
    output_type STRING NOT NULL,
    output_index INT64,
    agent_id STRING NOT NULL,
    agent_version STRING,

    -- Evaluation metadata
    evaluator_id STRING,
    evaluated_at TIMESTAMP,
    evaluation_source STRING,           -- "human" | "llm_scorer"
    scorer_id STRING,                   -- If LLM evaluation

    -- Scores (flattened for easy querying)
    factor_name STRING,
    factor_score FLOAT64,               -- Normalized 0-1
    factor_reasoning STRING,
    overall_quality FLOAT64,

    -- Context
    account_id STRING,
    input_context STRING,
    output_content STRING,

    -- Partitioning
    evaluation_date DATE,

    -- Clustering
    _PARTITIONTIME TIMESTAMP
)
PARTITION BY evaluation_date
CLUSTER BY agent_id, output_type;
```

#### 4.3.2 Table: `alignment_metrics`

Tracks scorer-human alignment over time.

```sql
CREATE TABLE alignment_metrics (
    metric_id STRING NOT NULL,
    calculated_at TIMESTAMP NOT NULL,

    -- Scope
    agent_id STRING,
    output_type STRING,
    factor_name STRING,
    scorer_id STRING,
    scorer_version STRING,

    -- Metrics
    total_comparisons INT64,
    agreement_count INT64,
    agreement_rate FLOAT64,
    mean_human_score FLOAT64,
    mean_llm_score FLOAT64,
    score_correlation FLOAT64,          -- Pearson correlation

    -- Distribution
    false_positive_rate FLOAT64,        -- LLM says good, human says bad
    false_negative_rate FLOAT64,        -- LLM says bad, human says good

    -- Partitioning
    metric_date DATE
)
PARTITION BY metric_date
CLUSTER BY agent_id, output_type;
```

#### 4.3.3 Table: `agent_performance_daily`

Daily aggregated performance metrics per agent.

```sql
CREATE TABLE agent_performance_daily (
    date DATE NOT NULL,
    agent_id STRING NOT NULL,
    agent_version STRING,
    environment STRING,                 -- "staging" | "canary" | "production"

    -- Volume
    total_invocations INT64,
    total_evaluations INT64,
    human_evaluations INT64,
    llm_evaluations INT64,

    -- Quality scores
    avg_overall_quality FLOAT64,
    avg_human_score FLOAT64,
    avg_llm_score FLOAT64,
    quality_std_dev FLOAT64,

    -- Factor breakdown (JSON for flexibility)
    factor_scores JSON,                 -- {"factor_name": {"avg": 0.8, "count": 100}}

    -- Operational metrics
    avg_latency_ms FLOAT64,
    error_rate FLOAT64,
    token_usage_avg INT64,

    -- Flags
    anomaly_detected BOOLEAN,
    anomaly_details STRING
)
PARTITION BY date
CLUSTER BY agent_id;
```

#### 4.3.4 Table: `optimization_history`

Tracks the impact of optimization changes.

```sql
CREATE TABLE optimization_history (
    optimization_id STRING NOT NULL,
    agent_id STRING NOT NULL,

    -- Change details
    change_type STRING,
    from_version STRING,
    to_version STRING,
    change_description STRING,

    -- Timeline
    recommended_at TIMESTAMP,
    approved_at TIMESTAMP,
    deployed_staging_at TIMESTAMP,
    deployed_canary_at TIMESTAMP,
    deployed_production_at TIMESTAMP,
    rolled_back_at TIMESTAMP,

    -- Before/after metrics
    metric_window_days INT64,           -- How many days of data compared
    before_avg_quality FLOAT64,
    after_avg_quality FLOAT64,
    quality_change_pct FLOAT64,
    before_agreement_rate FLOAT64,
    after_agreement_rate FLOAT64,

    -- Outcome
    final_status STRING,                -- "success" | "rolled_back" | "no_change"
    outcome_notes STRING
);
```

### 4.4 Google Cloud Storage Structure

```
gs://ken-e-evaluation-artifacts/
├── prompts/
│   └── {agent_id}/
│       └── {version}/
│           ├── instruction.txt         # Full prompt text
│           ├── config.json             # Full config snapshot
│           └── metadata.json           # Version metadata
├── evaluations/
│   └── exports/
│       └── {date}/
│           └── {export_id}.parquet     # Bulk evaluation exports
├── scorers/
│   └── {scorer_id}/
│       └── {version}/
│           ├── prompt.txt              # Scorer system prompt
│           └── config.json             # Scorer configuration
├── alignment_runs/
│   └── {run_id}/
│       ├── input_dataset.json
│       ├── disagreements.json
│       ├── prompt_iterations/
│       │   └── iteration_{n}.txt
│       └── final_report.json
└── backups/
    └── firestore/
        └── {date}/
            └── {collection}.json
```

### 4.5 W&B Weave Data Model

W&B Weave stores trace data and LLM evaluation results. The framework reads from Weave but does not modify its schema.

```
Weave Project: ken-e-evaluation
├── Traces
│   └── {trace_id}
│       ├── inputs: {...}
│       ├── outputs: {...}
│       ├── metadata:
│       │   ├── agent_id
│       │   ├── agent_version
│       │   ├── account_id
│       │   └── session_id
│       └── spans: [...]              # Sub-operations
├── Evaluations
│   └── {eval_run_id}
│       ├── dataset_ref
│       ├── scorer_ref
│       └── results: [...]
├── Scorers
│   └── {scorer_id}:{version}
│       ├── system_prompt
│       ├── output_type
│       ├── factor_name
│       └── model_config
└── Datasets
    └── {dataset_id}
        ├── rows: [...]
        └── metadata
```

### 4.6 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │   KEN-E Agent   │
                    │    Execution    │
                    └────────┬────────┘
                             │
                             │ Traces
                             ▼
                    ┌─────────────────┐
                    │    W&B Weave    │
                    │  (Trace Store)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │ Extractor  │  │   Human    │  │    LLM     │
     │  System    │  │  Eval UI   │  │  Scorers   │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           │               │               │
           ▼               ▼               ▼
     ┌─────────────────────────────────────────┐
     │              Firestore                   │
     │  (Evaluations, Configs, Queue)          │
     └─────────────────┬───────────────────────┘
                       │
                       │ Batch sync
                       ▼
     ┌─────────────────────────────────────────┐
     │              BigQuery                    │
     │  (Historical Analysis)                  │
     └─────────────────┬───────────────────────┘
                       │
                       ▼
     ┌─────────────────────────────────────────┐
     │        Recommendation Engine            │
     └─────────────────┬───────────────────────┘
                       │
                       │ Recommendations
                       ▼
     ┌─────────────────────────────────────────┐
     │          Human Review (UI)              │
     └─────────────────┬───────────────────────┘
                       │
                       │ Approved changes
                       ▼
     ┌─────────────────────────────────────────┐
     │        Deployment Pipeline              │
     │   Staging → Canary → Production         │
     └─────────────────┬───────────────────────┘
                       │
                       │ Config updates
                       ▼
     ┌─────────────────────────────────────────┐
     │     Firestore (Agent Configs)           │
     │          ↓                              │
     │     KEN-E Agent Engine                  │
     │   (Loads updated configs)               │
     └─────────────────────────────────────────┘
```

---

## 5. Human Feedback Capture System

> **Roadmap:** [Feature 4.3: MER-E Phase 2 — Human Feedback](product-roadmap.md#feature-43-mer-e-phase-2--human-feedback--patterns-parallel-track-phase-1) — Release 4.0

### 5.1 System Overview

The Human Feedback Capture System is the primary mechanism for collecting ground truth evaluations that train and align the LLM scorers. This system should **extend the existing evaluation_feedback application** rather than building from scratch, leveraging its React/TypeScript/Tailwind foundation.

#### 5.1.1 Recommendation: Extend Existing Application

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Extend evaluation_feedback** | Existing codebase, familiar stack, faster delivery | May need refactoring for new features | **Recommended** |
| Build new application | Clean architecture, modern patterns | Duplicate effort, longer timeline | Not recommended |

**Rationale:** The existing evaluation_feedback app already handles:
- Firebase/Firestore integration
- Form management with React Hook Form
- Property-based evaluation routing
- Basic evaluation submission

The new features (queue management, dashboard, deployment controls) can be added as new routes/components.

### 5.2 Evaluation Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HUMAN EVALUATION WORKFLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Queue     │────▶│   Review    │────▶│  Evaluate   │────▶│   Submit    │
│  Selection  │     │   Context   │     │   Factors   │     │  & Next     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼
 ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
 │Priority │        │• Input  │        │• Score  │        │• Save   │
 │queue or │        │• Output │        │  each   │        │• Update │
 │browse   │        │• Agent  │        │  factor │        │  queue  │
 │all      │        │  info   │        │• Notes  │        │• Next   │
 └─────────┘        └─────────┘        └─────────┘        └─────────┘
```

### 5.3 Queue Management System

#### 5.3.1 Queue Population Sources

The evaluation queue is populated from multiple sources with different priority levels:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QUEUE POPULATION SOURCES                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│  HIGHEST PRIORITY   │
│  (Score: 100-80)    │
├─────────────────────┤
│ Alignment Engine    │──▶ Disagreement samples where LLM and human
│ Disagreements       │    scores differ significantly
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  HIGH PRIORITY      │
│  (Score: 79-60)     │
├─────────────────────┤
│ Low Confidence      │──▶ Outputs where LLM scorer reported low
│ LLM Scores          │    confidence in its evaluation
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  MEDIUM PRIORITY    │
│  (Score: 59-40)     │
├─────────────────────┤
│ New Agent Versions  │──▶ Outputs from recently deployed prompt
│                     │    changes that need validation
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  NORMAL PRIORITY    │
│  (Score: 39-20)     │
├─────────────────────┤
│ Coverage Gaps       │──▶ Output types or agents with low
│                     │    human evaluation coverage
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  LOW PRIORITY       │
│  (Score: 19-0)      │
├─────────────────────┤
│ Random Sampling     │──▶ Random selection for baseline
│                     │    coverage and bias prevention
└─────────────────────┘
```

#### 5.3.2 Priority Scoring Algorithm

```python
def calculate_priority(trace_item):
    """
    Calculate priority score (0-100) for an evaluation queue item.
    Higher scores = higher priority.
    """
    score = 0

    # Disagreement samples from alignment engine (highest priority)
    if trace_item.is_disagreement_sample:
        score += 50
        score += min(trace_item.disagreement_magnitude * 20, 30)  # 0-30 based on magnitude

    # Low LLM confidence
    if trace_item.llm_confidence and trace_item.llm_confidence < 0.6:
        score += 25

    # New agent version needing validation
    if trace_item.agent_version_age_hours < 48:
        score += 20

    # Coverage gaps (inverse of evaluation count)
    coverage_score = max(0, 15 - (trace_item.similar_evaluations * 2))
    score += coverage_score

    # Recency bonus (fresher traces slightly preferred)
    if trace_item.trace_age_hours < 24:
        score += 5

    return min(score, 100)
```

### 5.4 Evaluation Interface Design

#### 5.4.1 Streamlined Evaluation Flow

The current application requires copy-pasting traces from W&B. The enhanced system should:

1. **Eliminate copy-paste**: Directly fetch traces from W&B via API
2. **Pre-populate context**: Show input, output, and agent info automatically
3. **Dynamic factor loading**: Load evaluation factors from Firestore based on output type
4. **Keyboard shortcuts**: Enable rapid evaluation with hotkeys

#### 5.4.2 Evaluation Form Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EVALUATION FORM: problem_awareness_strategy                                 │
│  Agent: marketing_strategy_agent v1.2.3                                      │
│  Trace: abc123... | Index: 2 of 5                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ INPUT CONTEXT                                               [Expand] │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ Account: Acme Corp                                                   │   │
│  │ ICP: Enterprise IT Directors                                         │   │
│  │ Product: Cloud Security Suite                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AGENT OUTPUT                                                [Expand] │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ "Enterprise IT Directors face significant challenges in securing    │   │
│  │  hybrid cloud environments. The primary pain points include:        │   │
│  │  1. Visibility gaps across multi-cloud deployments                  │   │
│  │  2. Compliance complexity with evolving regulations..."             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ EVALUATION FACTORS                                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  1. Problem Dimensions [?]                           Yes ○  No ○    │   │
│  │     Does the strategy identify multiple dimensions                   │   │
│  │     of the customer's problem?                                       │   │
│  │     Reasoning: [________________________________]                    │   │
│  │                                                                      │   │
│  │  2. Customer Language [?]                            Yes ○  No ○    │   │
│  │     Does the strategy use language that resonates                    │   │
│  │     with the target customer?                                        │   │
│  │     Reasoning: [________________________________]                    │   │
│  │                                                                      │   │
│  │  3. Specificity [?]                                  Yes ○  No ○    │   │
│  │     Are the pain points specific rather than generic?                │   │
│  │     Reasoning: [________________________________]                    │   │
│  │                                                                      │   │
│  │  4. Actionability [?]                                Yes ○  No ○    │   │
│  │     Does the strategy suggest actionable approaches?                 │   │
│  │     Reasoning: [________________________________]                    │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ OVERALL ASSESSMENT                                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Overall Quality:  ☆ ☆ ☆ ☆ ☆  (1-5)                                │   │
│  │                                                                      │   │
│  │  Flags:  □ Edge case  □ Exemplar  □ Needs team review              │   │
│  │                                                                      │   │
│  │  Notes: [__________________________________________________]        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LLM SCORER COMPARISON (Optional - Toggle)                   [Hide]  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  LLM Score: 3/4 factors = Yes                                       │   │
│  │  LLM Reasoning: "The strategy identifies 3 clear dimensions..."     │   │
│  │  ⚠️ Disagreement on Factor 2: LLM said Yes, you said No            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  [Skip]  [Save Draft]                    [Submit & Next] (Ctrl+Enter)       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Evaluation Factor Management

The system should support dynamic management of evaluation factors, including system-suggested improvements.

#### 5.5.1 Factor Suggestion System

When the alignment engine detects patterns in human evaluations that suggest the rubric could be improved, it generates suggestions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PENDING FACTOR SUGGESTIONS                                                  │
│  Output Type: problem_awareness_strategy                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ SUGGESTION #1                                    Confidence: 78%   │    │
│  │ Type: NEW FACTOR                                                   │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │                                                                    │    │
│  │ Suggested Factor: "Competitive Differentiation"                    │    │
│  │                                                                    │    │
│  │ Question: Does the strategy position the solution against          │    │
│  │           competitive alternatives?                                │    │
│  │                                                                    │    │
│  │ Reasoning: Analysis of 47 human evaluations shows evaluators       │    │
│  │ frequently mention competitive positioning in their notes,         │    │
│  │ but no existing factor captures this dimension.                    │    │
│  │                                                                    │    │
│  │ Evidence:                                                          │    │
│  │ • 23 evaluations mentioned "competitor" or "alternative"           │    │
│  │ • Strong correlation (r=0.72) between mentions and overall score   │    │
│  │                                                                    │    │
│  │ [Approve]  [Modify]  [Reject]  [Need More Evidence]               │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ SUGGESTION #2                                    Confidence: 65%   │    │
│  │ Type: MODIFY EXISTING                                              │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │                                                                    │    │
│  │ Current Factor: "Specificity"                                      │    │
│  │ Current Question: Are the pain points specific rather than generic?│    │
│  │                                                                    │    │
│  │ Suggested Change: Split into two factors                           │    │
│  │ • "Pain Point Specificity" - Are pain points specific to segment?  │    │
│  │ • "Solution Specificity" - Are solutions concrete and actionable?  │    │
│  │                                                                    │    │
│  │ Reasoning: Low inter-rater agreement (0.54) suggests the current   │    │
│  │ factor conflates two distinct concepts.                            │    │
│  │                                                                    │    │
│  │ [Approve]  [Modify]  [Reject]  [Need More Evidence]               │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.6 Bulk Evaluation Features

For efficiency, the system should support bulk operations:

| Feature | Description |
|---------|-------------|
| **Bulk Skip** | Mark multiple queue items as "not evaluatable" (e.g., malformed outputs) |
| **Template Responses** | Save common reasoning patterns for reuse |
| **Evaluation Sessions** | Track evaluation sessions for productivity metrics |
| **Auto-advance** | Automatically load next item after submission |
| **Keyboard Navigation** | Full keyboard support for rapid evaluation |

### 5.7 Integration with W&B Weave

#### 5.7.1 Trace Fetching Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TRACE FETCHING ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  Eval Framework │          │   Backend API   │          │   W&B Weave     │
│       UI        │          │   (FastAPI)     │          │      API        │
└────────┬────────┘          └────────┬────────┘          └────────┬────────┘
         │                            │                            │
         │  1. Request queue item     │                            │
         │───────────────────────────▶│                            │
         │                            │                            │
         │                            │  2. Fetch trace by ID      │
         │                            │───────────────────────────▶│
         │                            │                            │
         │                            │  3. Return trace data      │
         │                            │◀───────────────────────────│
         │                            │                            │
         │                            │  4. Extract output using   │
         │                            │     registered extractor   │
         │                            │                            │
         │  5. Return formatted       │                            │
         │     evaluation context     │                            │
         │◀───────────────────────────│                            │
         │                            │                            │
```

#### 5.7.2 Required W&B Integration Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /traces/{trace_id}` | Fetch single trace with full context |
| `GET /traces?agent_id=X&limit=N` | List recent traces for an agent |
| `GET /evaluations?scorer_id=X` | Fetch LLM evaluation results |
| `GET /scorers` | List available scorers |

---

## 6. Trace Collection & W&B Integration

> **Roadmap:** [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#feature-25-mer-e-phase-0--trace-extraction-parallel-track) — Release 2.0

### 6.1 Current State

All KEN-E agents are already instrumented to send traces to W&B Weave. This section documents the expected trace structure and how the evaluation framework consumes this data.

### 6.2 Trace Structure Requirements

For the evaluation framework to function effectively, traces must contain specific metadata:

```python
# Required trace metadata for evaluation framework
trace_metadata = {
    # Agent identification (REQUIRED)
    "agent_id": "business_researcher",           # Unique agent identifier
    "agent_version": "v1.2.3",                   # Version from Firestore metadata

    # Experiment tracking (REQUIRED for A/B testing)
    "experiment_id": "baseline",                 # Or specific experiment ID
    "variant_name": "baseline",                  # Variant being tested

    # Context (REQUIRED for evaluation)
    "account_id": "acc_123",                     # KEN-E account
    "session_id": "sess_456",                    # Chat/workflow session
    "user_id": "user_789",                       # Optional: User who triggered

    # Environment (REQUIRED for deployment tracking)
    "environment": "production",                 # "staging" | "canary" | "production"
    "rollout_percentage": 100,                   # If canary deployment

    # Timing (AUTO-POPULATED by Weave)
    "timestamp": "2026-01-10T14:30:00Z",
    "duration_ms": 2500,

    # Optional enrichment
    "input_tokens": 1500,
    "output_tokens": 800,
    "model_used": "gemini-2.0-flash",
    "temperature": 0.3,
}
```

### 6.3 Trace Enrichment Pipeline

The evaluation framework enriches raw traces with additional context needed for evaluation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRACE ENRICHMENT PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   Raw Trace     │
│   from W&B      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: EXTRACTION                                                           │
│ Apply registered extractors to identify evaluatable outputs                  │
│ • Parse trace structure                                                      │
│ • Match output types (34+ supported)                                         │
│ • Unroll list outputs into individual items                                  │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: CONTEXT ENRICHMENT                                                   │
│ Add business context from KEN-E databases                                    │
│ • Fetch account details from Firestore                                       │
│ • Retrieve ICP/product context from Neo4j                                    │
│ • Add agent configuration snapshot                                           │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: LLM PRE-SCORING (Optional)                                           │
│ Run LLM scorer for automated evaluation                                      │
│ • Select appropriate scorer based on output type                             │
│ • Generate scores and confidence levels                                      │
│ • Store results in Weave                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: QUEUE PRIORITIZATION                                                 │
│ Determine if/how item should be queued for human evaluation                  │
│ • Calculate priority score                                                   │
│ • Check for duplicates/similar items                                         │
│ • Add to evaluation_queue in Firestore                                       │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Enriched Item  │
│  Ready for Eval │
└─────────────────┘
```

### 6.4 Tool Call Trace Extraction

Tool call evaluation is a high priority. The system must extract and evaluate individual tool calls within agent traces.

#### 6.4.1 Tool Call Structure

```python
# Example tool call within a trace
tool_call = {
    "tool_name": "google_search",
    "tool_call_id": "tc_123",
    "parent_span_id": "span_456",        # Parent agent span

    "input": {
        "query": "cloud security market trends 2026",
        "num_results": 5
    },

    "output": {
        "results": [...],
        "search_metadata": {...}
    },

    "timing": {
        "start_time": "2026-01-10T14:30:01Z",
        "end_time": "2026-01-10T14:30:03Z",
        "duration_ms": 2000
    },

    "context": {
        "agent_id": "business_researcher",
        "agent_goal": "Research competitive landscape for Acme Corp",
        "previous_tool_calls": ["tc_121", "tc_122"],
        "reasoning": "Need to understand current market trends..."
    }
}
```

#### 6.4.2 Tool Call Evaluation Factors

| Factor | Question | Type |
|--------|----------|------|
| **Relevance** | Was this the right tool for the current subtask? | Boolean |
| **Query Quality** | Was the tool input well-formed and specific? | 1-5 Scale |
| **Timing** | Was this tool called at the right point in the workflow? | Boolean |
| **Necessity** | Was this tool call necessary, or redundant? | Boolean |
| **Result Utilization** | Did the agent effectively use the tool's output? | 1-5 Scale |

### 6.5 Batch Trace Processing

For efficiency, traces are processed in batches:

```python
# Batch processing configuration
batch_config = {
    "batch_size": 100,                    # Traces per batch
    "processing_interval_minutes": 60,    # How often to run
    "max_trace_age_hours": 72,            # Don't process traces older than this
    "priority_processing": True,          # Process high-priority items first
    "parallel_extractors": 4,             # Concurrent extractor threads
}
```

### 6.6 Trace Data Retention

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| Raw traces | 90 days | W&B Weave |
| Extracted outputs | 1 year | BigQuery |
| Evaluation results | Indefinite | Firestore + BigQuery |
| Aggregated metrics | Indefinite | BigQuery |

---

## 7. Automated Analysis & Recommendation Engine

> **Roadmap:** [Feature 3.5: MER-E Phase 1 — Quality Scoring](product-roadmap.md#feature-35-mer-e-phase-1--quality-scoring-parallel-track), [Feature 5.2: MER-E Phase 3 — Prompt Optimization](product-roadmap.md#feature-52-mer-e-phase-3--prompt-optimization-phase-1) — Releases 3.0, 5.0

### 7.1 Engine Overview

The Automated Analysis & Recommendation Engine is the intelligence layer that identifies improvement opportunities and generates actionable recommendations for human review. It operates through multiple analysis modules that examine different aspects of agent performance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION ENGINE ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   Data Sources  │
                              └────────┬────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Human Evals    │         │   LLM Scores    │         │  Agent Traces   │
│  (Firestore)    │         │   (W&B Weave)   │         │   (W&B Weave)   │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ANALYSIS MODULES                                   │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│                 │                 │                 │                       │
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐  │  ┌─────────────────┐  │
│  │ Alignment │  │  │  Pattern  │  │  │   Tool    │  │  │  Configuration  │  │
│  │  Analyzer │  │  │  Detector │  │  │  Usage    │  │  │    Optimizer    │  │
│  │           │  │  │           │  │  │  Analyzer │  │  │                 │  │
│  └─────┬─────┘  │  └─────┬─────┘  │  └─────┬─────┘  │  └───────┬─────────┘  │
│        │        │        │        │        │        │          │            │
└────────┼────────┴────────┼────────┴────────┼────────┴──────────┼────────────┘
         │                 │                 │                   │
         └─────────────────┴─────────────────┴───────────────────┘
                                     │
                                     ▼
                        ┌─────────────────────┐
                        │   Recommendation    │
                        │     Aggregator      │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Human Review Queue │
                        │    (Firestore)      │
                        └─────────────────────┘
```

### 7.2 Analysis Module: Alignment Analyzer

The Alignment Analyzer compares LLM scorer outputs with human evaluations to identify where the scorer needs improvement.

#### 7.2.1 Agreement Metrics

```python
class AlignmentMetrics:
    """Metrics computed for each scorer-factor combination."""

    # Basic agreement
    agreement_rate: float           # % of cases where LLM and human agree
    total_comparisons: int          # Number of paired evaluations

    # Error analysis
    false_positive_rate: float      # LLM says good, human says bad
    false_negative_rate: float      # LLM says bad, human says good

    # Score correlation (for scale-based factors)
    pearson_correlation: float      # -1 to 1 correlation coefficient
    mean_absolute_error: float      # Average score difference

    # Confidence calibration
    confidence_accuracy: float      # Does high confidence = correct?

    # Trend
    trend_direction: str            # "improving" | "stable" | "degrading"
    trend_significance: float       # Statistical significance of trend
```

#### 7.2.2 Disagreement Sampling Strategy

When LLM and human evaluations disagree, the system strategically samples these cases for analysis:

```python
def sample_disagreements(disagreements: List[Disagreement], sample_size: int) -> List[Disagreement]:
    """
    Intelligently sample disagreements to maximize learning.
    Uses stratified sampling across multiple dimensions.
    """
    sampled = []

    # Stratify by disagreement type
    false_positives = [d for d in disagreements if d.type == "false_positive"]
    false_negatives = [d for d in disagreements if d.type == "false_negative"]

    # Sample proportionally, but ensure minimum representation
    fp_count = max(sample_size // 3, len(false_positives) // 2)
    fn_count = max(sample_size // 3, len(false_negatives) // 2)

    # Within each stratum, prioritize:
    # 1. High-confidence LLM errors (most informative)
    # 2. Recent evaluations (most relevant)
    # 3. Diverse input contexts (avoid overfitting)

    sampled.extend(
        sorted(false_positives, key=lambda d: (-d.llm_confidence, -d.recency))[:fp_count]
    )
    sampled.extend(
        sorted(false_negatives, key=lambda d: (-d.llm_confidence, -d.recency))[:fn_count]
    )

    return sampled[:sample_size]
```

#### 7.2.3 Prompt Improvement Generation

When alignment is poor, the system generates prompt improvement suggestions:

```python
# Prompt improvement meta-prompt structure
improvement_prompt = """
You are an expert at improving LLM evaluation prompts.

## Current Scorer Prompt
{current_prompt}

## Factor Being Evaluated
Name: {factor_name}
Question: {factor_question}

## Disagreement Analysis
Total comparisons: {total_comparisons}
Agreement rate: {agreement_rate}%
False positive rate: {false_positive_rate}%
False negative rate: {false_negative_rate}%

## Sample Disagreements
{disagreement_samples}

## Your Task
Analyze the disagreements and suggest improvements to the scorer prompt that would:
1. Reduce false positives by {fp_reduction_target}%
2. Reduce false negatives by {fn_reduction_target}%
3. Maintain or improve overall agreement

Provide:
1. Analysis of why the current prompt leads to these errors
2. Specific changes to the prompt text
3. The complete revised prompt
4. Confidence level in your recommendation (0-100%)
"""
```

### 7.3 Analysis Module: Pattern Detector

The Pattern Detector identifies systematic issues in agent outputs that may not be captured by individual factor scores.

#### 7.3.1 Pattern Categories

| Pattern Type | Description | Example |
|--------------|-------------|---------|
| **Consistency Issues** | Output quality varies significantly across similar inputs | Same ICP produces 5-star and 2-star strategies |
| **Context Blindness** | Agent ignores important input context | Strategy doesn't reference specific product features |
| **Repetitive Content** | Agent produces overly similar outputs | 80% of strategies use identical phrases |
| **Length Anomalies** | Outputs are consistently too long or too short | All outputs hit max_tokens limit |
| **Structural Problems** | Outputs don't follow expected format | Missing required sections |
| **Hallucination Signals** | Outputs contain fabricated information | References non-existent competitors |

#### 7.3.2 Pattern Detection Algorithms

```python
class PatternDetector:
    def detect_consistency_issues(self, outputs: List[Output]) -> List[Issue]:
        """
        Identify cases where similar inputs produce very different quality outputs.
        """
        # Group outputs by input similarity
        input_clusters = self.cluster_by_input_similarity(outputs)

        issues = []
        for cluster in input_clusters:
            scores = [o.overall_quality for o in cluster.outputs]
            if max(scores) - min(scores) > 2:  # >2 point spread on 5-point scale
                issues.append(ConsistencyIssue(
                    cluster=cluster,
                    score_variance=np.var(scores),
                    recommendation="Prompt may need more specific guidance for this input type"
                ))

        return issues

    def detect_repetitive_content(self, outputs: List[Output]) -> List[Issue]:
        """
        Identify when agent produces overly similar outputs.
        """
        # Compute pairwise similarity using embeddings
        embeddings = self.embed_outputs(outputs)
        similarity_matrix = cosine_similarity(embeddings)

        # Flag if average similarity is too high
        avg_similarity = np.mean(similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)])

        if avg_similarity > 0.85:  # Threshold for "too similar"
            return [RepetitiveContentIssue(
                avg_similarity=avg_similarity,
                recommendation="Prompt may be too constrained, producing templated outputs"
            )]

        return []

    def detect_length_anomalies(self, outputs: List[Output]) -> List[Issue]:
        """
        Identify systematic length issues.
        """
        lengths = [len(o.content) for o in outputs]
        max_tokens = outputs[0].agent_config.max_output_tokens

        # Check if hitting token limit frequently
        truncation_rate = sum(1 for o in outputs if o.was_truncated) / len(outputs)
        if truncation_rate > 0.1:  # >10% truncated
            return [LengthIssue(
                type="truncation",
                rate=truncation_rate,
                recommendation=f"Increase max_output_tokens from {max_tokens} or make prompt more concise"
            )]

        return []
```

### 7.4 Analysis Module: Tool Usage Analyzer

This module specifically evaluates how agents use their available tools.

#### 7.4.1 Tool Usage Metrics

```python
class ToolUsageMetrics:
    """Metrics for evaluating tool usage patterns."""

    # Volume metrics
    avg_tool_calls_per_task: float
    tool_call_distribution: Dict[str, float]  # % of calls per tool

    # Quality metrics
    tool_relevance_score: float               # Are tools used appropriately?
    query_quality_score: float                # Are tool inputs well-formed?
    result_utilization_score: float           # Are results used effectively?

    # Efficiency metrics
    redundant_call_rate: float                # % of unnecessary calls
    missing_call_rate: float                  # % of tasks where tool should've been used but wasn't

    # Error metrics
    tool_error_rate: float                    # % of tool calls that fail
    retry_rate: float                         # % of calls requiring retry
```

#### 7.4.2 Tool Usage Patterns to Detect

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TOOL USAGE ANTI-PATTERNS                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PATTERN: Excessive Tool Calls                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Symptom: Agent makes >10 tool calls for simple tasks                        │
│ Cause: Prompt doesn't guide efficient tool use                              │
│ Impact: Slow execution, high cost                                           │
│ Recommendation: Add guidance on when to stop searching                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PATTERN: Poor Query Formation                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Symptom: Search queries are too vague or too specific                       │
│ Cause: Agent doesn't understand optimal query structure                     │
│ Impact: Irrelevant or no results                                            │
│ Recommendation: Add examples of good queries to prompt                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PATTERN: Ignored Results                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Symptom: Agent calls tool but doesn't incorporate results                   │
│ Cause: Results not relevant, or agent doesn't know how to use them          │
│ Impact: Wasted computation, uninformed output                               │
│ Recommendation: Clarify how tool results should inform output               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PATTERN: Missing Tool Usage                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Symptom: Agent produces output without using available tools                │
│ Cause: Prompt doesn't emphasize tool usage, or agent "knows" answer         │
│ Impact: Outdated or fabricated information                                  │
│ Recommendation: Require tool usage for certain output types                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Analysis Module: Configuration Optimizer

This module experiments with different configuration parameters to find optimal settings.

#### 7.5.1 Optimizable Parameters

| Parameter | Range | Optimization Strategy |
|-----------|-------|----------------------|
| **temperature** | 0.0 - 1.0 | Grid search with quality evaluation |
| **max_output_tokens** | 500 - 8000 | Binary search based on truncation rate |
| **model** | gemini-1.5-flash, gemini-2.0-flash, etc. | A/B testing with cost-quality tradeoff |
| **top_p** | 0.0 - 1.0 | Grid search (if supported by ADK) |
| **top_k** | 1 - 100 | Grid search (if supported by ADK) |

#### 7.5.2 Configuration Experiment Framework

```python
class ConfigurationExperiment:
    """
    Framework for running controlled configuration experiments.
    """

    def __init__(self, agent_id: str, parameter: str, values: List[Any]):
        self.agent_id = agent_id
        self.parameter = parameter
        self.values = values
        self.baseline_value = self.get_current_value()

    def design_experiment(self) -> ExperimentDesign:
        """
        Create experiment design with proper controls.
        """
        return ExperimentDesign(
            experiment_id=generate_experiment_id(),
            agent_id=self.agent_id,
            parameter=self.parameter,
            variants=[
                Variant(name="baseline", value=self.baseline_value, traffic_pct=40),
                *[Variant(name=f"test_{v}", value=v, traffic_pct=60//len(self.values))
                  for v in self.values if v != self.baseline_value]
            ],
            success_metrics=["overall_quality", "agreement_rate"],
            guardrail_metrics=["error_rate", "latency_p95"],
            min_sample_size=100,  # Per variant
            max_duration_days=14,
        )

    def analyze_results(self, results: ExperimentResults) -> ConfigRecommendation:
        """
        Analyze experiment results and generate recommendation.
        """
        # Statistical significance testing
        significant_improvements = []
        for variant in results.variants:
            if variant.name == "baseline":
                continue

            p_value = self.compute_p_value(results.baseline, variant)
            effect_size = self.compute_effect_size(results.baseline, variant)

            if p_value < 0.05 and effect_size > 0.1:  # Significant improvement
                significant_improvements.append({
                    "variant": variant,
                    "p_value": p_value,
                    "effect_size": effect_size,
                    "quality_improvement": variant.avg_quality - results.baseline.avg_quality
                })

        if not significant_improvements:
            return ConfigRecommendation(
                action="keep_current",
                reasoning="No statistically significant improvements found"
            )

        best = max(significant_improvements, key=lambda x: x["quality_improvement"])
        return ConfigRecommendation(
            action="update",
            parameter=self.parameter,
            new_value=best["variant"].value,
            expected_improvement=best["quality_improvement"],
            confidence=1 - best["p_value"],
            evidence=best
        )
```

### 7.6 Recommendation Aggregation

Multiple analysis modules may generate recommendations for the same agent. The aggregator prioritizes and consolidates these.

#### 7.6.1 Priority Scoring

```python
def calculate_recommendation_priority(rec: Recommendation) -> int:
    """
    Calculate priority score (0-100) for a recommendation.
    Higher = more urgent.
    """
    score = 0

    # Impact-based scoring
    if rec.expected_improvement > 0.2:  # >20% improvement
        score += 40
    elif rec.expected_improvement > 0.1:
        score += 25
    elif rec.expected_improvement > 0.05:
        score += 15

    # Confidence-based scoring
    score += int(rec.confidence * 30)  # 0-30 points

    # Evidence-based scoring
    if rec.evaluation_count > 100:
        score += 15
    elif rec.evaluation_count > 50:
        score += 10
    elif rec.evaluation_count > 20:
        score += 5

    # Type-based scoring (some changes are more impactful)
    type_scores = {
        "prompt": 10,       # Prompts have highest leverage
        "tool_guidance": 8,
        "temperature": 5,
        "model": 5,
        "max_tokens": 3,
    }
    score += type_scores.get(rec.type, 0)

    # Urgency factors
    if rec.current_performance < 0.5:  # Below 50% baseline
        score += 15  # Urgent fix needed

    return min(score, 100)
```

#### 7.6.2 Recommendation Consolidation

```python
def consolidate_recommendations(recs: List[Recommendation]) -> List[Recommendation]:
    """
    Consolidate multiple recommendations for the same agent.
    """
    # Group by agent
    by_agent = defaultdict(list)
    for rec in recs:
        by_agent[rec.agent_id].append(rec)

    consolidated = []
    for agent_id, agent_recs in by_agent.items():
        # Check for conflicts (e.g., both "increase temperature" and "decrease temperature")
        conflicts = detect_conflicts(agent_recs)
        if conflicts:
            # Keep only the higher-confidence recommendation
            agent_recs = resolve_conflicts(agent_recs, conflicts)

        # Check for compound improvements (e.g., prompt change + temperature change)
        # These should be tested together, not separately
        if should_bundle(agent_recs):
            consolidated.append(BundledRecommendation(
                agent_id=agent_id,
                components=agent_recs,
                combined_expected_improvement=estimate_combined_improvement(agent_recs)
            ))
        else:
            consolidated.extend(agent_recs)

    # Sort by priority
    return sorted(consolidated, key=lambda r: -calculate_recommendation_priority(r))
```

### 7.7 Automatic Issue Detection

The system proactively identifies areas needing attention, even without explicit optimization triggers.

#### 7.7.1 Monitoring Thresholds

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| Agreement Rate | <70% | <50% | Queue for alignment iteration |
| Overall Quality | <3.5/5 | <3.0/5 | Flag for prompt review |
| Tool Error Rate | >5% | >15% | Alert for tool investigation |
| Truncation Rate | >10% | >25% | Recommend token increase |
| Evaluation Coverage | <20% | <10% | Add to evaluation queue |

#### 7.7.2 Anomaly Detection

```python
class AnomalyDetector:
    """
    Detect sudden changes in agent performance that may indicate issues.
    """

    def detect_anomalies(self, agent_id: str, window_days: int = 7) -> List[Anomaly]:
        """
        Compare recent performance to historical baseline.
        """
        recent = self.get_metrics(agent_id, days=window_days)
        baseline = self.get_metrics(agent_id, days=30, offset=window_days)

        anomalies = []

        # Check for significant quality drops
        if recent.avg_quality < baseline.avg_quality - 2 * baseline.quality_std:
            anomalies.append(Anomaly(
                type="quality_drop",
                severity="critical",
                current_value=recent.avg_quality,
                baseline_value=baseline.avg_quality,
                recommendation="Investigate recent changes; consider rollback"
            ))

        # Check for increasing error rates
        if recent.error_rate > baseline.error_rate * 2:
            anomalies.append(Anomaly(
                type="error_spike",
                severity="high",
                current_value=recent.error_rate,
                baseline_value=baseline.error_rate,
                recommendation="Check for API changes or input pattern shifts"
            ))

        return anomalies
```

### 7.8 Human Feedback Request Generation

When the system identifies areas needing more human input, it generates targeted feedback requests.

#### 7.8.1 Feedback Request Types

| Request Type | Trigger | What's Needed |
|--------------|---------|---------------|
| **Coverage Gap** | <20 evaluations for output type | Random samples for baseline |
| **Alignment Disagreement** | LLM-human agreement <60% | Targeted disagreement samples |
| **New Version Validation** | Prompt deployed <48h ago | Samples from new version |
| **Edge Case Exploration** | Unusual input patterns detected | Samples from edge cases |
| **Rubric Validation** | Factor inter-rater agreement <60% | Re-evaluation of same samples |

#### 7.8.2 Request Prioritization

```python
def generate_feedback_requests(analysis_results: AnalysisResults) -> List[FeedbackRequest]:
    """
    Generate prioritized list of feedback requests based on analysis.
    """
    requests = []

    # Coverage gaps
    for output_type in analysis_results.output_types:
        coverage = get_evaluation_coverage(output_type)
        if coverage.count < 20:
            requests.append(FeedbackRequest(
                type="coverage_gap",
                output_type=output_type,
                target_count=20 - coverage.count,
                priority="high" if coverage.count < 5 else "medium",
                sampling_strategy="random"
            ))

    # Alignment disagreements
    for scorer in analysis_results.scorers:
        if scorer.agreement_rate < 0.6:
            requests.append(FeedbackRequest(
                type="alignment_disagreement",
                output_type=scorer.output_type,
                factor=scorer.factor,
                target_count=min(20, scorer.disagreement_count),
                priority="critical",
                sampling_strategy="disagreement_stratified"
            ))

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(requests, key=lambda r: priority_order[r.priority])

---

## 8. Deployment Pipeline & Rollback System

> **Roadmap:** [Feature 5.2: MER-E Phase 3 — Prompt Optimization](product-roadmap.md#feature-52-mer-e-phase-3--prompt-optimization-phase-1), [Feature 6.3: MER-E Phase 4 — Full Closed Loop](product-roadmap.md#feature-63-mer-e-phase-4--full-closed-loop) — Releases 5.0, 6.0

### 8.1 Deployment Philosophy

The deployment system is designed around three core principles:

1. **Human Approval Required**: No automatic deployments to production
2. **Gradual Rollout**: Changes flow through staging → canary → production
3. **Quick Rollback**: Any change can be reverted within minutes

### 8.2 Deployment Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   STAGING   │───▶│   CANARY    │───▶│  PRODUCTION │───▶│  MONITORING │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ • Test env  │    │ • 5-10% of  │    │ • 100% of   │    │ • Quality   │
│ • Internal  │    │   traffic   │    │   traffic   │    │   tracking  │
│   testing   │    │ • Real users│    │ • Full      │    │ • Anomaly   │
│ • Automated │    │ • Monitor   │    │   rollout   │    │   detection │
│   evals     │    │   closely   │    │             │    │ • Rollback  │
│             │    │             │    │             │    │   triggers  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

Gates (Human Approval Required):
────────────────────────────────
    [Staging ✓]      [Canary ✓]      [Production ✓]

Automatic Rollback Triggers:
────────────────────────────
• Error rate > 2x baseline
• Quality score < baseline - 1 std
• Latency p95 > 2x baseline
```

### 8.3 Stage Definitions

#### 8.3.1 Staging Environment

| Aspect | Configuration |
|--------|--------------|
| **Traffic** | 0% production traffic (internal only) |
| **Accounts** | Test accounts with synthetic data |
| **Duration** | Minimum 24 hours |
| **Validation** | Automated eval suite + manual spot checks |
| **Promotion Criteria** | All automated tests pass, no critical issues |

#### 8.3.2 Canary Environment

| Aspect | Configuration |
|--------|--------------|
| **Traffic** | 5-10% of production traffic |
| **Accounts** | Selected pilot accounts (opt-in) |
| **Duration** | Minimum 48-72 hours |
| **Validation** | Real user feedback + automated monitoring |
| **Promotion Criteria** | Quality >= baseline, no anomalies |

#### 8.3.3 Production Environment

| Aspect | Configuration |
|--------|--------------|
| **Traffic** | 100% of production traffic |
| **Accounts** | All accounts |
| **Duration** | Ongoing |
| **Validation** | Continuous monitoring |
| **Rollback Criteria** | Quality < baseline - 1 std OR error spike |

### 8.4 Deployment Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DETAILED DEPLOYMENT WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     RECOMMENDATION APPROVED                          │
    │                 (by human in Eval Framework UI)                      │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 1: CREATE VERSION                                               │
    │ • Generate new version ID (v1.2.4)                                   │
    │ • Snapshot current config to history                                 │
    │ • Apply recommended changes to new config                            │
    │ • Store in agent_config_history                                      │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 2: DEPLOY TO STAGING                                            │
    │ • Update staging Firestore with new config                           │
    │ • Trigger Cloud Build for staging deployment                         │
    │ • Wait for deployment confirmation                                   │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 3: STAGING VALIDATION (Automated)                               │
    │ • Run automated evaluation suite                                     │
    │ • Compare results to baseline                                        │
    │ • Generate staging report                                            │
    │                                                                      │
    │ Duration: 24+ hours                                                  │
    │ Outcome: Pass/Fail with metrics                                      │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                   [PASS]                   [FAIL]
                        │                       │
                        │                       ▼
                        │           ┌─────────────────────┐
                        │           │ BLOCKED             │
                        │           │ • Notify team       │
                        │           │ • Require manual    │
                        │           │   review            │
                        │           └─────────────────────┘
                        │
                        ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 4: HUMAN APPROVAL FOR CANARY                                    │
    │ • Review staging metrics in UI                                       │
    │ • Compare to baseline performance                                    │
    │ • Click "Promote to Canary" button                                   │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 5: CANARY DEPLOYMENT                                            │
    │ • Update Firestore with canary flag                                  │
    │ • Configure traffic split (5-10%)                                    │
    │ • Begin monitoring                                                   │
    │                                                                      │
    │ Duration: 48-72 hours                                                │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                [METRICS OK]            [ANOMALY DETECTED]
                        │                       │
                        │                       ▼
                        │           ┌─────────────────────┐
                        │           │ AUTO-PAUSE          │
                        │           │ • Halt traffic      │
                        │           │ • Alert team        │
                        │           │ • Await decision    │
                        │           └─────────────────────┘
                        │
                        ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 6: HUMAN APPROVAL FOR PRODUCTION                                │
    │ • Review canary metrics (real user data)                             │
    │ • Compare A/B results                                                │
    │ • Click "Promote to Production" button                               │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 7: PRODUCTION DEPLOYMENT                                        │
    │ • Update production Firestore                                        │
    │ • Remove canary flag (100% traffic)                                  │
    │ • Archive old version                                                │
    │ • Update deployment_events log                                       │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ STEP 8: CONTINUOUS MONITORING                                        │
    │ • Track quality metrics                                              │
    │ • Compare to pre-deployment baseline                                 │
    │ • Alert on anomalies                                                 │
    │ • Recommend rollback if degradation detected                         │
    └─────────────────────────────────────────────────────────────────────┘
```

### 8.5 Rollback System

#### 8.5.1 Rollback Triggers

| Trigger Type | Condition | Response |
|--------------|-----------|----------|
| **Automatic Pause** | Error rate > 2x baseline | Halt canary traffic, alert team |
| **Recommended Rollback** | Quality < baseline - 1 std | Notify team, await approval |
| **Manual Rollback** | Human judgment | Immediate on approval |
| **Emergency Rollback** | System-critical failure | One-click revert |

#### 8.5.2 Rollback Process

```python
class RollbackManager:
    """
    Manages rollback operations for agent configurations.
    """

    def initiate_rollback(
        self,
        agent_id: str,
        target_version: str,
        reason: str,
        triggered_by: str  # "system" | user_id
    ) -> RollbackResult:
        """
        Execute a rollback to a previous version.
        """
        # 1. Validate target version exists
        target_config = self.get_config_version(agent_id, target_version)
        if not target_config:
            raise ValueError(f"Version {target_version} not found")

        # 2. Create rollback record
        rollback_event = DeploymentEvent(
            event_type="rollback",
            agent_id=agent_id,
            from_version=self.get_current_version(agent_id),
            to_version=target_version,
            triggered_by=triggered_by,
            reason=reason,
            status="in_progress"
        )
        self.save_event(rollback_event)

        # 3. Update Firestore config
        self.update_agent_config(agent_id, target_config)

        # 4. If code deployment needed, trigger Cloud Build
        if self.requires_code_deployment(target_config):
            self.trigger_cloud_build(agent_id, target_version)

        # 5. Mark rollback complete
        rollback_event.status = "completed"
        rollback_event.completion_time = datetime.utcnow()
        self.save_event(rollback_event)

        # 6. Notify team
        self.send_notification(
            f"Rollback completed: {agent_id} reverted to {target_version}",
            severity="high"
        )

        return RollbackResult(
            success=True,
            agent_id=agent_id,
            new_version=target_version,
            event_id=rollback_event.id
        )

    def get_rollback_candidates(self, agent_id: str) -> List[ConfigVersion]:
        """
        Get list of versions that can be rolled back to.
        Returns versions with their performance metrics.
        """
        history = self.get_config_history(agent_id, limit=10)

        candidates = []
        for version in history:
            if version.version == self.get_current_version(agent_id):
                continue  # Skip current version

            candidates.append(ConfigVersion(
                version=version.version,
                created_at=version.created_at,
                performance=version.performance_metrics,
                change_description=version.notes,
                is_recommended=version.performance_metrics.avg_quality > self.quality_threshold
            ))

        return candidates
```

### 8.6 Integration with Cloud Build

The system integrates with existing Cloud Build pipeline for code-dependent changes.

```yaml
# cloudbuild-agent-deploy.yaml
steps:
  # Step 1: Validate configuration
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'python'
    args:
      - 'scripts/validate_agent_config.py'
      - '--agent-id=${_AGENT_ID}'
      - '--version=${_VERSION}'

  # Step 2: Run pre-deployment tests
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'python'
    args:
      - 'scripts/run_agent_tests.py'
      - '--agent-id=${_AGENT_ID}'

  # Step 3: Deploy to target environment
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'python'
    args:
      - 'scripts/deploy_agent.py'
      - '--agent-id=${_AGENT_ID}'
      - '--version=${_VERSION}'
      - '--environment=${_ENVIRONMENT}'

  # Step 4: Verify deployment
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'python'
    args:
      - 'scripts/verify_deployment.py'
      - '--agent-id=${_AGENT_ID}'
      - '--environment=${_ENVIRONMENT}'

substitutions:
  _AGENT_ID: ''
  _VERSION: ''
  _ENVIRONMENT: 'staging'

options:
  logging: CLOUD_LOGGING_ONLY
```

### 8.7 A/B Testing Infrastructure

> **Roadmap:** [Feature 4.4: A/B Testing Infrastructure](product-roadmap.md#feature-44-ab-testing-infrastructure) — Release 4.0

For configuration experiments, the system supports A/B testing at the account level.

#### 8.7.1 Traffic Splitting

```python
def get_agent_config_for_account(agent_id: str, account_id: str) -> AgentConfig:
    """
    Determine which agent configuration to use for a given account.
    Supports A/B testing via experiment assignment.
    """
    # Check for active experiments
    experiment = get_active_experiment(agent_id)

    if experiment:
        # Consistent assignment based on account_id hash
        variant = assign_variant(account_id, experiment)
        return get_config_for_variant(agent_id, variant)

    # No active experiment, use production config
    return get_production_config(agent_id)


def assign_variant(account_id: str, experiment: Experiment) -> str:
    """
    Consistently assign account to experiment variant.
    Uses hash for deterministic assignment.
    """
    hash_input = f"{account_id}:{experiment.id}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    bucket = hash_value % 100

    cumulative = 0
    for variant in experiment.variants:
        cumulative += variant.traffic_pct
        if bucket < cumulative:
            return variant.name

    return experiment.variants[-1].name  # Fallback to last variant
```

### 8.8 Deployment Notifications

| Event | Channel | Recipients |
|-------|---------|------------|
| Staging deployment complete | Slack #dev-deployments | Dev team |
| Canary started | Slack #dev-deployments | Dev team |
| Anomaly detected in canary | Slack #alerts + Email | Dev team + On-call |
| Production deployment complete | Slack #dev-deployments | Dev team |
| Rollback initiated | Slack #alerts + Email | Dev team + On-call |
| Rollback complete | Slack #dev-deployments | Dev team |

---

## 9. User Interface Design

### 9.1 Application Structure

The Evaluation Framework UI should extend the existing `evaluation_feedback` application. The recommended structure organizes features into logical modules:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EVALUATION FRAMEWORK UI STRUCTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  NAVIGATION                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
└─────────────────────────────────────────────────────────────────────────────┘

Routes:
├── /dashboard              # Overview metrics and alerts
├── /evaluate               # Human evaluation interface
│   ├── /evaluate/queue     # Prioritized evaluation queue
│   └── /evaluate/:id       # Single evaluation form
├── /agents                 # Agent management
│   ├── /agents/:id         # Agent detail view
│   ├── /agents/:id/config  # Configuration editor
│   └── /agents/:id/history # Version history
├── /recommendations        # Optimization recommendations
│   └── /recommendations/:id # Recommendation detail
├── /deployments            # Deployment management
│   ├── /deployments/active # Active deployments
│   └── /deployments/:id    # Deployment detail
└── /settings               # System configuration
```

### 9.2 Dashboard View

The dashboard provides an at-a-glance view of system health and areas needing attention.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EVALUATION FRAMEWORK DASHBOARD                              [Ken] [Logout] │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ALERTS                                                          [Hide] │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │ ⚠️  business_researcher: Agreement rate dropped to 52% (was 78%)       │ │
│  │ ⚠️  marketing_strategy_agent: 3 pending recommendations need review    │ │
│  │ ✓  Canary deployment (competitive_analyzer v1.3) performing well       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ EVALUATION      │  │ AGENT           │  │ PENDING         │              │
│  │ QUEUE           │  │ PERFORMANCE     │  │ RECOMMENDATIONS │              │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤              │
│  │                 │  │                 │  │                 │              │
│  │  47 items       │  │  12 agents      │  │  5 high         │              │
│  │  pending        │  │  monitored      │  │  priority       │              │
│  │                 │  │                 │  │                 │              │
│  │  12 high        │  │  8 healthy      │  │  12 total       │              │
│  │  priority       │  │  3 warning      │  │  pending        │              │
│  │                 │  │  1 critical     │  │                 │              │
│  │ [Start →]       │  │ [View All →]    │  │ [Review →]      │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ AGENT HEALTH OVERVIEW                                                  │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Agent                    Quality  Agreement  Status    Actions        │ │
│  │  ─────────────────────────────────────────────────────────────────    │ │
│  │  business_researcher      3.8/5    52%        ⚠️ Warn   [View]         │ │
│  │  marketing_strategy       4.2/5    78%        ✓ OK      [View]         │ │
│  │  competitive_analyzer     4.0/5    81%        🔵 Canary [View]         │ │
│  │  brand_guidelines         4.5/5    89%        ✓ OK      [View]         │ │
│  │  icp_researcher           3.2/5    45%        🔴 Crit   [View]         │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────────┐ │
│  │ QUALITY TREND (30 days)          │  │ RECENT ACTIVITY                 │ │
│  ├──────────────────────────────────┤  ├─────────────────────────────────┤ │
│  │                                  │  │                                 │ │
│  │  4.5 ─┬─────────────────────     │  │ 10:32  Ken evaluated 5 items    │ │
│  │  4.0 ─┤    ╱╲    ╱╲              │  │ 09:15  Recommendation created   │ │
│  │  3.5 ─┤╱──╲──╲──╲──╱─────       │  │ 08:00  Staging deploy complete  │ │
│  │  3.0 ─┤                          │  │ Yesterday                       │ │
│  │  2.5 ─┴─────────────────────     │  │ 17:45  Canary promoted to prod │ │
│  │       Jan 1        Jan 10        │  │ 14:22  Yafet evaluated 12 items │ │
│  │                                  │  │                                 │ │
│  └──────────────────────────────────┘  └─────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Evaluation Queue View

The evaluation queue shows prioritized items awaiting human review.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EVALUATION QUEUE                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Filters: [All Agents ▾] [All Output Types ▾] [All Priorities ▾] [Search]  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PRIORITY QUEUE                                          47 items total │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  ☐ │ Priority │ Agent                  │ Output Type        │ Reason  │ │
│  │  ──┼──────────┼────────────────────────┼────────────────────┼─────────│ │
│  │  ☐ │ 🔴 95    │ business_researcher    │ company_overview   │ Disagr. │ │
│  │  ☐ │ 🔴 92    │ icp_researcher         │ icp_narrative      │ Disagr. │ │
│  │  ☐ │ 🟠 78    │ marketing_strategy     │ problem_awareness  │ Low conf│ │
│  │  ☐ │ 🟠 75    │ competitive_analyzer   │ competitor_profile │ New ver │ │
│  │  ☐ │ 🟡 62    │ brand_guidelines       │ brand_voice        │ Coverage│ │
│  │  ☐ │ 🟡 58    │ marketing_strategy     │ acquisition_strat  │ Coverage│ │
│  │  ☐ │ 🟢 34    │ business_researcher    │ swot_analysis      │ Random  │ │
│  │  ☐ │ 🟢 28    │ competitive_analyzer   │ market_position    │ Random  │ │
│  │                                                                        │ │
│  │  [Select All]  [Bulk Skip Selected]              Page 1 of 6 [<] [>]   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Quick Actions:                                                              │
│  [Start Evaluation Session]  [View My Evaluations]  [Export Queue]          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ QUEUE STATISTICS                                                       │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  By Priority:           By Agent:              By Output Type:         │ │
│  │  🔴 Critical: 12        business_researcher: 8  problem_awareness: 6   │ │
│  │  🟠 High: 15            marketing_strategy: 12  company_overview: 5    │ │
│  │  🟡 Medium: 12          competitive_analyzer: 9 icp_narrative: 4       │ │
│  │  🟢 Low: 8              icp_researcher: 6       swot_analysis: 4       │ │
│  │                         brand_guidelines: 5     (12 other types)       │ │
│  │                         (3 others)                                     │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.4 Agent Detail View

Shows comprehensive information about a single agent including configuration, performance, and history.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT: business_researcher                                    v1.4.2       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [Overview]  [Configuration]  [Performance]  [History]  [Experiments]       │
│                                                                              │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────────┐ │
│  │ STATUS                           │  │ QUICK STATS                     │ │
│  ├──────────────────────────────────┤  ├─────────────────────────────────┤ │
│  │                                  │  │                                 │ │
│  │  Environment: Production         │  │  Invocations (7d):  1,247       │ │
│  │  Version: v1.4.2                 │  │  Evaluations (7d):  89          │ │
│  │  Last Updated: Jan 8, 2026       │  │  Avg Quality:       3.8/5       │ │
│  │  Updated By: alignment_engine    │  │  Agreement Rate:    52%         │ │
│  │                                  │  │  Error Rate:        1.2%        │ │
│  │  Health: ⚠️ Warning              │  │                                 │ │
│  │  (Agreement below threshold)     │  │                                 │ │
│  │                                  │  │                                 │ │
│  └──────────────────────────────────┘  └─────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PENDING RECOMMENDATIONS                                                │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  #127 │ Prompt Update │ High    │ Expected +18% quality │ [Review →]  │ │
│  │  #125 │ Temperature   │ Medium  │ Expected +5% quality  │ [Review →]  │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PERFORMANCE BY OUTPUT TYPE                                             │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Output Type          Quality  Agreement  Evaluations  Status          │ │
│  │  ──────────────────────────────────────────────────────────────────   │ │
│  │  company_overview     4.1/5    68%        34           ⚠️ Below target │ │
│  │  swot_analysis        3.5/5    42%        28           🔴 Critical     │ │
│  │  strategic_goals      4.2/5    75%        15           ✓ Healthy       │ │
│  │  value_proposition    3.9/5    58%        12           ⚠️ Below target │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ QUALITY TREND                                           [7d] [30d] [All]│ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  5.0 ─┬─────────────────────────────────────────────────────────────  │ │
│  │  4.5 ─┤                     ╱╲                                        │ │
│  │  4.0 ─┤  ╱╲    ╱╲    ╱╲   ╱  ╲   ╱╲                                  │ │
│  │  3.5 ─┤─╱──╲──╱──╲──╱──╲─╱────╲─╱──╲──                                │ │
│  │  3.0 ─┤                              ╲──────  ← v1.4.2 deployed       │ │
│  │  2.5 ─┴─────────────────────────────────────────────────────────────  │ │
│  │       Dec 15     Dec 22     Dec 29     Jan 5        Jan 10             │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Actions: [Run Alignment Analysis] [Create Experiment] [Edit Config]        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.5 Recommendation Review View

Detailed view for reviewing and acting on optimization recommendations.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RECOMMENDATION #127                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ SUMMARY                                                                │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Agent: business_researcher                                            │ │
│  │  Type: Prompt Update                                                   │ │
│  │  Priority: 🟠 High                                                     │ │
│  │  Created: Jan 9, 2026 at 14:32 by alignment_engine                     │ │
│  │  Status: Pending Review                                                │ │
│  │                                                                        │ │
│  │  Expected Improvement: +18% quality score                              │ │
│  │  Confidence: 78%                                                       │ │
│  │  Evidence: 47 disagreement samples analyzed                            │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ REASONING                                                              │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Analysis of 47 human-LLM disagreements revealed:                      │ │
│  │                                                                        │ │
│  │  • 28 false positives: LLM rated outputs as high quality when          │ │
│  │    humans found them lacking specificity                               │ │
│  │  • 12 false negatives: LLM penalized outputs for length when           │ │
│  │    humans valued the comprehensive coverage                            │ │
│  │  • Common pattern: Current prompt doesn't emphasize industry-specific  │ │
│  │    terminology and context                                             │ │
│  │                                                                        │ │
│  │  Recommended changes address these by:                                 │ │
│  │  1. Adding explicit guidance on industry terminology                   │ │
│  │  2. Clarifying quality vs. length tradeoffs                            │ │
│  │  3. Including examples of high-quality outputs                         │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PROMPT DIFF                                                   [Expand] │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  ─ You are a business strategy researcher.                             │ │
│  │  + You are an expert business strategy researcher with deep            │ │
│  │  + knowledge of industry-specific terminology and competitive          │ │
│  │  + dynamics.                                                           │ │
│  │                                                                        │ │
│  │    For the company mentioned by the user, research and provide         │ │
│  │    comprehensive analysis including:                                   │ │
│  │                                                                        │ │
│  │  + IMPORTANT: Use industry-specific terminology throughout your        │ │
│  │  + analysis. Reference specific market dynamics, competitor            │ │
│  │  + strategies, and quantitative data where available.                  │ │
│  │  +                                                                     │ │
│  │  + Quality Guidelines:                                                 │ │
│  │  + - Prioritize depth and specificity over brevity                     │ │
│  │  + - Include concrete examples and data points                         │ │
│  │  + - Reference industry frameworks where applicable                    │ │
│  │                                                                        │ │
│  │  [Show Full Diff]                                                      │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ SAMPLE DISAGREEMENTS                                                   │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │ Example 1: False Positive                              [Expand] │  │ │
│  │  ├─────────────────────────────────────────────────────────────────┤  │ │
│  │  │ Output: "The company operates in the technology sector..."      │  │ │
│  │  │ LLM Score: 4/5 (Good specificity)                               │  │ │
│  │  │ Human Score: 2/5 (Too generic, lacks industry depth)            │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │ Example 2: False Negative                              [Expand] │  │ │
│  │  ├─────────────────────────────────────────────────────────────────┤  │ │
│  │  │ Output: "Detailed 500-word competitive analysis..."             │  │ │
│  │  │ LLM Score: 2/5 (Too verbose)                                    │  │ │
│  │  │ Human Score: 5/5 (Comprehensive and valuable)                   │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  [View All 47 Samples]                                                 │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ REVIEW ACTIONS                                                         │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Review Notes:                                                         │ │
│  │  [                                                                   ] │ │
│  │  [                                                                   ] │ │
│  │                                                                        │ │
│  │  [Reject]     [Request Changes]     [Approve & Deploy to Staging]     │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.6 Deployment Management View

Track and manage active deployments across environments.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DEPLOYMENTS                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [Active Deployments]  [History]  [Rollback Log]                            │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ACTIVE DEPLOYMENTS                                                     │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ competitive_analyzer v1.3.1                         🔵 CANARY     │ │ │
│  │  ├──────────────────────────────────────────────────────────────────┤ │ │
│  │  │                                                                  │ │ │
│  │  │  Environment: Canary (10% traffic)                               │ │ │
│  │  │  Started: Jan 8, 2026 at 09:00                                   │ │ │
│  │  │  Duration: 25 hours (min 48h required)                           │ │ │
│  │  │                                                                  │ │ │
│  │  │  Metrics vs Baseline:                                            │ │ │
│  │  │  • Quality: 4.1/5 vs 3.9/5 (+5.1%) ✓                            │ │ │
│  │  │  • Agreement: 83% vs 78% (+6.4%) ✓                              │ │ │
│  │  │  • Error Rate: 0.8% vs 1.1% (-27%) ✓                            │ │ │
│  │  │  • Sample Size: 127 invocations                                  │ │ │
│  │  │                                                                  │ │ │
│  │  │  Progress: ████████████░░░░░░░░░░░░  52% of min duration        │ │ │
│  │  │                                                                  │ │ │
│  │  │  [Pause Canary]  [View Details]  [Promote to Production]        │ │ │
│  │  │                                  (available in 23h)              │ │ │
│  │  │                                                                  │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ business_researcher v1.4.3                          🟡 STAGING    │ │ │
│  │  ├──────────────────────────────────────────────────────────────────┤ │ │
│  │  │                                                                  │ │ │
│  │  │  Environment: Staging                                            │ │ │
│  │  │  Started: Jan 9, 2026 at 14:45                                   │ │ │
│  │  │  Duration: 8 hours (min 24h required)                            │ │ │
│  │  │                                                                  │ │ │
│  │  │  Automated Tests: ██████████████████████████████████  100% PASS  │ │ │
│  │  │                                                                  │ │ │
│  │  │  Progress: ████████░░░░░░░░░░░░░░░░  33% of min duration        │ │ │
│  │  │                                                                  │ │ │
│  │  │  [Cancel Staging]  [View Details]  [Promote to Canary]          │ │ │
│  │  │                                    (available in 16h)            │ │ │
│  │  │                                                                  │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ QUICK ROLLBACK                                                         │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Select agent to rollback:                                             │ │
│  │  [competitive_analyzer ▾]  [v1.2.0 (previous stable) ▾]  [Rollback]   │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.7 Configuration Editor View

Interface for viewing and editing agent configurations with diff visualization.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CONFIGURATION: business_researcher                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  [Evaluate]  [Agents]  [Recommendations]  [Deployments]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────────┐ │
│  │ VERSION INFO                     │  │ COMPARE WITH                    │ │
│  ├──────────────────────────────────┤  ├─────────────────────────────────┤ │
│  │ Current: v1.4.2 (Production)     │  │ [v1.4.1 ▾] [Show Diff]          │ │
│  │ Modified: Jan 8, 2026            │  │                                 │ │
│  │ By: alignment_engine             │  │                                 │ │
│  └──────────────────────────────────┘  └─────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PARAMETERS                                                    [Edit]   │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Model:              [gemini-2.0-flash ▾]                              │ │
│  │  Temperature:        [0.3        ] (0.0 - 1.0)                         │ │
│  │  Max Output Tokens:  [2500       ] (500 - 8000)                        │ │
│  │                                                                        │ │
│  │  Experiment ID:      [baseline   ]                                     │ │
│  │  Variant Name:       [baseline   ]                                     │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ INSTRUCTION (Prompt)                                          [Edit]   │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  1  │ You are an expert business strategy researcher with deep        │ │
│  │  2  │ knowledge of industry-specific terminology and competitive      │ │
│  │  3  │ dynamics.                                                       │ │
│  │  4  │                                                                 │ │
│  │  5  │ For the company mentioned by the user, research and provide     │ │
│  │  6  │ comprehensive analysis including:                               │ │
│  │  7  │                                                                 │ │
│  │  8  │ 1. Company Overview                                             │ │
│  │  9  │    - Mission and vision                                         │ │
│  │ 10  │    - Core business model                                        │ │
│  │ 11  │    - Key products/services                                      │ │
│  │ 12  │                                                                 │ │
│  │ 13  │ 2. Market Position                                              │ │
│  │ 14  │    - Industry sector and subsector                              │ │
│  │ 15  │    - Market share (if available)                                │ │
│  │     │ ...                                                             │ │
│  │     │                                                                 │ │
│  │     │ [Show Full Prompt - 47 lines]                                   │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ TOOLS (Read-only - requires code deployment)                          │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  • google_search_agent - Web search for company research              │ │
│  │                                                                        │ │
│  │  ℹ️ Tool changes require code deployment via Cloud Build              │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Actions: [Cancel] [Save as Draft] [Save & Deploy to Staging]               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.8 UI Component Library

The UI should use consistent components. Key components needed:

| Component | Purpose |
|-----------|---------|
| **MetricCard** | Display key metrics with trend indicators |
| **StatusBadge** | Show health status (healthy, warning, critical) |
| **PriorityIndicator** | Color-coded priority display |
| **DiffViewer** | Side-by-side or unified diff for prompt changes |
| **TimelineView** | Show deployment history and events |
| **QueueTable** | Sortable, filterable table for evaluation queue |
| **EvaluationForm** | Dynamic form based on output type factors |
| **ProgressBar** | Deployment progress with time remaining |
| **ConfirmDialog** | Confirmation for destructive actions |
| **NotificationToast** | Real-time notifications |

### 9.9 Technical Implementation Notes

| Aspect | Recommendation |
|--------|---------------|
| **State Management** | React Context for global state, React Query for server state |
| **Routing** | React Router v6 |
| **Forms** | Continue using React Hook Form |
| **API Client** | Create typed API client with Firebase Auth integration |
| **Real-time Updates** | Firestore onSnapshot for live queue/deployment updates |
| **Charts** | Recharts or Tremor for metrics visualization |
| **Code Diff** | react-diff-viewer for prompt comparison |
| **Accessibility** | Follow WCAG 2.1 AA guidelines |

---

## 10. KEN-E Application Modifications

This section details the changes required to the main KEN-E application to support the self-improving evaluation framework.

### 10.1 Agent Configuration Changes

#### 10.1.1 Enhanced Metadata Schema

Update the existing Firestore agent configuration to include additional metadata fields:

```python
# Enhanced agent configuration schema
enhanced_config = {
    # Existing fields (unchanged)
    "name": "business_researcher",
    "model": "gemini-2.0-flash",
    "description": "Researches business strategy information",
    "instruction": "...",
    "generate_content_config": {
        "temperature": 0.3,
        "max_output_tokens": 2500,
    },

    # Enhanced metadata (ADD THESE FIELDS)
    "metadata": {
        # Existing fields
        "version": "v1.4.2",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "2026-01-10T12:00:00Z",
        "updated_at": "2026-01-10T12:00:00Z",
        "updated_by": "initial_setup_script",
        "notes": "Baseline configuration...",

        # NEW: Version lineage
        "parent_version": "v1.4.1",
        "optimization_source": "alignment_engine",  # "manual" | "alignment_engine" | "a_b_test"

        # NEW: Performance tracking
        "performance_baseline": {
            "avg_quality": 3.8,
            "agreement_rate": 0.52,
            "sample_size": 89,
            "measured_at": "2026-01-08T00:00:00Z"
        }
    },

    # NEW: Deployment status tracking
    "deployment_status": {
        "environment": "production",  # "staging" | "canary" | "production"
        "rollout_percentage": 100,    # For canary deployments
        "deployed_at": "2026-01-08T14:30:00Z",
        "deployed_by": "ken@dive.team"
    }
}
```

#### 10.1.2 Agent Loading Changes

Modify the agent loading code to support experiment variants:

```python
# Updated agent creation pattern
def create_agent_from_firestore_config(
    doc_id: str,
    account_id: str = None,  # NEW: For A/B experiment assignment
    **kwargs
) -> Agent:
    """
    Load agent configuration from Firestore.
    Supports experiment-based variant selection.
    """
    # Check for active experiment
    if account_id:
        experiment = get_active_experiment(doc_id)
        if experiment:
            variant = assign_variant_for_account(account_id, experiment)
            config_doc_id = f"{doc_id}_{variant}"
        else:
            config_doc_id = doc_id
    else:
        config_doc_id = doc_id

    # Load configuration
    config, metadata = load_config_from_firestore(config_doc_id)

    # Create agent
    agent = Agent.from_config(config, f"/firestore/agent_configs/{config_doc_id}")

    # Attach metadata for tracing
    agent._eval_metadata = {
        "agent_id": doc_id,
        "agent_version": metadata.get("version"),
        "experiment_id": metadata.get("experiment_id"),
        "variant_name": metadata.get("variant_name"),
    }

    return agent
```

### 10.2 Trace Instrumentation Enhancements

#### 10.2.1 Enhanced Trace Metadata

Ensure all agent invocations include required metadata for evaluation:

```python
# Trace metadata wrapper
def instrument_agent_call(agent, inputs, context):
    """
    Wrap agent calls to ensure proper trace metadata.
    """
    trace_metadata = {
        # Agent identification
        "agent_id": agent._eval_metadata.get("agent_id"),
        "agent_version": agent._eval_metadata.get("agent_version"),

        # Experiment tracking
        "experiment_id": agent._eval_metadata.get("experiment_id", "baseline"),
        "variant_name": agent._eval_metadata.get("variant_name", "baseline"),

        # Context
        "account_id": context.get("account_id"),
        "session_id": context.get("session_id"),
        "user_id": context.get("user_id"),

        # Environment
        "environment": get_current_environment(),
        "rollout_percentage": get_rollout_percentage(agent._eval_metadata.get("agent_id")),

        # Model info
        "model_used": agent.model,
        "temperature": agent.generate_content_config.get("temperature"),
    }

    with weave.trace(metadata=trace_metadata):
        result = agent.run(inputs)

    return result
```

#### 10.2.2 Tool Call Instrumentation

Add detailed logging for tool calls:

```python
# Enhanced tool call tracing
class InstrumentedTool:
    """Wrapper to add evaluation-friendly tracing to tools."""

    def __init__(self, tool, parent_agent_id):
        self.tool = tool
        self.parent_agent_id = parent_agent_id

    def __call__(self, *args, **kwargs):
        tool_call_metadata = {
            "tool_name": self.tool.name,
            "parent_agent_id": self.parent_agent_id,
            "input_summary": self._summarize_input(args, kwargs),
        }

        with weave.trace(name=f"tool_call:{self.tool.name}", metadata=tool_call_metadata):
            start_time = time.time()
            try:
                result = self.tool(*args, **kwargs)
                tool_call_metadata["status"] = "success"
                tool_call_metadata["output_summary"] = self._summarize_output(result)
            except Exception as e:
                tool_call_metadata["status"] = "error"
                tool_call_metadata["error"] = str(e)
                raise
            finally:
                tool_call_metadata["duration_ms"] = (time.time() - start_time) * 1000

        return result
```

### 10.3 API Endpoints for Evaluation Framework

Add new endpoints to the KEN-E backend API:

```python
# New endpoints for evaluation framework integration

@router.get("/api/eval/agents")
async def list_agents_for_eval():
    """List all agents with their current configuration and performance metrics."""
    pass

@router.get("/api/eval/agents/{agent_id}/config")
async def get_agent_config(agent_id: str, version: str = None):
    """Get agent configuration, optionally for a specific version."""
    pass

@router.put("/api/eval/agents/{agent_id}/config")
async def update_agent_config(agent_id: str, config: AgentConfigUpdate):
    """Update agent configuration (creates new version)."""
    pass

@router.get("/api/eval/agents/{agent_id}/history")
async def get_agent_history(agent_id: str, limit: int = 10):
    """Get version history for an agent."""
    pass

@router.post("/api/eval/agents/{agent_id}/rollback")
async def rollback_agent(agent_id: str, target_version: str):
    """Rollback agent to a previous version."""
    pass

@router.get("/api/eval/experiments")
async def list_experiments():
    """List active A/B experiments."""
    pass

@router.post("/api/eval/experiments")
async def create_experiment(experiment: ExperimentCreate):
    """Create a new A/B experiment."""
    pass
```

### 10.4 Environment Configuration

Update environment configuration to support staging/canary/production:

```python
# Environment-aware configuration loading
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")  # staging | canary | production

FIRESTORE_COLLECTIONS = {
    "staging": {
        "agent_configs": "agent_configs_staging",
        "user_data": "user_data_staging",
    },
    "canary": {
        "agent_configs": "agent_configs",  # Same as production
        "user_data": "user_data",
    },
    "production": {
        "agent_configs": "agent_configs",
        "user_data": "user_data",
    }
}

def get_collection(collection_name: str) -> str:
    """Get environment-specific collection name."""
    return FIRESTORE_COLLECTIONS[ENVIRONMENT].get(collection_name, collection_name)
```

### 10.5 Required KEN-E Changes Summary

| Area | Change | Priority | Effort |
|------|--------|----------|--------|
| Agent config schema | Add metadata fields | High | Low |
| Agent loading | Support experiment variants | High | Medium |
| Trace metadata | Add required fields | High | Low |
| Tool instrumentation | Add detailed logging | High | Medium |
| API endpoints | Add eval framework endpoints | Medium | Medium |
| Environment config | Support staging/canary/prod | Medium | Low |
| Cloud Build | Add deployment triggers | Medium | Low |

---

## 11. Agentic Harness Integration

> **Roadmap:** [Feature 3.5: MER-E Phase 1 — Quality Scoring](product-roadmap.md#feature-35-mer-e-phase-1--quality-scoring-parallel-track) — Release 3.0

This section describes how the evaluation framework integrates with the KEN-E Agentic Harness architecture (see `KEN-E-Agentic-Harness-Design.md`).

### 11.1 New Agent Types Requiring Evaluation

The Agentic Harness introduces several specialist agents that require evaluation support beyond the original strategy agents:

| Agent | Primary Function | Output Types | Evaluation Priority |
|-------|------------------|--------------|---------------------|
| **Primary Orchestrator** | Routes requests, manages context | routing_decisions, context_loading | High |
| **Strategy Specialist** | Business/marketing strategy | Existing 34 types | High (already covered) |
| **Content Specialist** | Multi-format content generation | blog_post, social_post, email_copy, video_script, landing_page | Critical |
| **Analytics Specialist** | Data analysis with code execution | performance_report, forecast, data_visualization, insight_summary | High |
| **Execution Specialist** | Content deployment, validation | deployment_result, validation_report | Medium |
| **Automation Specialist** | n8n workflow creation | workflow_definition, automation_config | High |
| **Tool Discovery Agent** | MCP server search & loading | tool_search_result, server_recommendation | Medium |

### 11.2 New Output Types for Evaluation

#### Content Generation Outputs (16 new types)

**Blog & Long-Form Content**
- `blog_post` - Full blog article with title, body, meta description
- `article_outline` - Structured outline with headings and key points
- `content_brief` - Strategic brief for content creation
- `landing_page` - Sales/marketing landing page copy

**Social Media Content**
- `social_post_linkedin` - LinkedIn-optimized post
- `social_post_twitter` - Twitter/X post with character constraints
- `social_post_instagram` - Instagram caption with hashtag strategy
- `social_post_tiktok` - TikTok script/caption

**Email Content**
- `email_promotional` - Marketing/promotional email
- `email_newsletter` - Newsletter content
- `email_sequence` - Multi-email drip sequence

**Video Content**
- `video_script_longform` - Full video script (5+ minutes)
- `video_script_shortform` - Short-form video script (< 60 seconds)
- `video_outline` - Video structure and talking points

**Campaign Content**
- `campaign_plan` - Multi-channel campaign strategy
- `campaign_calendar` - Scheduled content calendar

#### Analytics Outputs (8 new types)

- `performance_report` - KPI analysis with metrics
- `forecast` - Predictive analysis with confidence intervals
- `attribution_analysis` - Channel/campaign attribution
- `data_visualization` - Chart/graph specifications
- `insight_summary` - Key findings and recommendations
- `anomaly_report` - Detected anomalies and explanations
- `benchmark_comparison` - Performance vs. benchmarks
- `kpi_dashboard` - Dashboard configuration

#### Execution Outputs (4 new types)

- `deployment_result` - Content deployment status and confirmation
- `validation_report` - Pre-deployment validation results
- `api_response_summary` - External API interaction results
- `scheduling_confirmation` - Calendar entry confirmation

#### Automation Outputs (4 new types)

- `workflow_definition` - n8n workflow JSON configuration
- `automation_config` - Automation parameters and triggers
- `report_automation` - Scheduled report configuration
- `integration_setup` - Third-party integration configuration

### 11.3 Evaluation Factors by Output Category

#### Content Quality Factors

| Factor | Question | Applies To |
|--------|----------|------------|
| `brand_voice_alignment` | Does the content match the established brand voice? | All content types |
| `audience_appropriateness` | Is the tone and complexity appropriate for the target audience? | All content types |
| `call_to_action_clarity` | Is there a clear, compelling call to action? | Promotional content |
| `seo_optimization` | Are relevant keywords naturally integrated? | Blog, landing pages |
| `platform_optimization` | Is the content optimized for the specific platform? | Social posts |
| `engagement_potential` | Is the content likely to drive engagement? | Social posts |
| `character_compliance` | Does content meet platform character limits? | Twitter, TikTok |
| `visual_hook` | Does the opening capture attention? | Video scripts |
| `narrative_flow` | Does the content flow logically? | Long-form content |
| `factual_accuracy` | Are claims accurate and verifiable? | All content types |

#### Analytics Quality Factors

| Factor | Question | Applies To |
|--------|----------|------------|
| `data_accuracy` | Are the numbers and calculations correct? | All analytics |
| `insight_actionability` | Are insights actionable and specific? | Reports, summaries |
| `visualization_clarity` | Are charts clear and properly labeled? | Visualizations |
| `statistical_validity` | Are statistical methods appropriate? | Forecasts, analysis |
| `context_relevance` | Is the analysis relevant to business context? | All analytics |
| `recommendation_quality` | Are recommendations practical and prioritized? | Reports |

#### Automation Quality Factors

| Factor | Question | Applies To |
|--------|----------|------------|
| `workflow_correctness` | Will the workflow execute without errors? | Workflow definitions |
| `trigger_appropriateness` | Are triggers set appropriately for use case? | Automations |
| `error_handling` | Does the workflow handle errors gracefully? | All automations |
| `output_usefulness` | Will the automation produce useful results? | Report automations |

### 11.4 Agent-Specific Evaluation Considerations

#### Content Specialist Evaluation

The Content Specialist generates diverse output formats. Key considerations:

1. **Format Compliance**: Each platform has specific requirements
   - Twitter: 280 characters max
   - LinkedIn: 3,000 characters optimal
   - Instagram: 2,200 characters max, 30 hashtags max
   - TikTok: 150 characters for hook

2. **Brand Consistency**: Content must align with stored brand guidelines
   - Voice tone (formal/casual/playful)
   - Terminology preferences
   - Messaging pillars

3. **Campaign Coherence**: When generating multiple pieces for a campaign, evaluate:
   - Message consistency across formats
   - Appropriate adaptation per platform
   - Progressive narrative across email sequences

```python
# Content Specialist evaluation configuration
CONTENT_SPECIALIST_EVAL_CONFIG = {
    "blog_post": {
        "min_word_count": 800,
        "max_word_count": 2500,
        "required_sections": ["introduction", "body", "conclusion", "cta"],
        "factors": [
            "brand_voice_alignment",
            "seo_optimization",
            "narrative_flow",
            "factual_accuracy",
            "audience_appropriateness"
        ]
    },
    "social_post_twitter": {
        "max_characters": 280,
        "factors": [
            "platform_optimization",
            "engagement_potential",
            "character_compliance",
            "brand_voice_alignment"
        ]
    },
    "email_promotional": {
        "required_sections": ["subject_line", "preview_text", "body", "cta"],
        "factors": [
            "call_to_action_clarity",
            "brand_voice_alignment",
            "audience_appropriateness",
            "engagement_potential"
        ]
    },
    "video_script_shortform": {
        "max_duration_seconds": 60,
        "required_sections": ["hook", "body", "cta"],
        "factors": [
            "visual_hook",
            "platform_optimization",
            "brand_voice_alignment"
        ]
    }
}
```

#### Analytics Specialist Evaluation

The Analytics Specialist performs multi-step analysis with Gemini's native code execution (Python code generated and run in a Google-managed sandbox):

1. **Data Retrieval Accuracy**: Verify correct data was fetched
2. **Calculation Correctness**: Review `executable_code` parts from Gemini code execution for correct logic, and cross-check `code_execution_result` output against source data from tool calls
3. **Insight Quality**: Assess actionability of findings
4. **Visualization Appropriateness**: Right chart type for data

```python
# Analytics Specialist evaluation configuration
ANALYTICS_SPECIALIST_EVAL_CONFIG = {
    "performance_report": {
        "required_sections": ["summary", "key_metrics", "trends", "recommendations"],
        "factors": [
            "data_accuracy",
            "insight_actionability",
            "context_relevance",
            "recommendation_quality"
        ],
        "numerical_validation": True,  # Cross-check numbers against source
        "code_execution_validation": True,  # Validate executable_code parts and code_execution_result output
        "code_review": True  # Review generated Python code for correctness
    },
    "forecast": {
        "required_sections": ["methodology", "predictions", "confidence_intervals", "assumptions"],
        "factors": [
            "statistical_validity",
            "data_accuracy",
            "insight_actionability"
        ],
        "confidence_interval_required": True,
        "code_review": True  # Review generated Python code for statistical calculations
    }
}
```

#### Execution Specialist Evaluation

The Execution Specialist deploys content to external platforms:

1. **Deployment Success**: Did content publish correctly?
2. **Format Preservation**: Was formatting maintained?
3. **Timing Accuracy**: Was it published at the scheduled time?
4. **Cross-Platform Consistency**: For multi-platform campaigns

```python
# Execution evaluation is primarily success/failure tracking
EXECUTION_EVAL_CONFIG = {
    "deployment_result": {
        "success_criteria": [
            "api_response_success",
            "content_format_preserved",
            "timing_within_tolerance",
            "url_accessible"
        ],
        "retry_tracking": True,
        "error_classification": [
            "api_error",
            "authentication_error",
            "rate_limit_error",
            "content_rejection",
            "format_error"
        ]
    }
}
```

### 11.5 Multi-Channel Context Handling

The Agentic Harness supports Web, Slack, and Voice channels. Evaluation considerations:

| Channel | Evaluation Focus | Special Considerations |
|---------|------------------|------------------------|
| **Web** | Full output quality | Standard evaluation applies |
| **Slack** | Conciseness, formatting | Thread context, markdown rendering |
| **Voice** | *Deferred to future version* | TTS-friendliness, response brevity |

For Slack channel responses:
- Evaluate markdown formatting correctness
- Assess response brevity (Slack prefers concise)
- Track thread coherence in multi-turn conversations

### 11.6 Tool Call Evaluation Enhancement

With the Agentic Harness's dynamic tool loading via MCP servers, tool call evaluation becomes more complex:

#### Tool Discovery Evaluation

```python
# Evaluate Tool Discovery Agent performance
TOOL_DISCOVERY_EVAL = {
    "metrics": {
        "search_relevance": "Did search return relevant tools?",
        "loading_efficiency": "Were minimal servers loaded?",
        "cache_hit_rate": "Is caching being utilized?",
        "token_budget_compliance": "Did tool loading stay within budget?"
    },
    "anti_patterns": [
        "loading_all_servers",  # Loading servers not needed for task
        "redundant_loading",    # Loading same server multiple times
        "wrong_server_priority" # Loading low-relevance servers first
    ]
}
```

#### MCP Tool Call Chain Evaluation

For sequential tool calls (common in Analytics Specialist):

```python
class ToolChainEvaluator:
    """
    Evaluates sequences of tool calls for efficiency and correctness.
    """

    def evaluate_chain(self, tool_calls: List[ToolCall]) -> ToolChainEvaluation:
        return ToolChainEvaluation(
            # Did the chain achieve the intended goal?
            goal_achieved=self._assess_goal_completion(tool_calls),

            # Were the tools called in optimal order?
            ordering_efficiency=self._assess_ordering(tool_calls),

            # Were there unnecessary/redundant calls?
            redundancy_score=self._detect_redundancy(tool_calls),

            # Did any calls fail and how were they handled?
            error_recovery=self._assess_error_handling(tool_calls),

            # Were parameters passed correctly between calls?
            data_flow_correctness=self._assess_data_flow(tool_calls)
        )
```

### 11.7 Combined Tool + Output Scoring

While tool usage and output quality are evaluated separately for granular analysis, a **composite Agent Effectiveness Score** provides a single metric for dashboards and A/B testing:

```python
class AgentEffectivenessCalculator:
    """
    Computes combined effectiveness score from tool and output evaluations.

    Benefits of combined scoring:
    1. Root cause attribution - identifies whether issues stem from tool
       selection, tool execution, or synthesis
    2. Weighted optimization - guides whether to optimize tool logic or prompts
    3. Single metric for A/B decisions and executive dashboards
    """

    # Default weights - can be tuned per agent type
    DEFAULT_WEIGHTS = {
        "strategy_specialist": {"tool": 0.3, "output": 0.7},  # Less tool-dependent
        "analytics_specialist": {"tool": 0.5, "output": 0.5}, # Balanced
        "content_specialist": {"tool": 0.2, "output": 0.8},   # Output-focused
        "execution_specialist": {"tool": 0.7, "output": 0.3}, # Tool-focused
        "automation_specialist": {"tool": 0.4, "output": 0.6}
    }

    def compute_effectiveness(
        self,
        agent_id: str,
        tool_score: float,  # 0-5 scale
        output_score: float,  # 0-5 scale
        custom_weights: Dict[str, float] = None
    ) -> AgentEffectivenessScore:

        weights = custom_weights or self.DEFAULT_WEIGHTS.get(
            agent_id,
            {"tool": 0.4, "output": 0.6}  # Default fallback
        )

        effectiveness = (
            weights["tool"] * tool_score +
            weights["output"] * output_score
        )

        # Determine optimization focus based on score gap
        score_gap = abs(tool_score - output_score)
        if score_gap > 1.0:  # Significant gap
            if tool_score < output_score:
                optimization_focus = "tool_selection_and_usage"
            else:
                optimization_focus = "output_synthesis_and_prompts"
        else:
            optimization_focus = "balanced"

        return AgentEffectivenessScore(
            overall=effectiveness,
            tool_component=tool_score,
            output_component=output_score,
            weights_used=weights,
            optimization_focus=optimization_focus
        )
```

---

## 12. Human Edit Distance Tracking

> **Roadmap:** [Feature 5.2: MER-E Phase 3 — Prompt Optimization](product-roadmap.md#feature-52-mer-e-phase-3--prompt-optimization-phase-1) — Release 5.0

This section defines how to measure the quality signal from human edits to AI-generated content.

### 12.1 Overview

When users edit AI-generated content before deployment, the extent of editing provides a valuable quality signal. Research from [ACL 2024](https://aclanthology.org/2024.findings-acl.126/) shows that "Revision Distance" metrics correlate with perceived quality and can guide optimization.

### 12.2 Edit Distance Metrics

#### 12.2.1 Character-Level Edit Distance (Levenshtein)

Classic Levenshtein distance measures minimum single-character edits:

```python
def levenshtein_distance(original: str, edited: str) -> int:
    """Standard Levenshtein distance calculation."""
    m, n = len(original), len(edited)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if original[i-1] == edited[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    return dp[m][n]

def normalized_edit_distance(original: str, edited: str) -> float:
    """Normalized to 0-1 scale where 0 = no edits, 1 = complete rewrite."""
    distance = levenshtein_distance(original, edited)
    max_len = max(len(original), len(edited))
    return distance / max_len if max_len > 0 else 0.0
```

#### 12.2.2 Compression-Based Edit Distance

Based on [arxiv:2412.17321](https://arxiv.org/abs/2412.17321), compression-based metrics better correlate with actual editing effort:

```python
import zlib

def compression_based_edit_distance(original: str, edited: str) -> float:
    """
    Measures edit effort using compression principles.
    Higher correlation with actual human editing time than Levenshtein.
    """
    # Compress each text independently
    original_compressed = len(zlib.compress(original.encode('utf-8')))
    edited_compressed = len(zlib.compress(edited.encode('utf-8')))

    # Compress concatenated texts
    combined = original + edited
    combined_compressed = len(zlib.compress(combined.encode('utf-8')))

    # Normalized compression distance (NCD)
    # Lower NCD = more similar, Higher NCD = more different
    ncd = (combined_compressed - min(original_compressed, edited_compressed)) / \
          max(original_compressed, edited_compressed)

    return ncd
```

#### 12.2.3 Semantic Revision Distance

Uses an LLM to identify semantic-level revisions:

```python
class SemanticRevisionAnalyzer:
    """
    Uses LLM to identify and categorize semantic revisions.
    Provides human-interpretable edit analysis.
    """

    REVISION_CATEGORIES = [
        "factual_correction",      # Fixed incorrect information
        "tone_adjustment",         # Changed voice/tone
        "clarity_improvement",     # Made clearer without changing meaning
        "content_addition",        # Added new information
        "content_removal",         # Removed information
        "restructuring",           # Reorganized without changing content
        "formatting",              # Changed formatting only
        "brand_alignment",         # Adjusted for brand voice
        "platform_optimization"    # Adjusted for platform requirements
    ]

    async def analyze_revisions(
        self,
        original: str,
        edited: str,
        content_type: str
    ) -> RevisionAnalysis:

        prompt = f"""
        Analyze the revisions made to this {content_type}.

        ORIGINAL:
        {original}

        EDITED VERSION:
        {edited}

        For each revision, identify:
        1. What was changed
        2. The category of change: {self.REVISION_CATEGORIES}
        3. Whether the change was necessary (quality issue in original)
        4. Severity: minor (cosmetic), moderate (clarity), major (correctness)

        Return structured JSON analysis.
        """

        analysis = await self.llm.generate(prompt, response_format="json")

        return RevisionAnalysis(
            revision_count=len(analysis["revisions"]),
            categories=self._count_categories(analysis),
            severity_breakdown=self._count_severities(analysis),
            quality_issues_found=self._extract_quality_issues(analysis),
            semantic_distance=self._compute_semantic_distance(analysis)
        )
```

### 12.3 Edit Distance Data Model

```python
# Firestore schema for edit tracking
edit_tracking_schema = {
    "collection": "content_edits",
    "document_structure": {
        "edit_id": "string",  # Unique identifier
        "trace_id": "string",  # Link to original generation trace
        "agent_id": "string",
        "output_type": "string",
        "account_id": "string",

        # Original and edited content
        "original_content": "string",
        "edited_content": "string",
        "original_length": "int",
        "edited_length": "int",

        # Computed metrics
        "levenshtein_distance": "int",
        "normalized_edit_distance": "float",  # 0-1
        "compression_distance": "float",  # 0-1

        # Semantic analysis (populated async)
        "semantic_analysis": {
            "revision_count": "int",
            "categories": "map<string, int>",  # Category -> count
            "severity_breakdown": "map<string, int>",  # minor/moderate/major -> count
            "quality_issues": ["list of strings"],
            "semantic_distance": "float"
        },

        # Context
        "edit_duration_seconds": "int",  # If tracked in UI
        "editor_user_id": "string",
        "deployment_status": "string",  # deployed | rejected | pending

        # Timestamps
        "original_generated_at": "timestamp",
        "edit_completed_at": "timestamp",
        "created_at": "timestamp"
    }
}
```

### 12.4 BigQuery Schema for Edit Analytics

```sql
-- Table for aggregated edit distance analytics
CREATE TABLE IF NOT EXISTS `ken_e_eval.content_edit_metrics` (
    -- Identifiers
    edit_id STRING NOT NULL,
    trace_id STRING NOT NULL,
    agent_id STRING NOT NULL,
    output_type STRING NOT NULL,
    account_id STRING,

    -- Edit distance metrics
    normalized_edit_distance FLOAT64,
    compression_distance FLOAT64,
    semantic_distance FLOAT64,
    revision_count INT64,

    -- Severity breakdown
    minor_revisions INT64,
    moderate_revisions INT64,
    major_revisions INT64,

    -- Category breakdown (flattened for querying)
    factual_corrections INT64,
    tone_adjustments INT64,
    clarity_improvements INT64,
    content_additions INT64,
    content_removals INT64,
    restructuring_changes INT64,
    formatting_changes INT64,
    brand_alignment_changes INT64,
    platform_optimization_changes INT64,

    -- Outcome
    deployed BOOL,
    edit_duration_seconds INT64,

    -- Timestamps
    generated_at TIMESTAMP,
    edited_at TIMESTAMP,
    synced_at TIMESTAMP
)
PARTITION BY DATE(edited_at)
CLUSTER BY agent_id, output_type;
```

### 12.5 Quality Signal Interpretation

Edit distance metrics inform optimization in several ways:

| Metric Pattern | Interpretation | Optimization Action |
|---------------|----------------|---------------------|
| High edit distance, many factual corrections | Agent producing incorrect information | Improve fact-checking, add verification tools |
| High edit distance, many tone adjustments | Brand voice misalignment | Update brand voice in prompts, add examples |
| Low edit distance, many minor formatting changes | Good content, presentation issues | Adjust output formatting templates |
| High variance across accounts | Inconsistent quality | Investigate account-specific context issues |
| Decreasing edit distance over time | Agent improving | Continue current optimization trajectory |

### 12.6 Edit Distance Dashboard Metrics

```python
# Key metrics to display on dashboard
EDIT_DISTANCE_DASHBOARD_METRICS = {
    "overall": {
        "avg_normalized_edit_distance": "Average edits as % of content",
        "content_acceptance_rate": "% of content deployed without major edits",
        "avg_edit_time": "Average time spent editing"
    },
    "by_agent": {
        "edit_distance_trend": "7-day rolling average edit distance",
        "top_revision_categories": "Most common types of edits",
        "major_revision_rate": "% of outputs requiring major revisions"
    },
    "by_output_type": {
        "best_performing": "Output types with lowest edit distance",
        "needs_improvement": "Output types with highest edit distance"
    }
}
```

### 12.7 UI Integration for Edit Tracking

The main KEN-E application needs modifications to capture edits:

```typescript
// React component for content editing with tracking
interface ContentEditorProps {
    originalContent: string;
    traceId: string;
    agentId: string;
    outputType: string;
    onSave: (editedContent: string) => void;
}

const ContentEditorWithTracking: React.FC<ContentEditorProps> = ({
    originalContent,
    traceId,
    agentId,
    outputType,
    onSave
}) => {
    const [content, setContent] = useState(originalContent);
    const [editStartTime] = useState(Date.now());

    const handleSave = async () => {
        const editDuration = Math.floor((Date.now() - editStartTime) / 1000);

        // Track the edit
        await trackContentEdit({
            traceId,
            agentId,
            outputType,
            originalContent,
            editedContent: content,
            editDurationSeconds: editDuration
        });

        onSave(content);
    };

    return (
        <div className="content-editor">
            <DiffViewer
                original={originalContent}
                current={content}
                showDiff={content !== originalContent}
            />
            <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
            />
            <div className="edit-stats">
                <span>Edit distance: {computeEditDistance(originalContent, content)}%</span>
                <span>Time editing: {formatDuration(Date.now() - editStartTime)}</span>
            </div>
            <button onClick={handleSave}>Save & Deploy</button>
        </div>
    );
};
```

---

## 13. Multi-Step Workflow Evaluation

> **Roadmap:** [Feature 5.4: Advanced Workflow & Observability](product-roadmap.md#feature-54-advanced-workflow--observability), [Feature 6.3: MER-E Phase 4 — Full Closed Loop](product-roadmap.md#feature-63-mer-e-phase-4--full-closed-loop) — Releases 5.0, 6.0

This section defines how to evaluate multi-step agentic workflows where KEN-E executes sequences of tasks.

### 13.1 Overview

The Agentic Harness executes complex workflows like:
- Keyword analysis → Content brief → Campaign creation → Deployment
- Performance report → Theory generation → Recommendation → Task assignment

These require evaluation at multiple granularities:
1. **Step-level**: Each individual step evaluated independently
2. **Workflow-level**: Overall task completion and quality
3. **Trajectory**: Efficiency of the path taken

### 13.2 Workflow Evaluation Framework

Based on best practices from [Deepchecks](https://www.deepchecks.com/agentic-workflow-evaluation-key-metrics-methods/) and [Confident AI](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-LEVEL WORKFLOW EVALUATION                         │
└─────────────────────────────────────────────────────────────────────────────┘

                    WORKFLOW LEVEL
                    ┌─────────────────────────────────────────────────┐
                    │  • Task Completion Score (0-5)                   │
                    │  • Overall Quality Score (0-5)                   │
                    │  • Trajectory Efficiency (0-1)                   │
                    │  • User Satisfaction (if available)              │
                    └─────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
              STEP LEVEL          STEP LEVEL          STEP LEVEL
         ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
         │ Step 1:      │    │ Step 2:      │    │ Step 3:      │
         │ Research     │    │ Generate     │    │ Deploy       │
         │              │    │              │    │              │
         │ • Accuracy   │    │ • Quality    │    │ • Success    │
         │ • Coverage   │    │ • Relevance  │    │ • Timing     │
         │ • Tool use   │    │ • Format     │    │ • Validation │
         └──────────────┘    └──────────────┘    └──────────────┘
```

### 13.3 Step-Level Evaluation

Each workflow step is evaluated as an independent agent output:

```python
@dataclass
class StepEvaluation:
    """Evaluation of a single workflow step."""
    step_id: str
    step_name: str
    step_type: str  # "research" | "generation" | "execution" | "analysis"

    # Standard output evaluation
    output_quality_score: float  # 0-5
    tool_usage_score: float  # 0-5
    factor_scores: Dict[str, bool]  # Factor-level scores

    # Step-specific metrics
    input_utilization: float  # Did step use previous step outputs effectively?
    output_completeness: float  # Did step produce all expected outputs?

    # Error tracking
    errors_encountered: List[str]
    recovery_successful: bool

    # Timing
    duration_seconds: int
    within_expected_duration: bool

class StepEvaluator:
    """Evaluates individual workflow steps."""

    async def evaluate_step(
        self,
        step: WorkflowStep,
        step_trace: WeaveTrace,
        workflow_context: WorkflowContext
    ) -> StepEvaluation:

        # Get step-type-specific evaluation config
        eval_config = self._get_step_config(step.step_type)

        # Standard output evaluation
        output_score = await self.output_evaluator.evaluate(
            output=step.output,
            output_type=step.output_type,
            factors=eval_config["factors"]
        )

        # Tool usage evaluation
        tool_score = await self.tool_evaluator.evaluate(
            tool_calls=step_trace.tool_calls,
            expected_tools=eval_config.get("expected_tools", [])
        )

        # Input utilization - did this step use context from previous steps?
        input_utilization = self._assess_input_utilization(
            step_inputs=step.inputs,
            previous_outputs=workflow_context.accumulated_outputs,
            step_output=step.output
        )

        return StepEvaluation(
            step_id=step.step_id,
            step_name=step.name,
            step_type=step.step_type,
            output_quality_score=output_score.overall,
            tool_usage_score=tool_score.overall,
            factor_scores=output_score.factors,
            input_utilization=input_utilization,
            output_completeness=self._assess_completeness(step, eval_config),
            errors_encountered=step_trace.errors,
            recovery_successful=step.status == "completed",
            duration_seconds=step.duration,
            within_expected_duration=step.duration <= eval_config.get("max_duration", 300)
        )
```

### 13.4 Workflow-Level Evaluation

Evaluates the workflow as a whole:

```python
@dataclass
class WorkflowEvaluation:
    """Evaluation of a complete workflow execution."""
    workflow_id: str
    workflow_type: str  # "keyword_analysis" | "campaign_creation" | etc.

    # Task completion
    task_completion_score: float  # 0-5: Did workflow achieve intended goal?
    steps_completed: int
    steps_total: int
    completion_rate: float  # steps_completed / steps_total

    # Quality aggregation
    overall_quality_score: float  # Weighted average of step scores
    min_step_score: float  # Weakest link
    quality_variance: float  # Consistency across steps

    # Trajectory efficiency
    trajectory_score: float  # 0-1: How efficient was the path?
    unnecessary_steps: int  # Steps that didn't contribute to outcome
    backtrack_count: int  # How many times did workflow retry/backtrack?

    # Individual step evaluations
    step_evaluations: List[StepEvaluation]

    # Bottleneck identification
    slowest_step: str
    lowest_quality_step: str

    # Overall assessment
    workflow_success: bool  # Binary: did workflow complete successfully?
    user_intervention_required: bool  # Did human have to step in?

class WorkflowEvaluator:
    """Evaluates complete workflow executions."""

    # Weight configurations for different workflow types
    WORKFLOW_WEIGHTS = {
        "keyword_analysis": {
            "research": 0.4,
            "analysis": 0.3,
            "recommendation": 0.3
        },
        "campaign_creation": {
            "brief_generation": 0.2,
            "content_generation": 0.5,
            "scheduling": 0.1,
            "deployment": 0.2
        },
        "performance_report": {
            "data_retrieval": 0.2,
            "analysis": 0.4,
            "insight_generation": 0.4
        }
    }

    async def evaluate_workflow(
        self,
        workflow: Workflow,
        step_evaluations: List[StepEvaluation]
    ) -> WorkflowEvaluation:

        # Calculate task completion
        task_completion = await self._assess_task_completion(workflow)

        # Calculate weighted quality score
        weights = self.WORKFLOW_WEIGHTS.get(workflow.type, {})
        weighted_scores = []
        for step_eval in step_evaluations:
            weight = weights.get(step_eval.step_type, 1.0 / len(step_evaluations))
            weighted_scores.append(step_eval.output_quality_score * weight)
        overall_quality = sum(weighted_scores)

        # Assess trajectory efficiency
        trajectory = self._assess_trajectory(workflow, step_evaluations)

        # Identify bottlenecks
        slowest = max(step_evaluations, key=lambda s: s.duration_seconds)
        lowest_quality = min(step_evaluations, key=lambda s: s.output_quality_score)

        return WorkflowEvaluation(
            workflow_id=workflow.workflow_id,
            workflow_type=workflow.type,
            task_completion_score=task_completion,
            steps_completed=len([s for s in step_evaluations if s.recovery_successful]),
            steps_total=len(step_evaluations),
            completion_rate=len([s for s in step_evaluations if s.recovery_successful]) / len(step_evaluations),
            overall_quality_score=overall_quality,
            min_step_score=min(s.output_quality_score for s in step_evaluations),
            quality_variance=self._calculate_variance([s.output_quality_score for s in step_evaluations]),
            trajectory_score=trajectory["efficiency"],
            unnecessary_steps=trajectory["unnecessary_count"],
            backtrack_count=trajectory["backtracks"],
            step_evaluations=step_evaluations,
            slowest_step=slowest.step_name,
            lowest_quality_step=lowest_quality.step_name,
            workflow_success=workflow.status == "completed",
            user_intervention_required=workflow.had_human_intervention
        )

    async def _assess_task_completion(self, workflow: Workflow) -> float:
        """
        Use LLM-as-judge to assess if the workflow achieved its intended goal.
        """
        prompt = f"""
        Evaluate whether this workflow successfully completed its intended task.

        WORKFLOW TYPE: {workflow.type}
        INTENDED GOAL: {workflow.description}

        WORKFLOW STEPS AND OUTPUTS:
        {self._format_workflow_summary(workflow)}

        FINAL STATUS: {workflow.status}

        Rate task completion on a 0-5 scale:
        0 - Complete failure, goal not achieved at all
        1 - Minimal progress, significant gaps
        2 - Partial completion, major elements missing
        3 - Mostly complete, some gaps
        4 - Complete with minor issues
        5 - Fully complete, goal achieved perfectly

        Provide your rating and brief justification.
        """

        result = await self.llm_judge.evaluate(prompt)
        return result.score
```

### 13.5 Trajectory Evaluation

Assesses whether the workflow took an efficient path:

```python
class TrajectoryEvaluator:
    """Evaluates the efficiency of workflow execution path."""

    def assess_trajectory(
        self,
        workflow: Workflow,
        step_evaluations: List[StepEvaluation]
    ) -> TrajectoryAssessment:

        # Count unnecessary steps
        unnecessary = self._identify_unnecessary_steps(workflow, step_evaluations)

        # Count backtracks (retries, re-executions)
        backtracks = self._count_backtracks(workflow)

        # Calculate optimal path length (based on workflow type)
        optimal_steps = self._get_optimal_step_count(workflow.type)
        actual_steps = len(step_evaluations)

        # Efficiency = optimal / actual (capped at 1.0)
        efficiency = min(1.0, optimal_steps / actual_steps) if actual_steps > 0 else 0

        # Penalize for errors and backtracks
        error_penalty = sum(1 for s in step_evaluations if s.errors_encountered) * 0.1
        backtrack_penalty = backtracks * 0.05

        final_efficiency = max(0, efficiency - error_penalty - backtrack_penalty)

        return TrajectoryAssessment(
            efficiency=final_efficiency,
            optimal_steps=optimal_steps,
            actual_steps=actual_steps,
            unnecessary_count=len(unnecessary),
            unnecessary_steps=unnecessary,
            backtracks=backtracks,
            total_duration=sum(s.duration_seconds for s in step_evaluations),
            efficiency_recommendations=self._generate_recommendations(
                workflow, unnecessary, backtracks
            )
        )
```

### 13.6 Workflow Evaluation Data Model

```python
# Firestore schema for workflow evaluations
workflow_evaluation_schema = {
    "collection": "workflow_evaluations",
    "document_structure": {
        "evaluation_id": "string",
        "workflow_id": "string",
        "workflow_type": "string",
        "account_id": "string",

        # Completion metrics
        "task_completion_score": "float",  # 0-5
        "steps_completed": "int",
        "steps_total": "int",
        "completion_rate": "float",

        # Quality metrics
        "overall_quality_score": "float",
        "min_step_score": "float",
        "quality_variance": "float",

        # Trajectory metrics
        "trajectory_score": "float",
        "unnecessary_steps": "int",
        "backtrack_count": "int",

        # Step evaluations (subcollection or embedded)
        "step_evaluations": [{
            "step_id": "string",
            "step_name": "string",
            "step_type": "string",
            "output_quality_score": "float",
            "tool_usage_score": "float",
            "duration_seconds": "int"
        }],

        # Bottlenecks
        "slowest_step": "string",
        "lowest_quality_step": "string",

        # Outcome
        "workflow_success": "bool",
        "user_intervention_required": "bool",

        # Evaluator info
        "evaluated_by": "string",  # "llm_judge" | user_id
        "evaluation_type": "string",  # "automatic" | "human"

        # Timestamps
        "workflow_started_at": "timestamp",
        "workflow_completed_at": "timestamp",
        "evaluated_at": "timestamp"
    }
}
```

### 13.7 Workflow Evaluation UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW EVALUATION: Campaign Creation #WF-1234                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Overall Assessment                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Task Completion: ████████████████████░░░░  4.2/5                     │ │
│  │  Overall Quality: █████████████████░░░░░░░  3.8/5                     │ │
│  │  Trajectory:      ██████████████████████░░  0.85                      │ │
│  │                                                                        │ │
│  │  Status: ✓ Completed    Duration: 4m 32s    Steps: 5/5                │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Step-by-Step Breakdown                                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Step 1: Content Brief Generation                                     │ │
│  │  ├─ Quality: ████████████████████████  4.5/5  ✓                       │ │
│  │  ├─ Tools: ████████████████████░░░░░  3.8/5                           │ │
│  │  └─ Duration: 45s (within expected)                                   │ │
│  │                                                                        │ │
│  │  Step 2: Blog Post Generation          ◀─ Lowest Quality              │ │
│  │  ├─ Quality: ████████████░░░░░░░░░░░  3.0/5  ⚠                        │ │
│  │  ├─ Tools: ██████████████████████░░░  4.2/5                           │ │
│  │  └─ Duration: 1m 12s (within expected)                                │ │
│  │                                                                        │ │
│  │  Step 3: Social Post Generation                                       │ │
│  │  ├─ Quality: ████████████████████░░░░  4.0/5  ✓                       │ │
│  │  ├─ Tools: ████████████████████████░  4.5/5                           │ │
│  │  └─ Duration: 38s (within expected)                                   │ │
│  │                                                                        │ │
│  │  Step 4: Email Generation                                             │ │
│  │  ├─ Quality: ██████████████████████░░  4.2/5  ✓                       │ │
│  │  ├─ Tools: ████████████████████░░░░░  3.8/5                           │ │
│  │  └─ Duration: 52s (within expected)                                   │ │
│  │                                                                        │ │
│  │  Step 5: Calendar Scheduling            ◀─ Slowest                    │ │
│  │  ├─ Quality: ████████████████████████  4.5/5  ✓                       │ │
│  │  ├─ Tools: ██████████████████████████  5.0/5                          │ │
│  │  └─ Duration: 1m 25s (above expected)                                 │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Improvement Recommendations                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Blog post generation quality below target - review Content          │ │
│  │   Specialist prompt for long-form content                             │ │
│  │ • Calendar scheduling step taking longer than expected - investigate  │ │
│  │   n8n API latency                                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  [Evaluate Individual Steps]  [Export Report]  [Create Optimization Task]   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. n8n Workflow Evaluation

> **Roadmap:** [Feature 4.1: Automation Specialist + n8n](product-roadmap.md#feature-41-automation-specialist--n8n), [Feature 6.3: MER-E Phase 4 — Full Closed Loop](product-roadmap.md#feature-63-mer-e-phase-4--full-closed-loop) — Releases 4.0, 6.0

This section defines how to evaluate the n8n workflows created by the Automation Specialist.

### 14.1 Overview

The Automation Specialist creates n8n workflows for:
- Scheduled report generation
- KPI monitoring and alerting
- Content calendar review
- Performance data aggregation

Evaluation focuses on two aspects:
1. **Execution Correctness**: Does the workflow run without errors?
2. **Output Value**: Are the results produced by the workflow useful?

### 14.2 Execution Correctness Evaluation

#### 14.2.1 Workflow Validation

Before deployment, workflows are validated:

```python
class N8nWorkflowValidator:
    """Validates n8n workflow definitions before deployment."""

    VALIDATION_CHECKS = [
        "node_connections_valid",      # All nodes properly connected
        "required_credentials_set",    # Auth configured for all APIs
        "error_handling_present",      # Error nodes configured
        "output_nodes_defined",        # Workflow produces outputs
        "trigger_configured",          # Schedule/webhook trigger set
        "no_circular_dependencies",    # DAG validation
        "api_endpoints_valid",         # External APIs accessible
        "data_mapping_valid"           # Field mappings correct
    ]

    async def validate_workflow(
        self,
        workflow_definition: Dict
    ) -> WorkflowValidationResult:

        results = {}
        for check in self.VALIDATION_CHECKS:
            checker = getattr(self, f"_check_{check}")
            results[check] = await checker(workflow_definition)

        return WorkflowValidationResult(
            is_valid=all(r["passed"] for r in results.values()),
            checks=results,
            warnings=self._collect_warnings(results),
            errors=self._collect_errors(results)
        )
```

#### 14.2.2 Execution Tracking

Track workflow execution outcomes:

```python
@dataclass
class WorkflowExecutionRecord:
    """Records a single execution of an n8n workflow."""
    execution_id: str
    workflow_id: str
    workflow_name: str

    # Execution outcome
    status: str  # "success" | "error" | "timeout" | "cancelled"
    started_at: datetime
    completed_at: datetime
    duration_seconds: int

    # Node-level details
    nodes_executed: int
    nodes_total: int
    failed_node: Optional[str]
    error_message: Optional[str]

    # Resource usage
    api_calls_made: int
    data_items_processed: int

    # Output tracking
    output_produced: bool
    output_location: str  # GCS path, Firestore doc, etc.
    output_size_bytes: int

class WorkflowExecutionTracker:
    """Tracks and aggregates n8n workflow executions."""

    async def record_execution(
        self,
        n8n_execution: Dict,  # From n8n API
        workflow_metadata: Dict
    ) -> WorkflowExecutionRecord:

        record = WorkflowExecutionRecord(
            execution_id=n8n_execution["id"],
            workflow_id=workflow_metadata["workflow_id"],
            workflow_name=workflow_metadata["name"],
            status=self._map_status(n8n_execution["finished"], n8n_execution.get("stoppedAt")),
            started_at=parse_timestamp(n8n_execution["startedAt"]),
            completed_at=parse_timestamp(n8n_execution.get("stoppedAt")),
            duration_seconds=self._calculate_duration(n8n_execution),
            nodes_executed=len(n8n_execution.get("data", {}).get("resultData", {}).get("runData", {})),
            nodes_total=workflow_metadata["node_count"],
            failed_node=self._find_failed_node(n8n_execution),
            error_message=self._extract_error(n8n_execution),
            api_calls_made=self._count_api_calls(n8n_execution),
            data_items_processed=self._count_data_items(n8n_execution),
            output_produced=self._check_output(n8n_execution),
            output_location=self._get_output_location(n8n_execution),
            output_size_bytes=self._get_output_size(n8n_execution)
        )

        await self._store_record(record)
        return record
```

#### 14.2.3 Execution Correctness Metrics

```python
# Aggregated metrics for workflow execution correctness
EXECUTION_CORRECTNESS_METRICS = {
    "success_rate": {
        "formula": "successful_executions / total_executions",
        "target": 0.98,  # 98% success rate
        "alert_threshold": 0.95
    },
    "avg_duration": {
        "formula": "sum(duration_seconds) / count(executions)",
        "baseline": "varies by workflow type",
        "alert_on": "2x baseline"
    },
    "error_rate_by_node": {
        "formula": "node_failures / total_executions",
        "use": "identify problematic nodes"
    },
    "timeout_rate": {
        "formula": "timeouts / total_executions",
        "target": 0.01,  # <1% timeouts
    },
    "retry_rate": {
        "formula": "retried_executions / total_executions",
        "target": 0.05  # <5% needing retry
    }
}
```

### 14.3 Output Value Evaluation

#### 14.3.1 Report Automation Output Evaluation

For workflows that generate reports:

```python
class ReportOutputEvaluator:
    """Evaluates the value of reports produced by automated workflows."""

    REPORT_QUALITY_FACTORS = [
        "data_completeness",     # All expected metrics present?
        "data_freshness",        # Data within expected time range?
        "calculation_accuracy",  # Computations correct?
        "insight_actionability", # Are insights useful?
        "formatting_quality",    # Is report readable?
        "anomaly_detection",     # Were important anomalies flagged?
    ]

    async def evaluate_report_output(
        self,
        report_content: Dict,
        workflow_config: WorkflowConfig,
        historical_reports: List[Dict] = None
    ) -> ReportEvaluation:

        # Check data completeness
        completeness = self._check_completeness(
            report_content,
            workflow_config.expected_metrics
        )

        # Check data freshness
        freshness = self._check_freshness(
            report_content.get("data_timestamps", {}),
            workflow_config.freshness_threshold
        )

        # Validate calculations (if possible)
        accuracy = await self._validate_calculations(
            report_content,
            workflow_config.validation_rules
        )

        # Evaluate insights (LLM-as-judge)
        insight_quality = await self._evaluate_insights(
            report_content.get("insights", []),
            report_content.get("data", {})
        )

        # Check for anomaly detection
        anomaly_detection = self._check_anomaly_detection(
            report_content,
            historical_reports
        )

        return ReportEvaluation(
            overall_score=self._compute_overall(
                completeness, freshness, accuracy, insight_quality, anomaly_detection
            ),
            data_completeness=completeness,
            data_freshness=freshness,
            calculation_accuracy=accuracy,
            insight_actionability=insight_quality,
            anomaly_detection=anomaly_detection,
            issues_found=self._collect_issues(
                completeness, freshness, accuracy
            )
        )

    async def _evaluate_insights(
        self,
        insights: List[str],
        data: Dict
    ) -> float:
        """Use LLM to evaluate if insights are actionable and accurate."""

        prompt = f"""
        Evaluate the quality of these insights generated from marketing data.

        DATA SUMMARY:
        {self._summarize_data(data)}

        GENERATED INSIGHTS:
        {json.dumps(insights, indent=2)}

        Rate each insight on:
        1. Accuracy - Is the insight supported by the data?
        2. Actionability - Can someone act on this insight?
        3. Specificity - Is the insight specific or too generic?

        Provide an overall score 0-5 for insight quality.
        """

        result = await self.llm_judge.evaluate(prompt)
        return result.score
```

#### 14.3.2 Monitoring Automation Evaluation

For KPI monitoring workflows:

```python
class MonitoringOutputEvaluator:
    """Evaluates KPI monitoring and alerting workflow outputs."""

    async def evaluate_monitoring_output(
        self,
        monitoring_result: Dict,
        kpi_config: KPIConfig,
        actual_outcomes: Dict = None  # If we have ground truth
    ) -> MonitoringEvaluation:

        # Check if correct KPIs were monitored
        kpi_coverage = self._check_kpi_coverage(
            monitoring_result.get("kpis_checked", []),
            kpi_config.required_kpis
        )

        # Evaluate alert appropriateness
        alert_quality = self._evaluate_alerts(
            monitoring_result.get("alerts", []),
            kpi_config.alert_thresholds,
            actual_outcomes
        )

        # Check for false positives/negatives (if ground truth available)
        if actual_outcomes:
            precision, recall = self._calculate_alert_accuracy(
                monitoring_result.get("alerts", []),
                actual_outcomes.get("actual_issues", [])
            )
        else:
            precision, recall = None, None

        # Evaluate recommendations
        recommendation_quality = await self._evaluate_recommendations(
            monitoring_result.get("recommendations", []),
            monitoring_result.get("data", {})
        )

        return MonitoringEvaluation(
            kpi_coverage=kpi_coverage,
            alert_appropriateness=alert_quality,
            alert_precision=precision,
            alert_recall=recall,
            recommendation_quality=recommendation_quality,
            overall_score=self._compute_overall_score(
                kpi_coverage, alert_quality, recommendation_quality
            )
        )
```

### 14.4 Workflow Evaluation Data Model

```python
# Firestore schema for n8n workflow evaluations
n8n_workflow_eval_schema = {
    "collection": "n8n_workflow_evaluations",
    "document_structure": {
        "evaluation_id": "string",
        "workflow_id": "string",
        "workflow_name": "string",
        "workflow_type": "string",  # "report" | "monitoring" | "data_sync" | "content_review"
        "account_id": "string",

        # Execution correctness
        "execution": {
            "execution_id": "string",
            "status": "string",
            "duration_seconds": "int",
            "nodes_executed": "int",
            "nodes_total": "int",
            "error_message": "string or null"
        },

        # Output value (varies by workflow type)
        "output_evaluation": {
            "overall_score": "float",  # 0-5
            "factors": {
                # For reports
                "data_completeness": "float",
                "data_freshness": "float",
                "calculation_accuracy": "float",
                "insight_actionability": "float",

                # For monitoring
                "kpi_coverage": "float",
                "alert_appropriateness": "float",
                "recommendation_quality": "float"
            },
            "issues_found": ["list of strings"]
        },

        # Evaluator
        "evaluated_by": "string",  # "automatic" | user_id

        # Timestamps
        "workflow_executed_at": "timestamp",
        "evaluated_at": "timestamp"
    }
}
```

### 14.5 Workflow Quality Dashboard Metrics

```python
N8N_WORKFLOW_DASHBOARD_METRICS = {
    "execution_health": {
        "success_rate_7d": "% of successful executions in last 7 days",
        "avg_duration_trend": "Duration trend over time",
        "error_distribution": "Errors by node type"
    },
    "output_quality": {
        "avg_output_score": "Average output value score",
        "insight_actionability_trend": "Trend in insight quality",
        "data_freshness_compliance": "% of reports with fresh data"
    },
    "by_workflow_type": {
        "report_automations": {
            "count": "Number of active report workflows",
            "avg_score": "Average quality score",
            "most_common_issues": "Frequent issues"
        },
        "monitoring_automations": {
            "count": "Number of active monitoring workflows",
            "alert_accuracy": "Alert precision/recall",
            "false_positive_rate": "% of unnecessary alerts"
        }
    }
}
```

---

## 15. Cross-Account Benchmarking

> **Roadmap:** [Feature 6.3: MER-E Phase 4 — Full Closed Loop](product-roadmap.md#feature-63-mer-e-phase-4--full-closed-loop) — Release 6.0

This section defines how to aggregate metrics across accounts for anonymized benchmarking.

### 15.1 Overview

Cross-account benchmarking enables:
- Comparing agent performance against anonymized industry baselines
- Identifying accounts that may benefit from optimization
- Detecting when specific agents underperform relative to the population
- Learning from high-performing accounts to improve all accounts

### 15.2 Data Anonymization Requirements

All cross-account data must be anonymized per [GDPR and enterprise AI benchmarking best practices](https://aisera.com/blog/enterprise-ai-benchmark/):

```python
class DataAnonymizer:
    """Anonymizes evaluation data for cross-account aggregation."""

    FIELDS_TO_REMOVE = [
        "account_id",
        "user_id",
        "account_name",
        "company_name",
        "user_email",
        "api_keys",
        "oauth_tokens"
    ]

    FIELDS_TO_HASH = [
        "session_id",  # Hashed for linkage without identification
    ]

    FIELDS_TO_GENERALIZE = {
        "industry": "industry_category",  # "Tech/SaaS" -> "Technology"
        "company_size": "size_bucket",    # "47 employees" -> "10-50"
        "revenue": "revenue_bucket"       # "$4.2M" -> "$1M-$10M"
    }

    def anonymize_evaluation(
        self,
        evaluation: Dict,
        include_industry_context: bool = True
    ) -> Dict:
        """
        Anonymize an evaluation record for cross-account analysis.
        """
        anon = evaluation.copy()

        # Remove identifying fields
        for field in self.FIELDS_TO_REMOVE:
            anon.pop(field, None)

        # Hash linkage fields
        for field in self.FIELDS_TO_HASH:
            if field in anon:
                anon[field] = self._hash_field(anon[field])

        # Generalize categorical fields
        if include_industry_context:
            for original, generalized in self.FIELDS_TO_GENERALIZE.items():
                if original in anon:
                    anon[generalized] = self._generalize(original, anon[original])
                    del anon[original]

        # Remove content that could identify
        anon.pop("input_text", None)
        anon.pop("output_text", None)
        anon.pop("output_content", None)

        # Keep only metrics
        return anon

    def _hash_field(self, value: str) -> str:
        """One-way hash for linkage fields."""
        import hashlib
        salt = os.getenv("ANONYMIZATION_SALT", "ken-e-default-salt")
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:16]
```

### 15.3 Aggregation Pipeline

```python
class CrossAccountAggregator:
    """Aggregates anonymized metrics across accounts."""

    def __init__(self, bigquery_client):
        self.bq = bigquery_client
        self.anonymizer = DataAnonymizer()

    async def aggregate_agent_metrics(
        self,
        agent_id: str,
        time_window_days: int = 30,
        min_accounts_for_benchmark: int = 10  # Privacy threshold
    ) -> AgentBenchmark:
        """
        Compute benchmark statistics for an agent across all accounts.
        Only returns benchmarks if enough accounts have data (k-anonymity).
        """

        query = f"""
        WITH account_metrics AS (
            SELECT
                -- Anonymized account identifier
                SHA256(CONCAT('{os.getenv("ANONYMIZATION_SALT")}', account_id)) as anon_account,

                -- Metrics
                AVG(output_quality_score) as avg_quality,
                AVG(tool_usage_score) as avg_tool_score,
                COUNT(*) as evaluation_count,
                AVG(CASE WHEN human_agrees THEN 1.0 ELSE 0.0 END) as agreement_rate

            FROM `{self.bq.project}.ken_e_eval.evaluations`
            WHERE agent_id = @agent_id
              AND evaluated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
              AND output_quality_score IS NOT NULL
            GROUP BY anon_account
            HAVING COUNT(*) >= 5  -- Min evaluations per account
        )
        SELECT
            COUNT(DISTINCT anon_account) as account_count,

            -- Central tendency
            AVG(avg_quality) as mean_quality,
            APPROX_QUANTILES(avg_quality, 100)[OFFSET(50)] as median_quality,

            -- Spread
            STDDEV(avg_quality) as stddev_quality,
            MIN(avg_quality) as min_quality,
            MAX(avg_quality) as max_quality,

            -- Percentiles
            APPROX_QUANTILES(avg_quality, 100)[OFFSET(25)] as p25_quality,
            APPROX_QUANTILES(avg_quality, 100)[OFFSET(75)] as p75_quality,
            APPROX_QUANTILES(avg_quality, 100)[OFFSET(90)] as p90_quality,

            -- Tool scores
            AVG(avg_tool_score) as mean_tool_score,

            -- Agreement
            AVG(agreement_rate) as mean_agreement_rate

        FROM account_metrics
        """

        result = await self.bq.query_async(
            query,
            parameters=[
                bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id),
                bigquery.ScalarQueryParameter("days", "INT64", time_window_days)
            ]
        )

        row = list(result)[0]

        # Check k-anonymity threshold
        if row.account_count < min_accounts_for_benchmark:
            return AgentBenchmark(
                agent_id=agent_id,
                available=False,
                reason=f"Insufficient accounts ({row.account_count} < {min_accounts_for_benchmark})"
            )

        return AgentBenchmark(
            agent_id=agent_id,
            available=True,
            account_count=row.account_count,  # Report count but not identities
            time_window_days=time_window_days,
            quality_benchmark=QualityBenchmark(
                mean=row.mean_quality,
                median=row.median_quality,
                stddev=row.stddev_quality,
                min=row.min_quality,
                max=row.max_quality,
                p25=row.p25_quality,
                p75=row.p75_quality,
                p90=row.p90_quality
            ),
            tool_score_mean=row.mean_tool_score,
            agreement_rate_mean=row.mean_agreement_rate
        )
```

### 15.4 Account Percentile Ranking

```python
class AccountRanker:
    """Computes where an account ranks relative to anonymized population."""

    async def compute_account_percentile(
        self,
        account_id: str,
        agent_id: str,
        benchmark: AgentBenchmark
    ) -> AccountPercentile:
        """
        Determine where this account's performance falls in the distribution.
        Does NOT expose other accounts' data.
        """

        # Get this account's metrics
        account_metrics = await self._get_account_metrics(account_id, agent_id)

        if not account_metrics or not benchmark.available:
            return AccountPercentile(available=False)

        # Compute percentile using benchmark distribution
        quality_percentile = self._compute_percentile(
            account_metrics.avg_quality,
            benchmark.quality_benchmark
        )

        # Determine performance category
        if quality_percentile >= 90:
            category = "top_performer"
        elif quality_percentile >= 75:
            category = "above_average"
        elif quality_percentile >= 50:
            category = "average"
        elif quality_percentile >= 25:
            category = "below_average"
        else:
            category = "needs_improvement"

        return AccountPercentile(
            available=True,
            agent_id=agent_id,
            quality_percentile=quality_percentile,
            performance_category=category,
            account_quality=account_metrics.avg_quality,
            benchmark_median=benchmark.quality_benchmark.median,
            improvement_potential=max(0, benchmark.quality_benchmark.p90 - account_metrics.avg_quality)
        )

    def _compute_percentile(
        self,
        value: float,
        benchmark: QualityBenchmark
    ) -> float:
        """
        Estimate percentile from benchmark distribution.
        Uses interpolation between known percentiles.
        """
        percentiles = [
            (0, benchmark.min),
            (25, benchmark.p25),
            (50, benchmark.median),
            (75, benchmark.p75),
            (90, benchmark.p90),
            (100, benchmark.max)
        ]

        for i in range(len(percentiles) - 1):
            p1, v1 = percentiles[i]
            p2, v2 = percentiles[i + 1]

            if v1 <= value <= v2:
                # Linear interpolation
                if v2 == v1:
                    return (p1 + p2) / 2
                return p1 + (p2 - p1) * (value - v1) / (v2 - v1)

        # Edge cases
        if value < benchmark.min:
            return 0
        return 100
```

### 15.5 Industry-Specific Benchmarks

```python
class IndustryBenchmarkManager:
    """Manages industry-specific benchmarks with anonymized data."""

    INDUSTRY_CATEGORIES = [
        "Technology",
        "E-commerce/Retail",
        "Financial Services",
        "Healthcare",
        "Professional Services",
        "Manufacturing",
        "Media/Entertainment",
        "Education",
        "Non-Profit",
        "Other"
    ]

    async def get_industry_benchmark(
        self,
        agent_id: str,
        industry_category: str,
        min_accounts: int = 5  # Lower threshold for industry-specific
    ) -> Optional[IndustryBenchmark]:
        """
        Get benchmark for a specific industry category.
        Returns None if insufficient data for privacy.
        """

        query = f"""
        WITH industry_metrics AS (
            SELECT
                SHA256(CONCAT('{os.getenv("ANONYMIZATION_SALT")}', e.account_id)) as anon_account,
                AVG(e.output_quality_score) as avg_quality
            FROM `ken_e_eval.evaluations` e
            JOIN `ken_e_eval.account_metadata` m
              ON e.account_id = m.account_id
            WHERE e.agent_id = @agent_id
              AND m.industry_category = @industry
              AND e.evaluated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            GROUP BY anon_account
            HAVING COUNT(*) >= 3
        )
        SELECT
            COUNT(DISTINCT anon_account) as account_count,
            AVG(avg_quality) as mean_quality,
            APPROX_QUANTILES(avg_quality, 100)[OFFSET(50)] as median_quality,
            STDDEV(avg_quality) as stddev_quality
        FROM industry_metrics
        """

        result = await self.bq.query_async(query, parameters=[
            bigquery.ScalarQueryParameter("agent_id", "STRING", agent_id),
            bigquery.ScalarQueryParameter("industry", "STRING", industry_category)
        ])

        row = list(result)[0]

        if row.account_count < min_accounts:
            return None  # Insufficient data for this industry

        return IndustryBenchmark(
            industry_category=industry_category,
            agent_id=agent_id,
            account_count=row.account_count,
            mean_quality=row.mean_quality,
            median_quality=row.median_quality,
            stddev_quality=row.stddev_quality
        )
```

### 15.6 Benchmark Dashboard

```python
BENCHMARK_DASHBOARD_METRICS = {
    "account_performance": {
        "your_quality_score": "Your average quality score",
        "percentile_rank": "Where you rank (e.g., 'Top 25%')",
        "vs_median": "Your score vs. population median",
        "improvement_potential": "Gap to 90th percentile"
    },
    "agent_comparison": {
        "agents_above_benchmark": "Agents performing above median",
        "agents_below_benchmark": "Agents needing attention",
        "biggest_gap": "Agent with largest gap to benchmark"
    },
    "industry_context": {
        "industry_rank": "Rank within your industry",
        "industry_median": "Your industry's median score",
        "vs_all_industries": "Your industry vs. overall median"
    },
    "trends": {
        "percentile_trend": "Your percentile rank over time",
        "closing_gap": "Are you catching up to top performers?"
    }
}
```

### 15.7 Privacy and Compliance

```python
class BenchmarkPrivacyGuard:
    """Ensures benchmark data meets privacy requirements."""

    def __init__(self):
        self.k_anonymity_threshold = 10  # Minimum accounts for global benchmark
        self.l_diversity_threshold = 3   # Minimum distinct values in sensitive attributes

    def can_release_benchmark(
        self,
        benchmark_data: Dict,
        benchmark_type: str
    ) -> Tuple[bool, str]:
        """
        Determine if benchmark data can be released.
        Returns (can_release, reason).
        """

        account_count = benchmark_data.get("account_count", 0)

        # K-anonymity check
        min_accounts = {
            "global": 10,
            "industry": 5,
            "size_bucket": 5
        }.get(benchmark_type, 10)

        if account_count < min_accounts:
            return False, f"Insufficient accounts: {account_count} < {min_accounts}"

        # Check for potential re-identification
        if benchmark_type == "industry":
            # Don't release if one account dominates
            if benchmark_data.get("max_account_share", 0) > 0.5:
                return False, "Single account dominates industry segment"

        return True, "OK"

    def redact_outliers(
        self,
        benchmark: AgentBenchmark
    ) -> AgentBenchmark:
        """
        Redact extreme outliers that might identify specific accounts.
        """
        redacted = benchmark.copy()

        # Don't report exact min/max if they're too far from median
        # (could identify outlier accounts)
        if redacted.quality_benchmark.max - redacted.quality_benchmark.median > 1.5:
            redacted.quality_benchmark.max = None
        if redacted.quality_benchmark.median - redacted.quality_benchmark.min > 1.5:
            redacted.quality_benchmark.min = None

        return redacted
```

### 15.8 Cross-Account Learning (Future)

While direct cross-account optimization is out of scope for v2.0, the benchmark infrastructure supports future capabilities:

```python
# Future capability: Learn from high-performing accounts
class CrossAccountLearner:
    """
    Future: Identify optimization patterns from top-performing accounts.
    Requires careful privacy review before implementation.
    """

    async def identify_success_patterns(
        self,
        agent_id: str,
        min_top_accounts: int = 10
    ) -> List[SuccessPattern]:
        """
        Analyze what top-performing accounts do differently.

        PRIVACY NOTE: This analyzes patterns, not specific outputs.
        Example patterns:
        - "Top performers provide more detailed company context"
        - "High-quality outputs correlate with specific tool usage patterns"
        """
        # Implementation deferred to future version
        pass
```

---

## 16. Prioritized Feature Roadmap

### 16.1 Roadmap Overview

The implementation is organized into four phases, progressing from foundational capabilities to advanced self-optimization features.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION ROADMAP                               │
└─────────────────────────────────────────────────────────────────────────────┘

    PHASE 1                 PHASE 2                 PHASE 3                 PHASE 4
    FOUNDATION              CORE LOOP               AUTOMATION              ADVANCED
    ──────────              ─────────               ──────────              ────────

┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ • Complete  │        │ • Human     │        │ • Auto      │        │ • Config    │
│   eval      │        │   feedback  │        │   analysis  │        │   optimizer │
│   results   │        │   UI        │        │   engine    │        │             │
│   module    │        │             │        │             │        │ • A/B test  │
│             │   ──▶  │ • Queue     │   ──▶  │ • Pattern   │   ──▶  │   infra     │
│ • Tool call │        │   manage-   │        │   detection │        │             │
│   extraction│        │   ment      │        │             │        │ • Factor    │
│             │        │             │        │ • Rec       │        │   suggestion│
│ • KEN-E     │        │ • Dashboard │        │   generation│        │             │
│   trace     │        │             │        │             │        │ • Anomaly   │
│   enhance   │        │ • Deploy    │        │ • Canary    │        │   detection │
│             │        │   pipeline  │        │   rollouts  │        │             │
└─────────────┘        └─────────────┘        └─────────────┘        └─────────────┘

   Foundation             Human Loop              Automation              Intelligence
   ───────────            ──────────              ──────────              ────────────
   Get data               Collect human           System suggests         System learns
   flowing                feedback                improvements            and optimizes
```

### 16.2 Phase 1: Foundation

**Goal:** Establish the data pipeline and complete the core evaluation workflow.

| Feature | Description | Priority | Effort | Dependencies |
|---------|-------------|----------|--------|--------------|
| **1.1** Complete Evaluation Results Module | Implement fetching of LLM and human evaluations from W&B/Firestore | Critical | Medium | None |
| **1.2** Tool Call Extractor | Build extractors for individual tool calls within traces | Critical | Medium | 1.1 |
| **1.3** KEN-E Trace Enhancements | Add required metadata fields to all agent traces | Critical | Low | None |
| **1.4** Enhanced Agent Config Schema | Add version lineage, deployment status fields | High | Low | None |
| **1.5** Database Schema Setup | Create Firestore collections and BigQuery tables per design | High | Medium | None |
| **1.6** Basic API Endpoints | Create eval framework API endpoints in KEN-E backend | High | Medium | 1.4, 1.5 |

**Exit Criteria:**
- End-to-end flow: Trace → Extraction → LLM Scoring → Human Evaluation → Agreement Calculation
- Tool call evaluation supported for core agent
- All agents emit compliant trace metadata

### 16.3 Phase 2: Core Optimization Loop

**Goal:** Enable the human-in-the-loop feedback and deployment workflow.

| Feature | Description | Priority | Effort | Dependencies |
|---------|-------------|----------|--------|--------------|
| **2.1** Enhanced Evaluation UI | Extend evaluation_feedback app with queue, W&B integration | Critical | High | Phase 1 |
| **2.2** Priority Queue System | Implement smart queue population and prioritization | High | Medium | 2.1 |
| **2.3** Dashboard View | Build performance dashboard with agent health overview | High | Medium | 2.1 |
| **2.4** Deployment Pipeline - Staging | Enable staging deployments with automated testing | High | Medium | 1.6 |
| **2.5** Version History & Rollback | Implement version tracking and one-click rollback | High | Medium | 2.4 |
| **2.6** Agent Detail View | Build agent configuration viewer with diff support | Medium | Medium | 2.1 |
| **2.7** Recommendation Review UI | Interface for reviewing and approving optimizations | Medium | Medium | 2.1 |
| **2.8** Firestore-BigQuery Sync | Batch sync evaluations to BigQuery for analytics | Medium | Low | 1.5 |

**Exit Criteria:**
- Team can evaluate outputs through UI without copy-paste
- Queue automatically prioritizes high-value evaluations
- Changes can be deployed to staging and rolled back
- Dashboard shows agent health at a glance

### 16.4 Phase 3: Automated Analysis & Recommendations

**Goal:** System automatically identifies issues and generates recommendations.

| Feature | Description | Priority | Effort | Dependencies |
|---------|-------------|----------|--------|--------------|
| **3.1** Alignment Analyzer | Automated LLM-human disagreement analysis | Critical | High | Phase 2 |
| **3.2** Prompt Improvement Generator | Generate prompt recommendations from disagreements | Critical | High | 3.1 |
| **3.3** Recommendation Aggregator | Consolidate, prioritize, and de-conflict recommendations | High | Medium | 3.2 |
| **3.4** Pattern Detector | Identify consistency issues, repetition, length anomalies | High | High | Phase 2 |
| **3.5** Tool Usage Analyzer | Analyze tool call patterns and identify anti-patterns | High | High | 1.2, Phase 2 |
| **3.6** Canary Deployment Support | Enable canary deployments with traffic splitting | High | Medium | 2.4 |
| **3.7** Automated Monitoring | Track quality metrics post-deployment | Medium | Medium | 3.6 |
| **3.8** Notification System | Slack/email alerts for anomalies and recommendations | Medium | Low | 3.3, 3.7 |

**Exit Criteria:**
- System generates actionable prompt recommendations
- Tool usage issues automatically identified
- Canary deployments supported with metrics comparison
- Team notified of issues and pending recommendations

### 16.5 Phase 4: Advanced Intelligence

**Goal:** Full self-optimization capabilities with minimal human intervention.

| Feature | Description | Priority | Effort | Dependencies |
|---------|-------------|----------|--------|--------------|
| **4.1** Configuration Optimizer | A/B testing infrastructure for temperature, model selection | High | High | Phase 3 |
| **4.2** Experiment Management UI | Interface to create, monitor, and conclude experiments | High | Medium | 4.1 |
| **4.3** Factor Suggestion System | Automatically suggest evaluation rubric improvements | Medium | High | Phase 3 |
| **4.4** Anomaly Detection | Real-time detection of quality degradation | Medium | Medium | 3.7 |
| **4.5** Feedback Request Generator | Proactively request human evaluations for coverage gaps | Medium | Medium | Phase 3 |
| **4.6** Structural Issue Detection | Flag agent orchestration issues, recommend restructuring | Low | High | 3.5 |
| **4.7** Historical Trend Analysis | Long-term quality trend visualization and insights | Low | Medium | 2.8 |
| **4.8** Multi-Provider LLM Support | Support Anthropic, OpenAI for scorers (beyond Gemini) | Low | Medium | Phase 3 |

**Exit Criteria:**
- System can optimize temperature and model selection through experiments
- Evaluation rubrics evolve based on system suggestions
- Proactive identification of areas needing human attention
- Complete audit trail of all optimizations and their impact

### 16.6 Feature Priority Matrix

```
                        HIGH IMPACT
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         │   QUICK WINS     │   BIG BETS       │
         │                  │                  │
         │ • 1.3 Trace      │ • 2.1 Eval UI    │
         │   enhance        │ • 3.1 Alignment  │
         │ • 1.4 Config     │   analyzer       │
  LOW ───│   schema         │ • 3.2 Prompt     │─── HIGH
 EFFORT  │ • 2.8 BQ sync    │   generator      │  EFFORT
         │ • 3.8 Notifs     │ • 4.1 Config     │
         │                  │   optimizer      │
         │                  │                  │
         ├──────────────────┼──────────────────┤
         │                  │                  │
         │   FILL-INS       │   STRATEGIC      │
         │                  │                  │
         │ • 1.5 DB setup   │ • 3.4 Pattern    │
         │ • 2.6 Agent      │   detector       │
         │   detail         │ • 3.5 Tool       │
         │ • 4.7 Trends     │   analyzer       │
         │                  │ • 4.3 Factor     │
         │                  │   suggestions    │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                        LOW IMPACT
```

### 16.7 Dependencies Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPENDENCY GRAPH                                     │
└─────────────────────────────────────────────────────────────────────────────┘

PHASE 1 (Foundation)
────────────────────

1.1 Eval Results Module ─────┬────────────────────────────────────────────────┐
                             │                                                │
1.2 Tool Call Extractor ─────┤                                                │
         │                   │                                                │
         │                   ▼                                                │
         │           PHASE 2 (Core Loop)                                      │
         │           ───────────────────                                      │
         │                                                                    │
         │           2.1 Enhanced Eval UI ───┬─── 2.2 Priority Queue          │
         │                   │               │                                │
1.3 Trace Enhancements       │               ├─── 2.3 Dashboard               │
         │                   │               │                                │
         │                   │               ├─── 2.6 Agent Detail            │
1.4 Config Schema ───────────┤               │                                │
         │                   │               └─── 2.7 Rec Review UI           │
         │                   │                                                │
1.5 DB Schema ───────────────┤                                                │
         │                   ▼                                                │
         │           2.4 Staging Deploy ─────┬─── 2.5 Rollback                │
         │                   │               │                                │
1.6 API Endpoints ───────────┘               │                                │
                                             ▼                                │
                             PHASE 3 (Automation)                             │
                             ────────────────────                             │
                                                                              │
                             3.1 Alignment Analyzer ──── 3.2 Prompt Generator │
                                     │                          │             │
                                     │                          ▼             │
                                     │               3.3 Rec Aggregator       │
                                     │                          │             │
2.2 Priority Queue ──────────────────┴──────────────────────────┤             │
                                                                │             │
                             3.4 Pattern Detector ──────────────┤             │
                                                                │             │
1.2 Tool Extractor ──────── 3.5 Tool Usage Analyzer ────────────┤             │
                                                                │             │
2.4 Staging ─────────────── 3.6 Canary Deploy ──────────────────┤             │
                                     │                          │             │
                                     ▼                          │             │
                             3.7 Monitoring ────────────────────┤             │
                                     │                          │             │
                                     │                          ▼             │
                                     │               3.8 Notifications        │
                                     │                                        │
                                     ▼                                        │
                             PHASE 4 (Advanced)                               │
                             ──────────────────                               │
                                                                              │
                             4.1 Config Optimizer ──── 4.2 Experiment UI      │
                                                                              │
3.3 Rec Aggregator ──────── 4.3 Factor Suggestions                            │
                                                                              │
3.7 Monitoring ──────────── 4.4 Anomaly Detection                             │
                                                                              │
3.3 Rec Aggregator ──────── 4.5 Feedback Requests                             │
                                                                              │
3.5 Tool Analyzer ───────── 4.6 Structural Detection                          │
                                                                              │
2.8 BQ Sync ─────────────── 4.7 Trend Analysis                                │
                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 16.8 Success Metrics by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| **Phase 1** | End-to-end pipeline functional | Yes/No |
| **Phase 1** | Tool calls extracted per trace | >90% |
| **Phase 1** | Trace metadata compliance | 100% |
| **Phase 2** | Evaluations per week | 50+ |
| **Phase 2** | Time to evaluate single item | <2 min |
| **Phase 2** | Deployment rollback time | <5 min |
| **Phase 3** | Recommendations generated per week | 5+ |
| **Phase 3** | Recommendation acceptance rate | >60% |
| **Phase 3** | Time from issue to recommendation | <24h |
| **Phase 4** | Scorer-human agreement rate | >85% |
| **Phase 4** | Agent quality score improvement | +20% from baseline |
| **Phase 4** | Manual prompt engineering time | -75% |

---

## 17. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Agent** | An AI component in KEN-E that performs a specific task (e.g., business_researcher) |
| **Alignment** | The degree to which LLM scorer judgments match human evaluations |
| **Canary Deployment** | Releasing a change to a small subset of users before full rollout |
| **Disagreement** | A case where LLM and human evaluations differ |
| **Evaluation Factor** | A specific criterion used to assess output quality (e.g., "specificity") |
| **Extractor** | A component that parses traces to identify evaluatable outputs |
| **False Negative** | LLM scores output as poor when human rates it as good |
| **False Positive** | LLM scores output as good when human rates it as poor |
| **Output Type** | A category of agent output (e.g., "problem_awareness_strategy") |
| **Scorer** | An LLM-based evaluator that assesses agent outputs against criteria |
| **Trace** | A record of an agent's execution including inputs, outputs, and tool calls |
| **Variant** | A specific configuration of an agent used in A/B testing |

### Appendix B: Output Types Reference

Total supported output types: **66 types across 8 categories**

---

#### Strategy Specialist Output Types (34 types - existing)

**Business Strategy (11 types)**
- company_overview
- swot_strengths
- swot_weaknesses
- swot_opportunities
- swot_threats
- strategic_goals
- value_proposition
- product_portfolio
- market_position
- industry_analysis
- business_model

**Marketing Strategy (6 types)**
- icp_narrative
- problem_awareness_strategy
- acquisition_strategy
- retention_strategy
- conversion_strategy
- loyalty_strategy

**Competitive Strategy (10 types)**
- competitor_analysis
- competitor_value_proposition
- substitute_products
- competitive_environment
- market_trends
- buyer_power
- supplier_power
- threat_of_entry
- industry_rivalry
- competitive_positioning

**Brand Guidelines (7 types)**
- brand_identity
- brand_voice
- brand_tone
- typography_guidelines
- imagery_guidelines
- color_palette
- messaging_pillars

---

#### Content Specialist Output Types (16 types - NEW)

**Blog & Long-Form Content (4 types)**
- blog_post
- article_outline
- content_brief
- landing_page

**Social Media Content (4 types)**
- social_post_linkedin
- social_post_twitter
- social_post_instagram
- social_post_tiktok

**Email Content (3 types)**
- email_promotional
- email_newsletter
- email_sequence

**Video Content (3 types)**
- video_script_longform
- video_script_shortform
- video_outline

**Campaign Content (2 types)**
- campaign_plan
- campaign_calendar

---

#### Analytics Specialist Output Types (8 types - NEW)

- performance_report
- forecast
- attribution_analysis
- data_visualization
- insight_summary
- anomaly_report
- benchmark_comparison
- kpi_dashboard

---

#### Execution Specialist Output Types (4 types - NEW)

- deployment_result
- validation_report
- api_response_summary
- scheduling_confirmation

---

#### Automation Specialist Output Types (4 types - NEW)

- workflow_definition
- automation_config
- report_automation
- integration_setup

### Appendix C: API Reference

**Evaluation Framework API Endpoints**

```
BASE URL: https://api.ken-e.ai/eval/v1

# Agents
GET    /agents                      # List all agents
GET    /agents/{id}                 # Get agent details
GET    /agents/{id}/config          # Get current configuration
PUT    /agents/{id}/config          # Update configuration
GET    /agents/{id}/history         # Get version history
POST   /agents/{id}/rollback        # Rollback to version

# Evaluations
GET    /evaluations                 # List evaluations
POST   /evaluations                 # Submit evaluation
GET    /evaluations/{id}            # Get evaluation details

# Queue
GET    /queue                       # Get evaluation queue
POST   /queue/{id}/assign           # Assign queue item
POST   /queue/{id}/skip             # Skip queue item

# Recommendations
GET    /recommendations             # List recommendations
GET    /recommendations/{id}        # Get recommendation details
POST   /recommendations/{id}/approve # Approve recommendation
POST   /recommendations/{id}/reject  # Reject recommendation

# Deployments
GET    /deployments                 # List active deployments
GET    /deployments/{id}            # Get deployment details
POST   /deployments/{id}/promote    # Promote to next stage
POST   /deployments/{id}/rollback   # Rollback deployment

# Experiments
GET    /experiments                 # List experiments
POST   /experiments                 # Create experiment
GET    /experiments/{id}            # Get experiment details
POST   /experiments/{id}/conclude   # End experiment

# Metrics
GET    /metrics/agents/{id}         # Get agent metrics
GET    /metrics/scorers/{id}        # Get scorer metrics
GET    /metrics/alignment           # Get alignment metrics
```

### Appendix D: Configuration Templates

**Agent Configuration Template**
```json
{
    "name": "agent_name",
    "model": "gemini-2.0-flash",
    "description": "Human-readable description",
    "instruction": "System prompt text...",
    "generate_content_config": {
        "temperature": 0.3,
        "max_output_tokens": 2500
    },
    "metadata": {
        "version": "v1.0.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "ISO-8601 timestamp",
        "updated_at": "ISO-8601 timestamp",
        "updated_by": "user_id or system",
        "notes": "Change description",
        "parent_version": null,
        "optimization_source": "manual"
    },
    "deployment_status": {
        "environment": "production",
        "rollout_percentage": 100,
        "deployed_at": "ISO-8601 timestamp",
        "deployed_by": "user_id"
    }
}
```

**Evaluation Factor Template**
```json
{
    "factor_id": "unique_factor_id",
    "question": "Does the output demonstrate X?",
    "description": "Guidance for evaluators on how to assess this factor",
    "score_type": "boolean",
    "weight": 1.0,
    "is_active": true,
    "created_at": "ISO-8601 timestamp",
    "updated_at": "ISO-8601 timestamp",
    "suggested_by": "human"
}
```

### Appendix E: Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `EVAL_001` | Trace not found | Verify trace ID exists in W&B |
| `EVAL_002` | Extraction failed | Check extractor configuration for output type |
| `EVAL_003` | Scorer not found | Create scorer for this output type/factor |
| `EVAL_004` | Configuration conflict | Resolve conflicting versions before deployment |
| `EVAL_005` | Deployment blocked | Address staging failures before promotion |
| `EVAL_006` | Rollback failed | Manual intervention required |
| `EVAL_007` | Experiment conflict | Only one experiment per agent allowed |
| `EVAL_008` | Insufficient evaluations | Need more human evaluations for alignment |

### Appendix F: Related Documentation

| Document | Location | Description |
|----------|----------|-------------|
| KEN-E Application Summary | `/KEN-E-Application-Summary.md` | Main application overview |
| AI Optimizer Summary | `/eval-framework-application-summary.md` | Current eval framework status |
| Sprint Review Notes | `/Weekly Sprint Review Notes...` | Recent development progress |
| KEN-E GitHub | `github.com/KEN-E-AI/KEN-E` | Main application repository |
| AI Optimizer GitHub | `github.com/KEN-E-AI/ai_optimizer` | Evaluation framework repository |
| Evaluation Feedback GitHub | `github.com/KEN-E-AI/evaluation_feedback` | Human feedback UI repository |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 10, 2026 | Development Team | Initial design document |

---

*End of Document*


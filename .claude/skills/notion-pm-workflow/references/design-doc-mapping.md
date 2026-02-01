# Design Document Section Mapping

This reference maps MER-E features to relevant sections in `docs/MER-E_Design.md`.

## How to Use This Mapping

When working on a user story:
1. Identify the parent Feature number (e.g., "1.1" from "1.1.1 - Fetch Human Evaluations")
2. Look up the Feature in the table below
3. Read the **Primary Sections** for essential context
4. Read **Supporting Sections** if you need deeper understanding

## Feature to Design Document Section Mapping

### Release 1: Foundation (Features 1.1 - 1.6)

| Feature | Feature Name | Primary Sections | Supporting Sections |
|---------|--------------|------------------|---------------------|
| **1.1** | Evaluation Results Module | §4.2 Firestore Schema (lines 374-567), §4.5 W&B Weave Data Model (lines 754-787), §6.1-6.2 Trace Structure (lines 1187-1227) | §3.2 Component Responsibilities (lines 254-287), §4.6 Data Flow Diagram (lines 787-858) |
| **1.2** | Tool Call Extractor | §6.4 Tool Call Trace Extraction (lines 1284-1332), §11.6 Tool Call Evaluation Enhancement (lines 3341-3393) | §6.3 Trace Enrichment Pipeline (lines 1227-1284), §11.7 Combined Tool + Output Scoring (lines 3393-3457) |
| **1.3** | KEN-E Trace Enhancements | §10.2 Trace Instrumentation Enhancements (lines 2921-2998), §6.2 Trace Structure Requirements (lines 1191-1227) | §10.1 Agent Configuration Changes (lines 2825-2921), §6.3 Trace Enrichment (lines 1227-1284) |
| **1.4** | Enhanced Agent Config Schema | §4.2.1 agent_configs Collection (within §4.2), §4.2.2 agent_config_history Collection | §10.1 Agent Configuration Changes (lines 2825-2921), §8.2-8.3 Deployment Stages (lines 1950-2015) |
| **1.5** | Database Schema Setup | §4.2 Firestore Schema (lines 374-567), §4.3 BigQuery Schema (lines 567-722), §4.4 GCS Structure (lines 722-754) | §4.1 Storage Strategy Overview (lines 339-374), §4.6 Data Flow Diagram (lines 787-858) |
| **1.6** | Basic API Endpoints | §10.3 API Endpoints for Evaluation Framework (lines 2998-3041) | §3.3 Integration Points (lines 287-323), §9.9 Technical Implementation Notes (lines 2806-2821) |

### Release 2: Core Loop (Features 2.1 - 2.8)

| Feature | Feature Name | Primary Sections | Supporting Sections |
|---------|--------------|------------------|---------------------|
| **2.1** | Enhanced Evaluation UI | §5.4 Evaluation Interface Design (lines 990-1074), §9.3 Evaluation Queue View (lines 2418-2469) | §5.2 Evaluation Workflow (lines 879-900), §5.5 Evaluation Factor Management (lines 1074-1130) |
| **2.2** | Priority Queue System | §5.3 Queue Management System (lines 900-990) | §7.8 Human Feedback Request Generation (lines 1887-1940), §5.6 Bulk Evaluation Features (lines 1130-1142) |
| **2.3** | Dashboard View | §9.2 Dashboard View (lines 2355-2418) | §7.7 Automatic Issue Detection (lines 1833-1887), §9.1 Application Structure (lines 2323-2355) |
| **2.4** | Deployment Pipeline - Staging | §8.2-8.3 Deployment Stages (lines 1950-2015), §8.4 Deployment Workflow (lines 2015-2124) | §8.1 Deployment Philosophy (lines 1942-1950), §8.6 Cloud Build Integration (lines 2218-2266) |
| **2.5** | Version History & Rollback | §8.5 Rollback System (lines 2124-2218) | §4.2.2 agent_config_history Collection, §8.4 Deployment Workflow (lines 2015-2124) |
| **2.6** | Agent Detail View | §9.4 Agent Detail View (lines 2469-2537) | §9.7 Configuration Editor View (lines 2717-2789), §10.1 Agent Configuration Changes (lines 2825-2921) |
| **2.7** | Recommendation Review UI | §9.5 Recommendation Review View (lines 2537-2648) | §7.6 Recommendation Aggregation (lines 1748-1833), §9.6 Deployment Management View (lines 2648-2717) |
| **2.8** | Firestore-BigQuery Sync | §4.3 BigQuery Schema (lines 567-722), §4.6 Data Flow Diagram (lines 787-858) | §4.1 Storage Strategy Overview (lines 339-374) |

### Release 3: Automated Analysis (Features 3.1 - 3.8)

| Feature | Feature Name | Primary Sections | Supporting Sections |
|---------|--------------|------------------|---------------------|
| **3.1** | Alignment Analyzer | §7.2 Analysis Module: Alignment Analyzer (lines 1411-1515) | §7.1 Engine Overview (lines 1360-1411), §7.6 Recommendation Aggregation (lines 1748-1833) |
| **3.2** | Prompt Improvement Generator | §7.2 Alignment Analyzer (prompt improvement within), §7.6 Recommendation Aggregation (lines 1748-1833) | §7.1 Engine Overview (lines 1360-1411), §1.3 What the System Can Optimize (lines 59-80) |
| **3.3** | Recommendation Aggregator | §7.6 Recommendation Aggregation (lines 1748-1833) | §7.7 Automatic Issue Detection (lines 1833-1887), §9.5 Recommendation Review View (lines 2537-2648) |
| **3.4** | Pattern Detector | §7.3 Analysis Module: Pattern Detector (lines 1515-1591) | §7.1 Engine Overview (lines 1360-1411), §12 Human Edit Distance Tracking (lines 3457-3775) |
| **3.5** | Tool Usage Analyzer | §7.4 Analysis Module: Tool Usage Analyzer (lines 1591-1663) | §6.4 Tool Call Trace Extraction (lines 1284-1332), §11.6 Tool Call Evaluation Enhancement (lines 3341-3393) |
| **3.6** | Canary Deployment Support | §8.7 A/B Testing Infrastructure (lines 2266-2308), §8.2-8.3 Deployment Stages (lines 1950-2015) | §8.4 Deployment Workflow (lines 2015-2124), §3.7 Automated Monitoring |
| **3.7** | Automated Monitoring | §7.7 Automatic Issue Detection (lines 1833-1887), §8.7 A/B Testing Infrastructure (lines 2266-2308) | §9.2 Dashboard View (lines 2355-2418), §15.6 Benchmark Dashboard (lines 4929-4956) |
| **3.8** | Notification System | §8.8 Deployment Notifications (lines 2308-2321) | §7.7 Automatic Issue Detection (lines 1833-1887), §7.6 Recommendation Aggregation (lines 1748-1833) |

### Release 4: Advanced Intelligence (Features 4.1 - 4.8)

| Feature | Feature Name | Primary Sections | Supporting Sections |
|---------|--------------|------------------|---------------------|
| **4.1** | Configuration Optimizer | §7.5 Analysis Module: Configuration Optimizer (lines 1663-1748), §8.7 A/B Testing Infrastructure (lines 2266-2308) | §1.3 What the System Can Optimize (lines 59-80), §7.1 Engine Overview (lines 1360-1411) |
| **4.2** | Experiment Management UI | §8.7 A/B Testing Infrastructure (lines 2266-2308), §9.6 Deployment Management View (lines 2648-2717) | §7.5 Configuration Optimizer (lines 1663-1748) |
| **4.3** | Factor Suggestion System | §5.5 Evaluation Factor Management (lines 1074-1130), §11.3 Evaluation Factors by Output Category (lines 3156-3193) | §7.6 Recommendation Aggregation (lines 1748-1833) |
| **4.4** | Anomaly Detection | §7.7 Automatic Issue Detection (lines 1833-1887), §3.7 Automated Monitoring | §15.4 Account Percentile Ranking (lines 4772-4857), §7.3 Pattern Detector (lines 1515-1591) |
| **4.5** | Feedback Request Generator | §7.8 Human Feedback Request Generation (lines 1887-1940) | §5.3 Queue Management System (lines 900-990), §7.7 Automatic Issue Detection (lines 1833-1887) |
| **4.6** | Structural Issue Detection | §7.4 Tool Usage Analyzer (lines 1591-1663), §1.3 What the System Can Optimize - Recommendation-Only (lines 73-80) | §11.4 Agent-Specific Evaluation Considerations (lines 3193-3326), §13 Multi-Step Workflow Evaluation (lines 3775-4202) |
| **4.7** | Historical Trend Analysis | §15.6 Benchmark Dashboard (lines 4929-4956), §4.3 BigQuery Schema (lines 567-722) | §15.3 Aggregation Pipeline (lines 4668-4772), §9.2 Dashboard View (lines 2355-2418) |
| **4.8** | Multi-Provider LLM Support | §1.3 What the System Can Optimize (lines 59-80), §10.4 Environment Configuration (lines 3041-3069) | §7.5 Configuration Optimizer (lines 1663-1748) |

## Special Topic Sections

For stories that touch cross-cutting concerns, also read these sections:

| Topic | Relevant Sections |
|-------|-------------------|
| **Weave/W&B Integration** | §4.5 W&B Weave Data Model, §5.7 Integration with W&B Weave, §6 Trace Collection & W&B Integration |
| **Firestore Design** | §4.2 Firestore Schema, §4.1 Storage Strategy Overview |
| **Security & Auth** | §3.4 Security & Access Control |
| **KEN-E Integration** | §10 KEN-E Application Modifications |
| **Agentic Harness** | §11 Agentic Harness Integration |
| **Edit Distance Tracking** | §12 Human Edit Distance Tracking |
| **Multi-Step Workflows** | §13 Multi-Step Workflow Evaluation |
| **n8n Workflows** | §14 n8n Workflow Evaluation |
| **Cross-Account Features** | §15 Cross-Account Benchmarking |

## Quick Reference: Line Ranges by Section

| Section | Start Line | End Line |
|---------|------------|----------|
| §1 Executive Summary | 35 | 102 |
| §2 Vision & Objectives | 103 | 192 |
| §3 System Architecture | 193 | 336 |
| §4 Data Storage Design | 337 | 857 |
| §5 Human Feedback System | 858 | 1184 |
| §6 Trace Collection | 1185 | 1357 |
| §7 Analysis & Recommendation | 1358 | 1939 |
| §8 Deployment Pipeline | 1940 | 2320 |
| §9 User Interface Design | 2321 | 2820 |
| §10 KEN-E Modifications | 2821 | 3082 |
| §11 Agentic Harness | 3083 | 3456 |
| §12 Edit Distance Tracking | 3457 | 3774 |
| §13 Multi-Step Workflow | 3775 | 4201 |
| §14 n8n Workflow Evaluation | 4202 | 4586 |
| §15 Cross-Account Benchmarking | 4587 | 5045 |
| §16 Feature Roadmap | 5046 | 5287 |
| §17 Appendices | 5288 | EOF |

---

## Keyword Search Index

Use this index to find relevant sections when you know the concept but not the feature number.

### Data & Storage Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Firestore | §4.2 (374-567), §4.1 (339-374) |
| BigQuery | §4.3 (567-722), §2.8 Feature |
| GCS / Cloud Storage | §4.4 (722-754) |
| Schema | §4.2, §4.3, §4.5 |
| Collection | §4.2 (Firestore collections) |
| Data model | §4.2, §4.3, §4.5, §4.6 |
| Migration | §4.2, §4.3 |

### Weave & W&B Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Weave | §4.5 (754-787), §5.7 (1142-1185), §6 (1185-1357) |
| W&B / Weights & Biases | §4.5, §5.7, §6 |
| Trace | §6 (1185-1357), §10.2 (2921-2998) |
| Scorer | §7.2 (1411-1515), §3.1-3.2 Features |
| Evaluation | §5 (858-1184), §4.5, §7.2 |
| Dataset | §4.5, §6.5 (1332-1347) |

### UI & Frontend Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Dashboard | §9.2 (2355-2418), §2.3 Feature |
| Evaluation UI | §5.4 (990-1074), §9.3 (2418-2469), §2.1 Feature |
| Queue | §5.3 (900-990), §9.3, §2.2 Feature |
| Form | §5.4, §9.3 |
| Component | §9.8 (2789-2806) |
| View | §9.2-9.7 |
| Agent detail | §9.4 (2469-2537), §2.6 Feature |
| Recommendation review | §9.5 (2537-2648), §2.7 Feature |
| Deployment management | §9.6 (2648-2717) |
| Configuration editor | §9.7 (2717-2789) |

### Analysis & Recommendation Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Alignment | §7.2 (1411-1515), §3.1 Feature |
| Prompt improvement | §7.2, §3.2 Feature |
| Pattern detection | §7.3 (1515-1591), §3.4 Feature |
| Tool usage | §7.4 (1591-1663), §3.5 Feature |
| Configuration optimizer | §7.5 (1663-1748), §4.1 Feature |
| Recommendation | §7.6 (1748-1833), §3.3 Feature |
| Anomaly | §7.7 (1833-1887), §4.4 Feature |
| Notification | §8.8 (2308-2321), §3.8 Feature |

### Deployment Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Deployment | §8 (1940-2320) |
| Staging | §8.2-8.3 (1950-2015), §2.4 Feature |
| Canary | §8.7 (2266-2308), §3.6 Feature |
| Rollback | §8.5 (2124-2218), §2.5 Feature |
| A/B testing | §8.7, §4.1-4.2 Features |
| Version | §8.5, §4.2.2 |
| Cloud Build | §8.6 (2218-2266) |

### KEN-E Integration Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Agent config | §10.1 (2825-2921), §4.2.1, §1.4 Feature |
| Trace instrumentation | §10.2 (2921-2998), §1.3 Feature |
| API endpoint | §10.3 (2998-3041), §1.6 Feature |
| Environment | §10.4 (3041-3069) |

### Advanced Features Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Agentic harness | §11 (3083-3456) |
| Edit distance | §12 (3457-3774) |
| Multi-step workflow | §13 (3775-4201) |
| n8n | §14 (4202-4586) |
| Cross-account | §15 (4587-5045) |
| Benchmark | §15.4-15.6 |
| Privacy | §15.7 (4956-5015) |

### Evaluation & Scoring Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Factor | §5.5 (1074-1130), §11.3 (3156-3193), §4.3 Feature |
| Rubric | §5.5, §4.3 Feature |
| Score | §5.4, §7.2 |
| Human evaluation | §5 (858-1184), §4.2.3 |
| LLM evaluation | §7.2, §4.5 |
| Agreement | §7.2, §1.1 Feature |
| Quality | §7.7, §15.5 |

### Security & Access Keywords

| Keyword | Relevant Sections |
|---------|-------------------|
| Security | §3.4 (323-337), §15.7 |
| Access control | §3.4 |
| Authentication | §3.4 |
| Privacy | §15.7 (4956-5015) |
| Anonymization | §15.2 (4599-4668) |

---

## How to Use the Keyword Index

1. **Identify the concept** you're working with (e.g., "Firestore query")
2. **Find relevant keywords** in the index (e.g., "Firestore", "Schema", "Collection")
3. **Note the section numbers** and line ranges
4. **Read those sections** from `docs/MER-E_Design.md`

### Example Usage

**Task:** Implement a function to fetch human evaluations from Firestore

**Keywords to search:** Firestore, human evaluation, schema

**Relevant sections:**
- §4.2 Firestore Schema (lines 374-567) - for collection structure
- §5 Human Feedback System (lines 858-1184) - for evaluation workflow
- §4.2.3 human_evaluations Collection - for specific fields

**Read command:**
```
Read docs/MER-E_Design.md lines 374-567  # Firestore schema
Read docs/MER-E_Design.md lines 858-990  # Human feedback overview
```

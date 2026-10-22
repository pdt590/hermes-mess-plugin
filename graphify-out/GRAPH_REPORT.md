# Graph Report - messenger  (2026-10-22)

## Corpus Check
- Corpus is ~11,726 words - fits in a single context window. You may not need a graph.

## Summary
- 210 nodes · 374 edges · 14 communities (11 shown, 3 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 48 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Installer and Test Runtime
- ManyChat Client and Retries
- Durable Inbox and Recovery
- Gateway Processing Lifecycle
- Webhook Ingress and Storage
- Installation and Architecture
- Platform Registration
- Validation and Ingress Tests
- Gateway Integration Tests
- Messenger Automation Contract
- Credentials and Authorization
- Graph Navigation Rules
- Single Fanpage Scope

## God Nodes (most connected - your core abstractions)
1. `Inbox` - 23 edges
2. `MessengerAdapter` - 15 edges
3. `configure()` - 15 edges
4. `Settings` - 10 edges
5. `ManyChatClient` - 9 edges
6. `test_recovery_and_disconnect_preserves_accepted_message()` - 9 edges
7. `test_persistence_dedup_conflict_and_no_id()` - 9 edges
8. `test_capacity_duplicate_and_prune()` - 9 edges
9. `create_app()` - 9 edges
10. `make_client()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Asynchronous in-process platform adapter` --rationale_for--> `MessengerAdapter`  [EXTRACTED]
  system-design/implementation-spec.md → adapter.py
- `Preserve existing environment and YAML settings` --rationale_for--> `configure()`  [EXTRACTED]
  INSTALLATION.md → scripts/install.py
- `Durable SQLite inbox with FIFO worker` --references--> `Inbox`  [EXTRACTED]
  system-design/implementation-spec.md → store.py
- `client()` --uses--> `Settings`  [INFERRED]
  tests/test_webhook.py → config.py
- `2000 UTF-16 unit outbound text chunks` --references--> `text_chunks()`  [INFERRED]
  README.md → manychat.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Asynchronous Messenger processing and response flow** — system_design_architecture_messenger, readme_manychat_automation, readme_webhook_contract, system_design_implementation_spec_durable_inbox, adapter_messengeradapter, manychat_manychatclient_send_text [EXTRACTED 1.00]
- **Uncertain delivery and single retry ownership** — readme_delivery_uncertainty, readme_retry_policy, system_design_progress_retry_owner, adapter_messengeradapter_send_retry_is_final, adapter_messengeradapter_record_delivery_obligation [EXTRACTED 1.00]
- **Cross-platform installation and configuration preservation** — installation_guide, setup_ps1_runtime_discovery, setup_sh_setup, scripts_install_ensure_dependencies, scripts_install_configure, installation_configuration_merge [EXTRACTED 1.00]

## Communities (14 total, 3 thin omitted)

### Community 0 - "Installer and Test Runtime"
Cohesion: 0.08
Nodes (15): Real Facebook and ManyChat end-to-end remains unverified, _atomic_write(), _config_content(), configure(), default_home(), ensure_dependencies(), main(), _mapping() (+7 more)

### Community 1 - "ManyChat Client and Retries"
Cohesion: 0.10
Nodes (13): Delivery, ManyChatClient, retry_delay(), text_chunks(), 2000 UTF-16 unit outbound text chunks, make_client(), test_failures_are_not_retried_or_leaked(), test_fragmented_json_success() (+5 more)

### Community 2 - "Durable Inbox and Recovery"
Cohesion: 0.14
Nodes (10): Pending processing complete failed states, Conflict, Full, Inbox, Receipt, Durable SQLite inbox with FIFO worker, test_recovery_and_disconnect_preserves_accepted_message(), test_capacity_duplicate_and_prune() (+2 more)

### Community 3 - "Gateway Processing Lifecycle"
Cohesion: 0.13
Nodes (4): MessengerAdapter, integer(), number(), read()

### Community 4 - "Webhook Ingress and Storage"
Cohesion: 0.14
Nodes (4): _env_content(), create_app(), receive(), normalize_payload()

### Community 5 - "Installation and Architecture"
Cohesion: 0.17
Nodes (13): Windows and Linux installation guide, Hermes Python runtime discovery, Facebook Messenger Hermes platform plugin, aiohttp runtime dependency >=3.9,<4, pytest pytest-asyncio and ruamel.yaml development dependencies, Explicit HermesPython and HermesHome overrides, PowerShell Hermes Python selection and installer invocation, setup.sh script (+5 more)

### Community 6 - "Platform Registration"
Cohesion: 0.20
Nodes (5): check_requirements(), _env_enablement(), register(), validate_config(), register()

### Community 7 - "Validation and Ingress Tests"
Cohesion: 0.18
Nodes (4): Settings, plugin(), test_settings_validate_and_hide_secrets(), test_validation()

### Community 8 - "Gateway Integration Tests"
Cohesion: 0.23
Nodes (9): make_adapter(), test_bind_failure_cleans_resources(), test_gateway_fifo_completion_and_routing(), api(), handler(), test_register_platform(), test_send_failure_no_gateway_retry(), test_uncertain_final_not_added_to_gateway_boot_redelivery() (+1 more)

### Community 9 - "Messenger Automation Contract"
Cohesion: 0.33
Nodes (6): ManyChat contact ID identity, HTTPS tunnel or reverse proxy for webhook, ManyChat External Request Automation, Authenticated JSON webhook contract, Hermes agent owns AI tools and conversation context, Facebook Messenger customer channel

### Community 10 - "Credentials and Authorization"
Cohesion: 0.50
Nodes (4): Explicit contact authorization, Messenger platform manifest version 0.1.0, Optional listener storage and timeout settings, ManyChat token and webhook secret

## Knowledge Gaps
- **13 isolated node(s):** `Graphify repository navigation rules`, `Explicit contact authorization`, `Pending processing complete failed states`, `2000 UTF-16 unit outbound text chunks`, `Real Facebook and ManyChat end-to-end remains unverified` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 75 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Inbox` connect `Durable Inbox and Recovery` to `Gateway Processing Lifecycle`, `Webhook Ingress and Storage`, `Platform Registration`, `Validation and Ingress Tests`, `Gateway Integration Tests`?**
  _High betweenness centrality (0.179) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Inbox` (e.g. with `MessengerAdapter` and `client()`) actually correct?**
  _`Inbox` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Graphify repository navigation rules`, `Explicit contact authorization`, `Pending processing complete failed states` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Installer and Test Runtime` be split into smaller, more focused modules?**
  _Cohesion score 0.08362369337979095 - nodes in this community are weakly interconnected._
- **Why does `MessengerAdapter` connect `Gateway Processing Lifecycle` to `ManyChat Client and Retries`, `Durable Inbox and Recovery`, `Installation and Architecture`, `Platform Registration`, `Validation and Ingress Tests`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `MessengerAdapter` (e.g. with `Settings` and `ManyChatClient`) actually correct?**
  _`MessengerAdapter` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `ManyChat Client and Retries` be split into smaller, more focused modules?**
  _Cohesion score 0.10227272727272728 - nodes in this community are weakly interconnected._
## Extraction Audit Notes

- Full local build: 29 detected files, approximately 11,726 words; code structural extraction plus 10 documents and targeted PowerShell semantic coverage. No private credentials were read.
- PowerShell setup.ps1 produced no AST symbols; its installer/runtime-selection behavior was added by semantic extraction, separately marked with semantic provenance.
- Graph health: 89 raw AST edges have undeclared endpoints, chiefly external/import references. The builder synthesizes additional endpoint nodes; this does not prove their implementation was analyzed.
- Undirected graph conversion merges 16 same-endpoint edge variants. Raw extraction and integrity details are retained in extraction_audit.json and graph_health.json, including the original distinct relations.
- Semantic agent token usage is not exposed by the host collaboration tool. Numeric zero placeholders in generated token tables/cost.json mean UNKNOWN, not zero token consumption. No external LLM API was called by this pipeline; no monetary API cost was measured.
- graphify-out/ was written into the working tree. Unless ignored it appears in git status; choose which graph artifacts to commit or add the directory to .gitignore. See https://docs.graphify.com/guides/team-workflows.

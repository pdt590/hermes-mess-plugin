# Graph Report - messenger  (2026-10-22)

## Corpus Check
- 31 files · ~14,030 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .example 1, (none) 1, .ini 1)

## Summary
- 253 nodes · 481 edges · 17 communities (10 shown, 7 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 47 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- install.py
- ManyChat Client and Retries
- Durable Inbox and Recovery
- MessengerAdapter
- test_native_webhook.py
- Installation and Architecture
- uninstall.sh script
- adapter.py
- Gateway Integration Tests
- MessengerIngressAdapter
- Credentials and Authorization
- Graph Navigation Rules
- Single Fanpage Scope
- pathlib
- test_install.py

## God Nodes (most connected - your core abstractions)
1. `configure()` - 28 edges
2. `uninstall()` - 22 edges
3. `Inbox` - 21 edges
4. `MessengerAdapter` - 15 edges
5. `MessengerIngressAdapter` - 11 edges
6. `ManyChatClient` - 9 edges
7. `test_recovery_and_disconnect_preserves_accepted_message()` - 9 edges
8. `test_persistence_dedup_conflict_and_no_id()` - 9 edges
9. `test_capacity_duplicate_and_prune()` - 9 edges
10. `Settings` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Preserve existing environment and YAML settings` --rationale_for--> `configure()`  [EXTRACTED]
  INSTALLATION.md → scripts/install.py
- `Installer follow-up records 45 passing tests` --references--> `configure()`  [EXTRACTED]
  system-design/progress.md → scripts/install.py
- `Durable SQLite inbox with FIFO worker` --references--> `Inbox`  [EXTRACTED]
  system-design/implementation-spec.md → store.py
- `Asynchronous in-process platform adapter` --rationale_for--> `MessengerAdapter`  [EXTRACTED]
  system-design/implementation-spec.md → adapter.py
- `2000 UTF-16 unit outbound text chunks` --references--> `text_chunks()`  [INFERRED]
  README.md → manychat.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Asynchronous Messenger processing and response flow** — system_design_architecture_messenger, readme_manychat_automation, readme_webhook_contract, system_design_implementation_spec_durable_inbox, adapter_messengeradapter, manychat_manychatclient_send_text [EXTRACTED 1.00]
- **Uncertain delivery and single retry ownership** — readme_delivery_uncertainty, readme_retry_policy, system_design_progress_retry_owner, adapter_messengeradapter_send_retry_is_final, adapter_messengeradapter_record_delivery_obligation [EXTRACTED 1.00]
- **Cross-platform installation and configuration preservation** — installation_guide, setup_ps1_runtime_discovery, setup_sh_setup, scripts_install_ensure_dependencies, scripts_install_configure, installation_configuration_merge [EXTRACTED 1.00]

## Communities (17 total, 7 thin omitted)

### Community 0 - "install.py"
Cohesion: 0.12
Nodes (24): _atomic_write(), commit_changes(), _config_content(), configure(), _env_content(), _mapping(), parse_env(), read_template() (+16 more)

### Community 1 - "ManyChat Client and Retries"
Cohesion: 0.11
Nodes (13): Delivery, ManyChatClient, retry_delay(), text_chunks(), 2000 UTF-16 unit outbound text chunks, make_client(), test_failures_are_not_retried_or_leaked(), test_fragmented_json_success() (+5 more)

### Community 2 - "Durable Inbox and Recovery"
Cohesion: 0.13
Nodes (8): Pending processing complete failed states, Conflict, Full, Inbox, Receipt, Durable SQLite inbox with FIFO worker, test_capacity_duplicate_and_prune(), test_persistence_dedup_conflict_and_no_id()

### Community 4 - "test_native_webhook.py"
Cohesion: 0.26
Nodes (5): native(), signed(), test_native_auth_queue_and_contact_session(), test_native_static_token_echo_and_dedup(), test_native_tampered_stale_and_legacy_secret_rejected()

### Community 5 - "Installation and Architecture"
Cohesion: 0.18
Nodes (14): Windows and Linux installation guide, Hermes Python runtime discovery, Facebook Messenger Hermes platform plugin, aiohttp runtime dependency >=3.9,<4, pytest pytest-asyncio and ruamel.yaml development dependencies, ensure_dependencies(), main(), Explicit HermesPython and HermesHome overrides (+6 more)

### Community 7 - "adapter.py"
Cohesion: 0.13
Nodes (10): check_requirements(), _env_enablement(), register(), validate_config(), Settings, integer(), number(), read() (+2 more)

### Community 8 - "Gateway Integration Tests"
Cohesion: 0.21
Nodes (10): make_adapter(), test_gateway_fifo_completion_and_routing(), api(), handler(), test_no_plugin_listener_and_database_failure_cleans_resources(), test_recovery_and_disconnect_preserves_accepted_message(), test_register_platform(), test_send_failure_no_gateway_retry() (+2 more)

### Community 9 - "MessengerIngressAdapter"
Cohesion: 0.09
Nodes (10): MessengerIngressAdapter, ManyChat contact ID identity, HTTPS tunnel or reverse proxy for webhook, ManyChat External Request Automation, Authenticated JSON webhook contract, Hermes agent owns AI tools and conversation context, Facebook Messenger customer channel, test_payload_validation() (+2 more)

### Community 10 - "Credentials and Authorization"
Cohesion: 0.50
Nodes (4): Explicit contact authorization, Messenger platform manifest version 0.1.0, Optional listener storage and timeout settings, ManyChat token and webhook secret

### Community 16 - "test_install.py"
Cohesion: 0.14
Nodes (10): Real Facebook and ManyChat end-to-end remains unverified, default_home(), Installer follow-up records 45 passing tests, template(), test_dependencies_install_only_missing(), test_home_detection(), test_install_merges_without_overwriting_unrelated_settings(), test_invalid_config_never_modifies_files() (+2 more)

## Knowledge Gaps
- **13 isolated node(s):** `Real Facebook and ManyChat end-to-end remains unverified`, `2000 UTF-16 unit outbound text chunks`, `Explicit contact authorization`, `ManyChat token and webhook secret`, `Graphify repository navigation rules` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 84 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MessengerAdapter` connect `MessengerAdapter` to `ManyChat Client and Retries`, `Durable Inbox and Recovery`, `adapter.py`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `MessengerAdapter` (e.g. with `Settings` and `ManyChatClient`) actually correct?**
  _`MessengerAdapter` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Real Facebook and ManyChat end-to-end remains unverified`, `2000 UTF-16 unit outbound text chunks`, `Explicit contact authorization` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `install.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12435897435897436 - nodes in this community are weakly interconnected._
- **Why does `Inbox` connect `Durable Inbox and Recovery` to `Gateway Integration Tests`, `MessengerAdapter`, `adapter.py`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Should `ManyChat Client and Retries` be split into smaller, more focused modules?**
  _Cohesion score 0.10967741935483871 - nodes in this community are weakly interconnected._
- **Why does `configure()` connect `install.py` to `test_install.py`, `Installation and Architecture`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
# Execution ledger: system-design/implementation-plan.md

User approved spec, plan and inline execution. No commits or gateway config mutations.

Pre-flight: tasks 2 and 4 consume Inbox; task 4 consumes ManyChatClient and Settings. Interfaces compatible; receipt IDs stay separate from upstream message IDs.

Ruling: implement in the requested workspace because this is the plugin install target; Git metadata is read-only under sandbox, so branch creation failed without changing refs. No global Git exception written.

Ruling: use `on_processing_complete(event, outcome)` to release the FIFO worker. `handle_message()` returns before completion in installed Hermes.

Ruling: only retry explicit HTTP 429 rejections; 5xx/timeouts can follow accepted sends, so return an uncertain failure rather than risking duplicates. Crash recovery remains at-least-once.

Task 1: complete; initial 3 tests failed on missing modules, then passed.
Task 2: complete; 9 HTTP tests failed before implementation, then passed.
Task 3: complete; 7 client tests failed before implementation, then passed. Swagger fetched from official compileJson Page_API endpoint, 2026-10-22.
Task 4: in progress; real Hermes base adapter used. Integration test caught base-class plain-text fallback replaying a failed send despite retryable=False. Override `_send_retry_is_final` to make the client the sole retry owner; regression verifies only one upstream call for HTTP 503.

Independent review identified generic gateway delivery ledger boot replay of uncertain/partial failures. Regression through real `send_final_ledgered()` + `sweep_recoverable()` failed with one recoverable duplicate. Ruling: override `_record_delivery_obligation()` for Messenger, relying on the plugin inbox recovery rather than two independent durable retry owners. No fake delivered status written to Hermes ledger.

Registry integration test caught credentials-in-check_fn blocking YAML-only configuration. Keep dependency probe independent of credentials; validate credentials via Settings/validate_config and use scoped secrets only for env auto-enablement.

Ruling: watchdog failure pauses ingress (503) and leaves the current row recoverable; never start another turn over a stuck worker. Operators must inspect upstream delivery before recovery, because replay can duplicate a response.

Task 4: complete. PluginContext and PluginManager load smoke tests, registry adapter creation, actual BasePlatformAdapter processing lifecycle, routing, watchdog, shutdown/recovery, bind failure and outgoing ledger regression all pass.

Task 5: complete. README and .env.example include installation, actual platforms config layout, ManyChat mapping, authorization, HTTPS, retries/recovery and operational limitations. `scripts/test_with_hermes.py` uses a temporary Hermes home and fake ManyChat HTTP servers; no active gateway/profile is changed.

Final verification: `../../hermes-agent/venv/Scripts/python scripts/test_with_hermes.py ../../hermes-agent` -> 33 passed, no skips, 2026-10-22. `python -m compileall -q` over plugin, scripts and tests -> exit 0. `git diff --check` -> exit 0.

Official Hermes `validate_plugin_dir(Path.cwd())` -> ok=true, 15 checks passed, warnings=[], security scan safe; register() capability probe ran in isolation. Platform intentionally runs in-process on the gateway event loop.

Independent final review found one important delivery-ledger replay issue; red/green regression added and fix reviewed. Follow-up reviewer confirmed no remaining important defects. Review did not independently rerun suite; root agent ran full suite after fixes.

Not exercised: real Facebook Page / ManyChat Automation / API credential / actual model response. Automated integration substitutes only the agent handler and external ManyChat HTTP endpoint while retaining actual Hermes adapter and plugin manager. No deployment, plugin enablement, gateway restart, commit or push performed.

## Installer and wildcard-host follow-up

Added `setup.ps1` (Windows), POSIX `setup.sh` (Linux/Git Bash), shared `scripts/install.py`. Both launchers require/use Hermes Python; check aiohttp and YAML editor imports, pip-install only missing prerequisites, merge missing .env/config keys, preserve existing values including YAML-only values, back up changed files and write atomically with rollback on write failure. Existing configuration is never printed. Installer is run by the operator; only temporary homes were configured during development.

All old numeric loopback literals removed from maintained project files (excluded .git, .venv and caches); bind addresses use wildcard IPv4. Client test URLs and README request use localhost, because wildcard bind addresses are not portable connection destinations.

Verification: 45 tests passed with Hermes runtime; 12 installer tests include idempotency, backups, malformed YAML, YAML-only values and rollback. Both PowerShell and Git Bash launchers executed against temporary homes twice; second run made no changes. Shell syntax check and compileall passed; native Linux execution was not available. Official Hermes validator again passed all 15 checks with no warnings/security findings. Active Hermes home/gateway were not modified or restarted.

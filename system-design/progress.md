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

## Native Hermes webhook migration (current architecture)

User explicitly selected the built-in Hermes webhook at port 8644. Messenger no longer starts an aiohttp server or validates an X-Webhook-Secret header. Native Hermes route `manychat` authenticates via its existing HMAC V2 verifier or supported X-Gitlab-Token token mechanism, filters echoes, and uses `deliver_only` to forward text/contact/message ID to the internal `messenger_ingress` platform. The bridge commits the existing SQLite inbox; Messenger's worker remains the sole producer of customer Agent turns, preserving contact sessions, authorization and FIFO recovery. No Hermes core changes or runtime method replacements.

Manifest 0.2.0 uses standalone loading to eagerly register both platform names before config parsing. Installer migrates obsolete listener variables, configures built-in webhook port 8644 and a per-route secret, preserving unrelated routes/global secret. The supplied real secret is stored only in ignored local .env, not documentation or public code; setup reads it when the operator applies migration. Secret and port synchronization are covered by tests.

Runtime caveat: built-in deliver_only records a delivery ID before downstream handoff. Clients should omit X-Request-ID (Hermes generates a fresh ID) or generate a new one per HTTP attempt; payload message_id remains stable for plugin deduplication. Native `200/delivered` acknowledges inbox persistence, not AI completion. Downstream bridge failure returns 502, not the old standalone listener's 503/409 statuses.

Verification: 45 tests passed, including an actual native WebhookAdapter listener on an ephemeral test port, signed HMAC V2, tampered/stale/missing auth, static-token auth, echo filtering, durable dedup, per-contact Agent events, completion/recovery, installer migration and idempotency. Official Hermes validator passed 15 checks without warnings. Windows setup run twice against a temporary home verified port 8644 and private secret equality without printing it. Active Hermes profile and gateway were not modified/restarted; real ManyChat/Fanpage still untested.

## Template-only setup and uninstall

Setup now parses only .env.example for application configuration, without interpolation, process-environment overrides, local .env fallback or generated secret values. Matching keys in Hermes .env are synchronized to the template; unrelated variables remain untouched. OS environment still locates the Hermes home/Python runtime. python-dotenv parses quoted/multiline values without executing shell content.

Added uninstall.ps1, uninstall.sh and scripts/uninstall.py. Uninstall removes Messenger configuration/owned route/env variables and archives the verified installed plugin directory outside discovery into plugin-backups. Database and shared dependencies are retained. Setup records non-secret ownership metadata in plugin-data/messenger/setup-state.json so uninstall can restore previous shared webhook fields/WEBHOOK_PORT while preserving later operator edits and other routes. Config changes are backed up; archive failure rolls configuration back. Paths are resolved and checked to stay inside the selected Hermes home before any directory move; no recursive deletion is performed.

Verification: 54 tests passed with Hermes runtime, including template-only values, no variable interpolation, idempotency, unrelated-settings preservation, uninstall/shared-field restoration, refusing another plugin, rollback on archive failure, and Windows locked-root archival fallback. PowerShell setup/setup/uninstall/uninstall completed against a temporary Hermes home; second runs are idempotent. Running uninstall from inside a temporary installed plugin also succeeded after adding the locked-directory fallback; readback confirmed no manifest remained in discovery and the archive contained the source. Shell setup/uninstall executed under Git Bash and POSIX syntax checks passed; native Ubuntu was not available. No uninstall or setup was applied to the active Hermes profile.

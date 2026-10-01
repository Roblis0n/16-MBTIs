# Host compatibility evidence

Checked 2026-09-30. Documentation and observed execution remain separate.

- Portable root manifest is documented with Agent Plugins 1.0.0 schema; compatibility `.codex-plugin/plugin.json` remains supported. Inline `extensions.com.openai` replaces the compatibility overlay, not a merge. [Official packaging](https://developers.openai.com/plugins/build/plugins)
- Skills require `name` and `description` in SKILL.md and load supporting scripts/references progressively. This does not prove every plugin entry was invoked. [Official skills](https://learn.chatgpt.com/docs/build-skills)
- Actual collaboration schema exposes spawn_agent, followup_task, send_message, interrupt_agent, list_agents and wait_agent; fork_turns accepts none/all/positive integer. No close tool is exposed. [Related official multi-agent documentation](https://developers.openai.com/api/docs/guides/responses-multi-agent)
- CODEX_HOME relocation is documented; isolated HOME/CODEX_HOME and an allowlisted credential-free environment were used for CLI probes. [Official environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables)

## Observed scope

Linux Python helper and Codex CLI 0.159.0-alpha.7 exist. Baseline0.4.0 local marketplace registration, install/list and uninstall/list succeeded. Entry invocation failed before model startup because the sandbox helper required a user-owned mode0700 app-server socket directory. No security setting or shared socket permissions were changed, no credentials copied, no new login requested, and no sandbox bypass used. See reports/one-shot/host-cli-*.json.

Final0030.5.0 package registration, installation and uninstall also succeeded; its installed entry startup remains blocked. Exact archive hash and receipts are in reports/one-shot/host-cli-final003-install.json. Windows/macOS/desktop/IDE/Claude actual-host tests remain not_run. Native worker use is separate from plugin installation and cannot promote static_candidate to host_candidate. No effectiveness or calibration claim is supported.

## Known discrepancies

The local plugin scaffold skill creates compatibility manifests; current official docs recommend portable roots and support compatibility fallbacks. Build both from one source when needed, respect documented precedence, and verify actual client behavior rather than rename files.

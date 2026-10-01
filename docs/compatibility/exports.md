# Experimental standalone and Claude exports

Codex plugin remains the main product. Both exporters consume the verified generated core package, never a second maintained persona/runtime tree. Each of eight skills includes its own scripts, resources, license and provenance. The exporter records core source hashes, source build hash, exporter version and output file hashes. Relative-path tests are local synthetic checks, not host installation evidence.

From repository root, after the core build:

- python -B -m tools.exporters standalone plugins/16-minds dist/standalone
- python -B -m tools.exporters claude plugins/16-minds dist/claude

An existing destination is always refused, with existing file names reported; no user skill is overwritten. Inspect differences and choose a new staging destination. This exports only: no global registration or installation is attempted. Single skills may be copied independently for inspection.

Both targets: status experimental_exporter; target version unknown; host permissions unknown; native delegation unknown; isolation unknown; token observability unknown; real install, eight-entry smoke, pair self-history behavior and uninstall all not_run. Claude gets a minimal experimental .claude-plugin identity generated from the same core identity. Common workflow instructions are unchanged, so the exporter does not revive a separate historical Task protocol. Actual host semantics must be checked on a user-specified version before claiming compatibility.

Linux local resource isolation is tested. Windows, macOS, IDE and Claude host integration remain not_run. No cloud account, subscription or API dependency is added to the stable plugin.

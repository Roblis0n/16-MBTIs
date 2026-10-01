# 16 Minds · 16-MBTIs

[简体中文](README.md) · [MIT License](LICENSE) · [Changelog](CHANGELOG.md)

**Examine one question through different perspectives.** 16 Minds is a Codex plugin that uses sixteen MBTI-inspired role designs for analysis, discussion, writing and decision support. Choose one perspective, compare several, or select an exact roster for your task.

Version **0.5.0**, release level **`static_candidate`**, business protocol **1.0.0**. These roles are creative perspective and voice designs, not psychological assessments, human participants or independent external evidence. This community project is not affiliated with OpenAI, Anthropic or the official MBTI organization.

## Eight skills

| Skill | Purpose |
| --- | --- |
| `minds-one` | Analyze with one specified perspective. |
| `minds` | Analyze with multiple perspectives and synthesize findings. |
| `minds-pair` | Discuss shared material through two perspectives. |
| `minds-cast` | Select an exact number of roles for a task. |
| `minds-write` | Write or rewrite while preserving supplied facts and constraints. |
| `minds-decide` | Evaluate options against objectives and hard constraints. |
| `minds-vote` | Count synthetic ballots for a frozen proposal version. |
| `minds-ask` | Ask clarifying questions or conduct a one-question-at-a-time interview. |

The sixteen roles are INTJ, INTP, ENTJ, ENTP, INFJ, INFP, ENFJ, ENFP, ISTJ, ISFJ, ESTJ, ESFJ, ISTP, ISFP, ESTP and ESFP. Multiple-role workflows default to four roles and support 1–16; pair uses exactly two. Light, middle and heavy modes allow at most one, two and three rounds, with retries sharing the original budget.

Optional experimental profiles include code review, premortem, decision checks, research feasibility, journal, recheck, course papers, event plans and technical proposals. Profiles are off by default and do not grant tool permissions.

## Install in Codex

Use a plugin-capable Codex client and **Python 3.11+**. The helper uses only the Python standard library. No extra model SDK or separate model API key is required by the plugin; content generation uses the host's existing model access.

This repository includes the generated `plugins/16-minds/` package and its `.agents/plugins/marketplace.json` catalog.

If your Codex CLI supports plugin marketplaces:

```text
codex plugin marketplace add Roblis0n/16-MBTIs --ref main
```

In the desktop plugin directory, choose **16 Minds Local**, install **16 Minds**, and select a skill in a new chat. Adding a marketplace and installing a plugin are separate steps. The catalog name is `16minds-local`; the plugin identity is `16-minds@16minds-local`. Check the source of an existing installation with the same name before proceeding.

Alternatively, clone the repository and add it as a local marketplace:

```text
git clone https://github.com/Roblis0n/16-MBTIs.git
cd 16-MBTIs
codex plugin marketplace add .
```

Follow the same desktop installation steps. See [official plugin packaging documentation](https://developers.openai.com/plugins/build/plugins) for the supported marketplace format. Client versions and host capabilities affect availability; installation alone does not establish complete workflow support.

## Example

Select the `minds` skill and supply your material:

```text
Use 16 Minds with four perspectives to review the following research plan.
Identify assumptions, missing resources and likely failure points.
Use only the supplied material. Do not browse or save records.
Preserve disagreement and distinguish facts, interpretations and hypotheses.

[Paste the plan here]
```

These are host requests. Legacy slash names are parser aliases, not guaranteed client command registrations.

## Execution, privacy and limitations

The host model generates content and performs actual tool calls. Python helpers validate requests, rosters, budgets, state transitions, evidence references, ballots and text invariants. They do not generate role answers or call model APIs. A prepared run is not a completed run.

Independent role execution requires actual host delegation and isolation. Unsupported capabilities are disclosed or refused. Simulating roles in one context requires explicit permission and disclosure. Synthetic votes are not surveys of real people.

Persistence, browsing and additional model calls default off. There is no telemetry, cloud synchronization or background service; the host still processes chat context. Secure persistence currently requires POSIX filesystem capabilities and explicitly refuses writes on Windows.

The original 0.5.0 package has Windows installation and enablement records, but complete eight-skill model execution has not passed target-host acceptance. Historical Windows full regression had failures and errors. Linux isolated installation and removal succeeded, while model startup was blocked by host sandbox conditions. These historical results do not certify this repository's rebuilt package.

Role selection remains uncalibrated. Public synthetic tasks are not an independent holdout study, and no superiority over a single-model answer is claimed. Standalone and Claude exports are experimental and require separate host validation.

The repository includes maintainable source, tests, public synthetic fixtures and the installable plugin. Old source snapshots, planning archives, machine installation logs and historical model sessions remain in the original local handoff archive.

## Development

Maintain source files and rebuild generated plugin files:

```text
python -B tools/minds_cli.py help
python -B tools/minds_cli.py version
python -B tools/build.py
python -B tools/build.py --check
python -B -m unittest tests.unit.test_build tests.unit.test_cli -v
```

The build also creates `dist/16-minds-0.5.0-static_candidate.zip`. Existing generated files are checked before replacement. Full regression is available through `python -B tools/check.py --label a-new-unique-label`; use Python UTF-8 mode on Windows. POSIX storage tests currently have known Windows failures.

Source assets live in `source/`, standard-library helpers in `runtime/minds/`, installable files in `plugins/16-minds/`, and tests in `tests/`. Evaluation and experiment protocols live in `evaluation/` and `experiments/`.

Read the [execution protocol](source/references/protocol.md), [development status](docs/当前开发状态.md), [installation and rollback notes](docs/install/README.md), [export notes](docs/compatibility/exports.md), and [security boundary](SECURITY.md).

## License and attribution

MIT. Original author **yukurash** retains the original copyright and attribution. This repository maintains the Codex migration. See [LICENSE](LICENSE), [ATTRIBUTION.md](ATTRIBUTION.md) and [persona provenance](source/plugin/persona-provenance.json).

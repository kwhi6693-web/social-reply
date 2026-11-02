# 💬 Social Reply

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

> Express what you mean. Send a reply that sounds like you.

[![Agent Skill](https://img.shields.io/badge/Type-Agent%20Skill-3f4856?style=flat-square)](SKILL.md)
[![Version](https://img.shields.io/badge/Version-2.0.2-0e7490?style=flat-square)](CHANGELOG.md)
[![Validation](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-2f855a?style=flat-square)](LICENSE)
[![Reply](https://img.shields.io/badge/Reply-One%20best%20reply-7c3aed?style=flat-square)](SKILL.md)
[![Memory](https://img.shields.io/badge/Memory-Private%20by%20design-0e7490?style=flat-square)](references/profile-memory.md)

**Go to:** [Start](#-quick-start) · [Install](#-installation-and-data-packages) · [Features](#-feature-map) · [Validation](#-validation-and-compatibility) · [Maintenance](#-maintenance)

## 🎯 One reply, just right

Not sure how to reply? Share the chat text or a screenshot. Social Reply considers the actual context, your intentions, and your expression preferences, then gives you **one natural reply you can send directly** by default.

Use it with friends, acquaintances, and relationship conversations without first assigning a relationship label. Ask for a review when you want more detail. When no reply is appropriate, it can say so.

```text
Help me reply naturally, without emoji.
That does not sound like me. Make it less formal.
Keep my replies to this person shorter from now on.
Show me what you remember.
```

**You decide what to express; the Skill helps you express it.** It must not invent missing facts or present an inference as another person's actual thoughts.

## 🧩 Feature map

| What you need | How the Skill helps |
|---|---|
| 💬 Reply now | One final reply grounded in current facts |
| 🎛️ Sound like yourself | Separate settings for one turn, one person, global rules, and lasting preferences |
| 🧠 Remember what matters | Compact profiles separated from source evidence, with correction, export, and linked deletion |
| 📚 Use relevant guidance | 32 core methods retrieved by topic, with applicability and source notes |
| 🌱 Learn from experience | Optional extensions, off by default, with review, activation, suspension, and revocation; separate from core theory |
| ⚡ Keep daily use light | Separate fast, standard, and deep paths; unrelated material is not loaded in full by default |
| 🔐 Control your data | Private data outside the installation, verified backups, and recovery into a new directory |

Eight logical layers are implemented by four core modules. See the [architecture](references/architecture.md).

## 🧪 Validation and compatibility

Current public version: **v2.0.2**. The stable release designation does not expand the validation scope below. Existing evidence includes 116 local tests, 52 offline tool-entry calls, and 58 fully recorded tool-entry calls in anonymous acceptance work on a real ChatGPT Work host. These are different kinds of evidence, not an equivalent number of model-reply tests. Naming and documentation changes do not alter runtime behavior; unaffected results are reused.

On an already installed host, bounded reply samples, anonymous profile reads and memory correction, custom rules, core theory, and extension switches have been exercised. Automatic selection has limited sample evidence; it does not establish that every message triggers the Skill or loads a particular version.

**Still unverified:** first ZIP installation in an independent clean host, complete version binding for automatic body loading, actual model token usage and first-effective-reply/full-generation latency, long-term cross-device persistence, and other operating systems. The CI badge shows the repository's real workflow status; a workflow file alone does not prove that CI ran successfully.

Text replies require a model host supporting Agent Skills; screenshots require vision. Private data tools require Python 3.10+ and authorized file access. Tools manage data; the host model generates replies. Local preparation speed is not model generation speed.

## ⚡ Quick start

After installation, send chat text or a screenshot and ask, “Help me reply.” There is no mandatory profile setup or style questionnaire.

Anonymous examples do not require a relationship stage. The first execution must load the complete SKILL.md body; later turns may reuse it. If the host does not select the Skill, explicitly ask, “Use $social-reply to help me reply.” Seeing its description alone does not prove the full rules are active. Maintainers should verify loading evidence separately; ordinary users should not need to supply file paths with each reply.

- “Less formal; that does not sound like me”: get one replacement, for this turn only.
- “Do not use emoji with this person from now on”: update only that person's private settings.
- “Show current settings” or “What do you remember?”: inspect effective scope, sources, and pending claims.
- “Use approved experience”: enable application; “Pause learning”: stop proposing new extensions. These are separate switches.
- “Remember this important fact” or “Back up my data”: execute and verify only when authorized storage is available; otherwise state the limitation.

## 📦 Installation and data packages

Download the installable ZIP and matching SHA-256 file from the [release](https://github.com/kwhi6693-web/social-reply/releases/tag/v2.0.2). Verify the checksum, then install the complete social-reply folder using your host's supported Skill installation flow and reload. Use the attached installer rather than assuming GitHub's generated source ZIP is the verified installable package.

The host AI handles understanding and generation. Ordinary text replies do not require Python; screenshots require vision. Local persistence tools use Python 3.10+, the standard library only, and authorized file permissions.

The public installer is for installation. Private migration packages, complete project archives, and database backups contain private data and are only for personal retention and recovery; do not upload them as public installers. Installation does not require the 32 original videos or a private migration package. The invocation name is social-reply.

```text
Use $social-reply to reply to this conversation. Give just one suitable reply.
Use $social-reply. For this turn: natural, no emoji, at most thirty characters.
Use $social-reply to review the facts and unknowns in this invitation.
```

Private identities, tone preferences, relationship goals, and boundaries are not distributed in the public package. Set them yourself or inherit them through a private migration.

## 🧰 Local entry points

These interfaces are for hosts and maintainers; ordinary users can use natural language. Commands accept JSON on stdin and return JSON on stdout. They do not execute code embedded in input. PRIVATE_DIR represents an authorized private directory outside the Skill installation.

```bash
python -B scripts/social_reply.py --data PRIVATE_DIR init
python -B scripts/social_reply.py --data PRIVATE_DIR person-add
python -B scripts/social_reply.py --data PRIVATE_DIR context
```

After authorizing storage, use storage-bind to bind an existing private directory. Later commands such as context can then omit --data. The default locator lives in the current user's state directory; --binding selects another private locator. Explicit --data always takes precedence. A binding does not contain the database and does not guarantee access after switching devices or clearing the workspace.

person-add input:

```json
{"identifier":"PERSON_A","aliases":["Example person"]}
```

context input:

```json
{"identifier":"PERSON_A","topic":"daily","mode":"reply","custom":{"max_chars":30}}
```

context returns material for the host model to turn into a reply. Do not display the full JSON to a user who asked for one sentence.

Since 2.0.1, when topic-specific plus general rules exceed 16, processing explicitly switches to STANDARD and requests topic consolidation instead of silently dropping approved rules. Unrelated topics or people do not trigger this limit; existing rules and private data are preserved.

| Command | JSON fields |
|---|---|
| person-add / person-resolve / profile-get | identifier, optional aliases (empty when unknown); or alias; or identifier |
| aliases-set | identifier, aliases, expected; preserves person ID |
| source-add | identifier (null for global), kind, content; optional event_group, sent |
| claim-upsert | identifier, content, source_refs, evidence_type, confidence, reason, expected; optional claim_id, status |
| source-get / memory-list | source_id, identifier; or identifier, limit, offset |
| source-delete / person-delete | source_id, optional retain_anonymized replacement summary; or identifier, expected |
| config-get / config-set / config-reset | scope; scope, data, expected; scope, expected |
| core-get / core-propose | optional version; rules, reason, optional replace_ids |
| core-adopt / core-rollback | proposal, expected_version, confirmed; or version, expected_version |
| extension-propose | scope, content, kind, source_refs, conditions; optional counterevidence |
| extension-transition | identifier, state, expected_version, confirmed; optional content (revised only) |
| extension-rollback / extension-delete / extension-list | identifier, version, expected_version, confirmed; or scope |
| export / restore | destination; or source, destination (new directory) |
| migrate | records; dry-run by default, writes only with apply=true |
| health | empty object; checks database integrity and foreign keys |
| check-reply | reply, config; checks single-reply format, length, and avoided words only |
| extract | archive, destination, optional budgets; no --data needed |
| storage-status | empty object; checks binding and file existence, not database integrity or durable cloud persistence |
| storage-bind | directory, expected, confirmed=true; expected from storage-status revision; does not create a database |
| storage-backup | destination (new private directory); saves snapshot.sqlite3 and recovery.json |
| storage-recover | manifest, destination (new private directory), confirmed=true; verifies before recovery and does not switch bindings automatically |
| user-status | optional identifier; effective settings, per-field sources and revisions, extension switches; compact profile and capacity warnings for a specified person |

Read expected from the latest profile-get or config-get; do not guess it. Report actual failures without claiming data was saved, loaded, or deleted.

context also accepts as_of (YYYY-MM-DD), preferably the client's current date; the default is UTC. Temporal reminders refresh even on cache hits without changing profiles or automatically revoking boundaries. For relative dates, valid_through is only a review aid derived from the record's update time, not proof of the original message date. “Recently” is not assigned an arbitrary expiry.

Common Chinese temporary phrases such as “明天” (tomorrow), “下周” (next week), “周末” (the weekend), “本月” (this month), and “今年” (this year) prompt conservative verification instead of unsupported deadlines. This keyword behavior is not proof of equivalent detection in every language. Keyword matching is not complete temporal language understanding; the host must still use the original text and current facts. The 64 KiB budget is checked after adding temporal reminders; overflow uses STANDARD consolidation while preserving claims and evidence.

## 🌱 Settings and extensions

Settings: language, tone, max_chars, nickname, avoid, relationship_goal, output_mode, extension_enabled, extension_generate, extension_auto_lowrisk. scope is global, SELF, or a person ID. Per-turn custom settings apply only to that turn and do not change historical facts. config-reset resets its scope; export includes effective configuration.

Extensions are off by default. extension_enabled controls application; extension_generate controls proposing candidates. Disabling application while retaining branches does not change Core. extension-delete removes all branches and history in the specified scope. By default, activation requires review and user confirmation; Core imports follow a separate review process.

## 🗂️ Migration and recovery

1. Preserve original documents and videos. Check archive volumes, CRC, manifests, and duplicates; extract safely into a new private directory.
2. Prepare private migration JSON: each records item contains person_id (or null), aliases, content, and optional claims (a string array) and event_group.
3. Run migrate as a dry-run before apply. Sources are deduplicated by hash; claims automatically migrated from old summaries are unknown/pending, without claiming to reread original screenshots. Each item commits transactionally; interruption can be retried with the same mapping.
4. Put confirmed tone, boundaries, and current goals in the relevant private configuration. Preserve old documents without copying them into public rules.
5. export creates a consistent, unencrypted snapshot. restore targets a new directory and checks health without overwriting an existing directory. Local deletion does not erase original uploads or platform backups.

For routine backups, use storage-backup and keep the manifest with its snapshot. storage-recover checks size, SHA-256, schema, database integrity, and foreign keys before restoring into a new directory. Only after verified recovery, explicitly switch storage-bind using the latest binding revision. Preserve the original directory, older snapshots, and existing binding. Checksums detect corruption and mismatches; they do not provide encryption or a source signature. Local saving is not an external backup. Host persistence requires independent save evidence and a later recovery check.

## 🔧 Maintenance

```bash
python -B scripts/validate_skill.py
python -B -m unittest discover -s tests -v
python -B scripts/benchmark.py
```

The benchmark measures local context preparation: SQL reads, logical data files, bytes, and token counts when available. If host first-token timing, billed tokens, or complete model generation latency cannot be observed, mark them unverified rather than substituting local milliseconds.

Design references: [Architecture](references/architecture.md), [Profiles and memory](references/profile-memory.md), [Core theory](references/theory-core.md), and [Extensions](references/extensions.md). The three READMEs are localized; linked implementation references and the Skill entry are not fully translated.

The public package contains general rules, tools, and anonymous tests only. Real records, private databases, exports, credentials, machine paths, private locators, and workspace Git history do not belong in a public package. Automated scanning still needs human review. The host model may process input; no zero-transmission, default encryption, or permanent platform-backup erasure guarantee is made.

Code and original documentation use MIT. This license does not grant rights to third-party videos or user materials.

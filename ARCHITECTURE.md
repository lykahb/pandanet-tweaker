# Architecture

This document is the top-level map of the repository.

It follows the same basic recommendation from OpenAI's "Harness engineering: leveraging Codex in an agent-first world" (February 11, 2026): keep `AGENTS.md` short, keep repository knowledge in versioned files, and make architecture legible through stable boundaries instead of long prompt instructions.

## Purpose

`pandanet-tweaker` is a narrow CLI that patches Pandanet's Electron `app.asar` with replacement board and stone assets, using Sabaki themes as the primary import format.

The architecture is optimized for:

- narrow scope
- predictable data flow
- explicit target mapping
- agent and human legibility
- mechanical verification through tests

## System Shape

The main flow is:

```text
CLI
  -> stage theme source
  -> import theme or explicit assets
  -> normalize to semantic roles
  -> build replacement plan
  -> map semantic roles to Pandanet targets
  -> patch CSS/JS/runtime assets
  -> rebuild a new app.asar
```

The semantic roles are intentionally small and stable:

- `board`
- `stone-black`
- `stone-white`

Everything else should be derived from those roles or explicitly modeled as an extension.

## Layer Map

### 1. Interface Layer

Files:

- `src/pandanet_tweaker/cli.py`

Responsibilities:

- parse CLI arguments
- construct typed requests
- call orchestration code
- print theme summaries and replacement plans

Non-responsibilities:

- theme parsing
- Pandanet path knowledge
- direct ASAR manipulation

## 2. Core Domain Layer

Files:

- `src/pandanet_tweaker/models.py`
- `src/pandanet_tweaker/errors.py`

Responsibilities:

- define stable typed contracts such as `ImportedTheme`, `ThemeAsset`, `ReplaceRequest`, and `ReplacementPlan`
- define shared enums and error types

Rules:

- keep this layer dependency-light
- avoid filesystem, archive, or target-specific behavior here
- prefer typed dataclasses over loose dict passing

## 3. Theme Input Layer

Files:

- `src/pandanet_tweaker/theme_sources.py`
- `src/pandanet_tweaker/assets.py`
- `src/pandanet_tweaker/importers/sabaki.py`

Responsibilities:

- stage theme directories or zip files
- load explicit asset overrides
- detect Sabaki theme structure
- extract theme metadata, asset bytes, stone transforms, and random variants
- normalize imported assets into internal semantic roles

Rules:

- this layer must not know Pandanet archive paths
- this layer must not patch CSS or JS
- importer logic should be format-specific, not target-specific

If a new theme format is added, it should arrive as a new importer module and still produce the same internal contracts.

## 4. Target Description Layer

Files:

- `src/pandanet_tweaker/targets/pandanet.py`
- `docs/pandanet-assets.md`

Responsibilities:

- define Pandanet-specific file paths, stock references, selectors, and helper mappings
- translate semantic roles into target archive paths and rewritten CSS/JS references
- define deterministic helpers such as source archive resolution and grid-filter derivation

Rules:

- `docs/pandanet-assets.md` is the source of truth for asset paths and dimensions
- `targets/pandanet.py` is the executable encoding of that truth
- this layer must not parse Sabaki packages

## 5. Orchestration and Patch Layer

Files:

- `src/pandanet_tweaker/pipeline.py`

Responsibilities:

- compose input loading, normalization, validation, target mapping, and output rebuilding
- build dry-run replacement plans
- patch Pandanet CSS and JS references
- inject narrow runtime hooks when stone transforms require runtime drawing changes
- validate user options before rebuild

Rules:

- this is the only layer that should stitch importers, targets, and packaging together
- keep policy decisions here, not in the CLI
- keep fragile minified-JS seams documented in `docs/pandanet-js-patches.md`

Current pressure point:

- `pipeline.py` is both orchestration and patch engine. That is acceptable at the current size, but if patch behavior grows, split by responsibility rather than by file type:
  - planning
  - CSS patching
  - JS patching
  - runtime script generation

## 6. Packaging Layer

Files:

- `src/pandanet_tweaker/packaging/asar.py`

Responsibilities:

- isolate the third-party `asar` dependency
- expose read, extract, pack, and rebuild operations
- translate backend failures into project errors

Rules:

- no theme-format knowledge
- no Pandanet selector knowledge
- no CLI parsing

This layer should remain a thin adapter.

## 7. Verification Layer

Files:

- `tests/test_sabaki.py`
- `tests/test_pipeline.py`
- `tests/test_pandanet_targets.py`
- `tests/test_asar_packaging.py`

Responsibilities:

- prove importer behavior against theme fixtures
- prove replacement-plan behavior and patch generation
- prove Pandanet target helpers
- prove packaging adapter behavior around the ASAR backend

Near-term gap:

- add fixture-based integration tests for extract -> replace -> rebuild against known sample archives

## Dependency Rules

Allowed dependency direction:

```text
cli
  -> pipeline
  -> models / errors

pipeline
  -> assets
  -> theme_sources
  -> importers/*
  -> targets/*
  -> packaging/*
  -> models / errors

importers/*
  -> theme_sources
  -> models / errors

targets/*
  -> models

packaging/*
  -> errors

models / errors
  -> standard library only
```

Disallowed dependency direction:

- importers -> targets
- importers -> packaging
- targets -> importers
- targets -> packaging
- packaging -> importers
- packaging -> targets
- CLI -> direct ASAR backend calls

These rules matter because the project has two different axes of change:

1. input formats such as Sabaki themes
2. output targets such as Pandanet archive paths and patch seams

Those axes should stay isolated.

## Architectural Invariants

The following invariants should stay true unless the project goal changes:

- The tool remains Pandanet-specific. Do not turn it into a generic Electron patcher.
- Sabaki import logic stays isolated from Pandanet target mapping.
- The default behavior writes a new output archive instead of overwriting an installed app in place.
- Dry-run planning remains a first-class path.
- Asset bytes and extensions are preserved whenever possible so Electron can render original formats, including SVG.
- The preferred source archive is a clean `original-app.asar`.
- Fragile target facts live in repository docs, not in memory or chat history.
- Human decisions that affect future changes should be written into docs or tests.

## Repository Knowledge Model

This repository should use progressive disclosure:

- `AGENTS.md`: short operating constraints and current priorities
- `ARCHITECTURE.md`: top-level system map and dependency rules
- `docs/pandanet-assets.md`: authoritative Pandanet asset inventory
- `docs/pandanet-js-patches.md`: ledger for minified patch anchors and upgrade notes
- `docs/plan.md`: implementation plan and outstanding work

The goal is that a future contributor, or an agent, can recover the important context from the repository itself without depending on chat history.

## How To Extend Safely

### Add a new Pandanet target

1. Update `docs/pandanet-assets.md`.
2. Encode the mapping in `targets/pandanet.py`.
3. Patch through `pipeline.py`.
4. Add or update tests.

### Add a new theme format

1. Add a new importer under `src/pandanet_tweaker/importers/`.
2. Normalize it into the existing semantic roles and typed models.
3. Do not add target-specific conditionals to the importer.
4. Add importer-specific tests.

### Add a new patch behavior

1. Prefer a typed input on `ReplaceRequest` or related models.
2. Keep target constants in `targets/pandanet.py`.
3. Keep JS seam notes in `docs/pandanet-js-patches.md`.
4. Add dry-run plan coverage and patch tests.

### Add a new packaging backend

1. Keep it behind `src/pandanet_tweaker/packaging/`.
2. Preserve the existing high-level rebuild interface.
3. Do not let backend-specific details leak into CLI or importer code.

## Recommended Follow-Ups

These are not required for correctness today, but they align with the repository-knowledge and boundary-enforcement guidance that inspired this document:

- add a lightweight boundary test that enforces allowed import directions
- add integration fixtures for real or minimized ASAR samples
- add a small doc-maintenance habit: when a patch anchor or target path changes, update docs in the same change
- keep `AGENTS.md` short and let this file carry the architectural map

## Reference

- OpenAI, "Harness engineering: leveraging Codex in an agent-first world," February 11, 2026: https://openai.com/index/harness-engineering/

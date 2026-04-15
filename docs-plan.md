# Documentation Split Plan

This plan is based on the current state of:
- `README.md`
- `README-ru.md`
- `SPEC.md`
- `AGENTS.md`

The goal is to redesign project-facing documentation without rewriting the current `README.md` immediately.

## 1. Main idea

Instead of editing the existing `README.md` right away, create a new pair of landing-style files:

- `README-new.md`
- `README-new-ru.md`

These files should act as open source project landing pages, while the detailed reference material moves into:

- `docs/`
- `docs-ru/`

`SPEC.md` should remain an internal technical description of the implementation, not a replacement for user-facing docs.

## 2. Documentation layers

The documentation should be split into three layers.

### 2.1 Landing layer

Files:
- `README-new.md`
- `README-new-ru.md`

Purpose:
- explain what the project is;
- explain why it exists;
- show the architecture visually;
- show a demo;
- give a fast path to first success;
- list features;
- link to detailed docs.

These files should stay short and high-signal.

### 2.2 Reference documentation layer

Folders:
- `docs/`
- `docs-ru/`

Purpose:
- full command documentation;
- config reference;
- networking and proxy reference;
- backup workflows;
- troubleshooting;
- known issues.

These directories should contain the complete user documentation set in English and Russian.

### 2.3 Internal technical layer

File:
- `SPEC.md`

Purpose:
- document current implementation and system behavior;
- support development and change control;
- not serve as the main onboarding document for end users.

## 3. Target structure for README-new.md

Recommended structure for `README-new.md`:

1. Hero / one-paragraph pitch
   - what `Agent Safety Kit` is;
   - who it is for;
   - what risk it addresses.

2. Why this matters
   - short explanation of the threat model;
   - 3-5 links to real examples where agents damaged files or repos;
   - short explanation of why “just use git” is not enough for this specific workflow.

3. Architecture overview
   - placeholder for the future visual scheme;
   - 4-6 bullets below the scheme explaining host, VM, mounted project, backups, networking, and agent execution flow.

4. Demo
   - placeholder for a GIF / console recording;
   - a short explanation of what the viewer sees.

5. Quick start
   - shortest path to first working setup:
     - install;
     - `agsekit config-gen`;
     - `agsekit up`;
     - `agsekit addmount`;
     - `agsekit run`.
   - avoid long explanations here.

6. Features
   - concise list of main capabilities:
     - VM isolation;
     - automatic incremental backups;
     - declarative YAML config;
     - agent installers;
     - `proxychains`;
     - `http_proxy`;
     - `portforward`;
     - interactive and non-interactive flows;
     - Linux and macOS host preparation.

7. Short how-to
   - small practical entry points with links to full docs:
     - how to use an OpenAI-compatible API with supported agents;
     - how to work behind restricted networks;
     - how to use `proxychains`;
     - how to use `http_proxy`;
     - how to use `portforward`.

8. Documentation section
   - direct links to:
     - `docs/README.md`;
     - `docs-ru/README.md`;
     - command docs;
     - config docs;
     - networking docs;
     - backup docs;
     - troubleshooting;
     - known issues.

9. Supported agents
   - compact list only;
   - long explanations should move into docs.

10. Limitations / philosophy / security model
   - short section describing what the tool does not do;
   - links to `docs/philosophy.md` and `docs-ru/philosophy.md`.

11. Optional closing sections
   - platform support matrix;
   - contributing;
   - license;
   - FAQ.

## 4. Target structure for README-new-ru.md

`README-new-ru.md` should be a full Russian counterpart of `README-new.md`.

It should mirror:
- structure;
- examples;
- documentation links;
- supported feature descriptions.

It should not become a separate, divergent document.

## 5. Suggested additional sections for landing docs

Besides the user-requested content, the landing README should also include:

- “Who is this for / who is this not for”
- “What this tool does not do”
- “Current limitations”
- “Known issues”
- “Platform support”
- “FAQ”
- “Contributing”
- “License”

Not all of these need to be large sections. Some can be short link hubs into `docs/`.

## 6. Reference docs structure

Recommended structure for English docs:

- `docs/README.md`
- `docs/getting-started.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/agents.md`
- `docs/networking.md`
- `docs/backups.md`
- `docs/troubleshooting.md`
- `docs/known-issues.md`
- `docs/commands/prepare.md`
- `docs/commands/up.md`
- `docs/commands/create-vm.md`
- `docs/commands/install-agents.md`
- `docs/commands/run.md`
- `docs/commands/mount.md`
- `docs/commands/status.md`
- `docs/commands/doctor.md`
- `docs/commands/systemd.md`
- `docs/commands/vm-lifecycle.md`
- `docs/commands/networking.md`
- `docs/commands/backups.md`

Recommended structure for Russian docs:

- `docs-ru/README.md`
- `docs-ru/getting-started.md`
- `docs-ru/architecture.md`
- `docs-ru/configuration.md`
- `docs-ru/agents.md`
- `docs-ru/networking.md`
- `docs-ru/backups.md`
- `docs-ru/troubleshooting.md`
- `docs-ru/known-issues.md`
- `docs-ru/commands/prepare.md`
- `docs-ru/commands/up.md`
- `docs-ru/commands/create-vm.md`
- `docs-ru/commands/install-agents.md`
- `docs-ru/commands/run.md`
- `docs-ru/commands/mount.md`
- `docs-ru/commands/status.md`
- `docs-ru/commands/doctor.md`
- `docs-ru/commands/systemd.md`
- `docs-ru/commands/vm-lifecycle.md`
- `docs-ru/commands/networking.md`
- `docs-ru/commands/backups.md`

## 7. What belongs in docs, not in README-new

The following content should be moved out of the landing README into docs:

- full CLI command reference;
- all command arguments and options;
- long YAML configuration reference;
- detailed `proxychains` / `http_proxy` / `portforward` behavior;
- full backup command behavior;
- detailed installation details for each agent;
- troubleshooting procedures;
- known issues list.

The landing README should link to these sections instead of embedding them in full.

## 8. Linking rules

The new documentation system should include:

### 8.1 From landing docs

`README-new.md` and `README-new-ru.md` should link to:
- documentation index;
- quick start;
- configuration reference;
- command docs;
- troubleshooting;
- known issues;
- `docs/philosophy.md` / `docs-ru/philosophy.md`.

### 8.2 Inside docs

Each doc page should include:
- a short intro;
- examples;
- links to related pages;
- “See also” or equivalent footer navigation.

### 8.3 Language parity

The English and Russian trees should mirror each other by file set and structure.

## 9. Proposed writing style

### 9.1 README-new*

Style:
- concise;
- persuasive;
- open source landing page style;
- optimized for first-time readers.

### 9.2 docs/*

Style:
- operational;
- explicit;
- command-oriented;
- suitable for lookup and troubleshooting.

## 10. AGENTS.md update plan

`AGENTS.md` should be expanded with explicit documentation rules:

- user-facing documentation lives in `docs/` and `docs-ru/`;
- `README-new.md` and `README-new-ru.md` are landing pages, not full reference manuals;
- when CLI commands, arguments, config semantics, architecture, networking, proxy behavior, backup behavior, or agent workflows change, the matching pages in `docs/` and `docs-ru/` must be updated;
- when a new command is added, a corresponding page must be created in `docs/commands/` and `docs-ru/commands/`, or an existing command page must be updated;
- when examples change in one language, the matching document in the second language must be kept in sync.

## 11. Migration order

Recommended order of work:

1. Create `README-new.md` and `README-new-ru.md`.
2. Create the skeletons for `docs/` and `docs-ru/`.
3. Write `docs/README.md` and `docs-ru/README.md` as documentation indexes.
4. Move command reference material out of the current README into `docs/commands/*`.
5. Move YAML config reference into `docs/configuration.md` and `docs-ru/configuration.md`.
6. Move proxy/networking explanations into `docs/networking.md` and `docs-ru/networking.md`.
7. Move backup workflows into `docs/backups.md` and `docs-ru/backups.md`.
8. Add troubleshooting and known-issues pages.
9. Link `README-new*` to all major documentation sections.
10. Update `AGENTS.md` with documentation maintenance requirements.
11. After the new documentation is complete, decide whether the old `README.md` and `README-ru.md` should be replaced, archived, or redirected to the new landing files.

## 12. Important scope note

This plan intentionally does not rewrite the current `README.md` and `README-ru.md` yet.

The next implementation phase should work on:
- `README-new.md`
- `README-new-ru.md`
- `docs/`
- `docs-ru/`
- `AGENTS.md`

and only later decide how to replace or retire the current README pair.

---
name: doc-taxonomy
description: Canonical documentation types and locations for Job Applications.
---

# Documentation Taxonomy

**Location:** `docs/ai_context/DOC_TAXONOMY.md`
**Updated by:** any agent that adds or changes a documentation type
**Read by:** every agent at session start

## Purpose

This file defines where durable documentation belongs. Prefer extending an
existing canonical document over adding another Markdown file.

## Hierarchy

```text
project-root/
├── README.md                 project entry point and architecture
├── AGENTS.md                 project-specific agent additions
├── CONVENTIONS.md            project code and data conventions
├── docs/
│   ├── specs/                what must be built
│   ├── plans/                how confirmed work will be built
│   ├── tasks/                executable task breakdowns
│   ├── execution-plans/      approved sequential-execution prompts
│   ├── ai_context/           current machine-readable project context
│   ├── human_docs/           durable human guides when genuinely needed
│   └── session_state.md      current resumable state
├── <subsystem>/
│   ├── README.md             subsystem scope and navigation
│   ├── AGENTS.md             local additions only, when necessary
│   └── RULES.md              consolidated domain rules, when necessary
└── archive/                  superseded material plus manifests
```

## Document Definitions

### Root files

- `README.md`: concise human-facing project overview, capabilities, structure,
  sources of truth, and navigation. It does not duplicate detailed rules.
- `AGENTS.md`: project-specific additions to `~/agent-governance/AGENTS.md`.
  It does not copy global rules.
- `CONVENTIONS.md`: project-specific code, data, naming, and output standards.

### Planning documents

- `docs/specs/<NNN>_<feature>.md`: requirements and acceptance criteria. Status
  progresses from Draft to Confirmed, In Progress, and Implemented.
- `docs/plans/<NNN>_<feature>.md`: technical design and ordered implementation
  after the matching spec is approved.
- `docs/tasks/<NNN>_<feature>.md`: phase-ordered executable tasks after the
  matching plan is approved.
- `docs/execution-plans/<NN>-seq-exec-prompt.md`: sequential execution prompt
  produced after task approval.

The spec, plan, and task file for one change share the same zero-padded number.

### Agent context

- `docs/ai_context/CODEBASE_MAP.md`: current module ownership, public entry
  points, schemas, shared utilities, dependency diagram, and known gaps.
- `docs/ai_context/SYSTEM_WORKFLOW_MAP.md`: current end-to-end data flow and
  stage ownership.
- `docs/ai_context/AGENT_EXECUTION_LOG.md`: append-only outcomes and
  do-not-repeat guidance for agent tasks.
- `docs/session_state.md`: current phase, active artifacts, blockers, and next
  authorized action. It is current state, not history.

### Subsystem documentation

- `<subsystem>/README.md`: subsystem ownership, inputs, outputs, supported entry
  points, and local diagram when useful.
- `<subsystem>/AGENTS.md`: only specialized additions or overrides that cannot
  live in root rules.
- `<subsystem>/RULES.md`: consolidated operational policy for that domain.
- `<subsystem>/SCHEMA.md`: data contract when the schema requires explanation
  beyond column names.

### Human guides

`docs/human_docs/` is reserved for durable how-to or conceptual guides that do
not fit the root or subsystem README. Do not place agent scratch notes or run
reports here.

## Content That Belongs Elsewhere

| Content | Canonical location |
|---|---|
| Verified career facts | `profile_info/` |
| Job, application, company, contact, message state | `tracking/` |
| Reproducible run output | `execution_results/` |
| Resume templates and resume-specific rules | `resume_custom/` |
| Superseded historical material | organized `archive/` with a manifest |
| Temporary agent notes | do not persist unless incorporated canonically |

## Naming

- Use predictable, responsibility-based names.
- Use `<NNN>_<snake_case_name>.md` for spec, plan, and task documents.
- Use Git for versions; do not create `_new`, `_final`, `_latest`, or
  agent-named variants.

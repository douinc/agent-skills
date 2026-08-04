---
name: graph-engineering
description: Use when work spans multiple components, an unfamiliar codebase needs dependency mapping, impact analysis depends on architecture or constraints, or durable evidence-backed project context must be created or refreshed.
---

# Graph Engineering

## Overview

Model a project as evidence-backed knowledge, not a pile of files. Build only the graph needed for the current decision, keep facts separate from inference, and persist only durable knowledge.

## Core Contract

1. Define the question and the smallest useful scope.
2. Inspect existing documentation before source code, tests, configuration, and history.
3. Attach a repository path, symbol, command result, or commit to every important claim.
4. Classify each claim as `observed`, `inferred`, `proposed`, or `unknown`.
5. Represent relevant entities and connections with the vocabulary in [knowledge-schema.md](references/knowledge-schema.md).
6. Apply [update-policy.md](references/update-policy.md) before changing durable documentation.
7. Report impact, risk, unresolved questions, and the evidence that supports each conclusion.

Do not require a graph database, MCP server, external API, or special runtime. A compact Markdown table or diagram is enough when it preserves the required semantics.

## Output Contract

Return these sections in order:

1. **Scope** — question, boundaries, and audited revision when available.
2. **Evidence** — strongest sources and any contradictions.
3. **Knowledge map** — relevant nodes and directed relations.
4. **Impact** — affected components, interfaces, constraints, and decisions.
5. **Risks and unknowns** — consequences, missing evidence, and validation needed.
6. **Persistence decision** — no change, update an existing document, or propose a new durable location.

Example map:

| Source | Relation | Target | Status | Evidence |
| --- | --- | --- | --- | --- |
| `AccountDeletionRoute` | `implemented_by` | `DeleteAccountService` | observed | `api/routes/account.ts#deleteAccount` |
| `DeleteAccountService` | `depends_on` | `DeletionJob` | proposed | approved ADR-0042 |
| `DeletionJob` | `constrained_by` | `Idempotent cleanup` | inferred | retry configuration + integration test |

## Durable Knowledge Guardrail

Default to read-only analysis. Edit project knowledge only when the user explicitly requests documentation changes or the authorized task clearly includes them.

Never persist:

- chain-of-thought, hidden reasoning, scratch notes, or loop transcripts;
- unverified guesses presented as facts;
- secrets, credentials, personal data, or environment-specific identifiers;
- temporary status that will be obsolete when the current task ends.

## Common Mistakes

| Mistake | Correction |
| --- | --- |
| Mapping every file | Keep only entities that affect the current decision. |
| Treating a diagram as evidence | Attach evidence to each important node or relation. |
| Replacing conflicting history | Mark the conflict and supersede only with stronger evidence. |
| Creating a new context folder immediately | Prefer the closest existing durable document. |
| Writing assumptions as architecture | Label them `inferred`, `proposed`, or `unknown`. |

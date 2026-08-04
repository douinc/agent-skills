# Graph Engineering and Loop Engineering Skills Design

## Goal

Add two product-independent agent skills to `agent-skills`:

- `graph-engineering`: builds and maintains durable project knowledge.
- `loop-engineering`: controls non-trivial development work through small, verified iterations.

The skills translate the concepts in “Graph Engineering and Loop Engineering for Agent Workflows” into practical repository workflows without requiring a graph database, a specific MCP server, or any Dou/Saylog product context.

## Design principles

- Keep memory management and execution control as separate responsibilities.
- Make `loop-engineering` the normal entry point for development work.
- Allow each skill to work independently.
- Use `graph-engineering` only when a task crosses files, components, policies, or architectural boundaries.
- Prefer existing project documentation over creating a new documentation hierarchy.
- Do not persist transient reasoning, iteration logs, or unverified assumptions.
- Require fresh evidence before completion claims.

## Architecture

The dependency is one-way:

~~~text
user request
    ↓
loop-engineering
    ├── load durable context through graph-engineering when warranted
    ├── plan → act → verify → decide
    └── return durable facts and decisions for graph update
~~~

`graph-engineering` never invokes `loop-engineering`. This prevents recursive skill invocation and keeps knowledge maintenance usable as a standalone activity.

If `graph-engineering` is unavailable, `loop-engineering` performs a temporary repository context scan and continues without writing persistent project knowledge.

## Skill 1: graph-engineering

### Trigger

Use for tasks that require understanding or maintaining cross-file architecture, dependencies, interfaces, decisions, constraints, risks, or persistent project context. Skip it for isolated, low-risk edits whose required context is already explicit.

### Inputs

- The current user objective.
- Repository instructions such as `AGENTS.md`, `CLAUDE.md`, and `README.md`.
- Architecture documents, ADRs, API contracts, issue references, and relevant Git history.
- Source code and tests that provide current implementation evidence.

### Knowledge model

The skill uses a lightweight graph vocabulary:

| Node | Meaning |
| --- | --- |
| Component | A service, package, module, or major subsystem |
| Interface | An API, event, file format, CLI, or shared contract |
| Decision | An accepted architectural or product choice |
| Constraint | A policy, compatibility requirement, or invariant |
| Evidence | Code, test, document, issue, or commit supporting a claim |
| Risk | A known failure mode or uncertain impact |
| Unknown | A question that must not be silently guessed |

Supported relationships include:

- `depends_on`
- `implemented_by`
- `constrained_by`
- `verified_by`
- `supersedes`
- `blocked_by`

The model is conceptual. Markdown tables, headings, links, and existing repository documents are sufficient storage.

### Read behavior

1. Discover repository-owned instructions and knowledge documents.
2. Prefer sources closest to the implementation being changed.
3. Distinguish verified facts, documented decisions, inferences, and unknowns.
4. Check whether durable documentation agrees with current code and tests.
5. Report conflicts instead of silently choosing one source as authoritative.

### Write behavior

The default behavior is read-only. Persist knowledge only when:

- the project already has an appropriate owned document; or
- the user approves creation of a durable context location.

If no suitable location exists, propose `docs/agent-context/` but do not create it automatically.

Only persist information likely to remain useful across future tasks:

- stable component relationships;
- accepted decisions and their evidence;
- durable constraints and interfaces;
- unresolved risks or unknowns that affect future work.

Do not persist chain-of-thought, temporary plans, raw command output, or routine loop history.

### Output

A concise context packet containing:

- relevant components and relationships;
- controlling decisions and constraints;
- supporting evidence;
- conflicts or stale information;
- unknowns that may block work;
- recommended durable documentation updates.

## Skill 2: loop-engineering

### Trigger

Use for non-trivial development tasks that require multiple actions, iterative verification, failure analysis, or explicit completion criteria. For trivial edits, use a compact loop consisting of goal, action, and verification.

### Loop state

Each iteration tracks:

| Field | Purpose |
| --- | --- |
| Goal | The concrete outcome being pursued |
| Acceptance criteria | Observable conditions proving completion |
| Constraints | Scope, policies, compatibility, and safety limits |
| Evidence | Facts supporting the current approach |
| Next action | The smallest useful action to perform |
| Verification | The command or observation that tests the action |
| Result | What actually happened |
| Decision | Continue, revise, complete, or stop |

This state is conversational and is not committed to the repository by default.

### Protocol

1. Restate the goal and observable acceptance criteria.
2. Classify the task as trivial, local, or cross-cutting.
3. For cross-cutting work, load context through `graph-engineering` when available.
4. Select the smallest action that materially advances the goal.
5. Execute one coherent change.
6. Run the verification tied to that change.
7. Compare the result with the acceptance criteria.
8. Continue, revise the hypothesis, complete, or stop.
9. At completion, identify durable facts or decisions worth returning to `graph-engineering`.

### Stop conditions

Stop and report clearly when:

- all acceptance criteria are satisfied with fresh evidence;
- a policy or source-of-truth conflict requires user judgment;
- the same blocking condition occurs three times;
- required access, dependency, or external state is unavailable;
- the next action would exceed the authorized scope;
- verification disproves the current approach and no evidence-backed alternative is available.

### Output

- The achieved outcome or exact blocker.
- Fresh verification evidence.
- Remaining risks or unverified assumptions.
- Durable knowledge changes proposed or applied through `graph-engineering`.

## File layout

~~~text
skills/
├── graph-engineering/
│   ├── SKILL.md
│   └── references/
│       ├── knowledge-schema.md
│       └── update-policy.md
└── loop-engineering/
    ├── SKILL.md
    └── references/
        ├── loop-protocol.md
        └── stop-conditions.md
~~~

The main `SKILL.md` files contain trigger rules and the executable workflow. Reference files hold detailed schemas, examples, and checklists so the primary instructions remain concise.

## Repository integration

- Add both skills to the `agent-skills` README.
- Add independent marketplace entries for both skills.
- Document that users normally install both together, while each remains independently usable.
- Keep all examples generic and free of company- or product-specific repository names.

Recommended installation:

~~~bash
npx skills add douinc/agent-skills \
  --skill graph-engineering \
  --skill loop-engineering
~~~

## Failure handling

- Missing documentation: inspect the repository and label gaps as unknowns.
- Conflicting sources: cite both and request or propose a resolution.
- Stale documentation: verify against implementation and preserve history when updating.
- Missing companion skill: use the documented fallback rather than failing the task.
- Repeated failed actions: stop after the third occurrence of the same blocker.
- No test suite: use the strongest available structural or behavioral verification and state the limitation.

## Validation

Implementation is complete when:

- each skill directory and referenced file exists;
- frontmatter names match directory names;
- all relative links resolve;
- README and marketplace entries point to valid skill directories;
- `marketplace.json` parses successfully;
- no Dou, Saylog, Carevoice, or other product-specific dependency appears;
- scenario review confirms trivial, cross-cutting, conflicting-source, missing-companion, repeated-failure, and successful-completion behavior;
- `git diff --check` passes.

## Non-goals

- Building a graph database or visualization UI.
- Persisting every agent action or internal reasoning step.
- Replacing project-owned architecture documentation.
- Defining product policy, issue management, or deployment workflows.
- Creating a third orchestration skill in the first version.

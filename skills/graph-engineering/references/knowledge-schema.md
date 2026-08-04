# Knowledge Schema

Use this vocabulary to make maps consistent across repositories. Include only types that help answer the current question.

## Node types

| Type | Meaning | Typical evidence |
| --- | --- | --- |
| `Component` | Deployable unit, package, module, service, datastore, or operational subsystem | manifest, directory, deployment config |
| `Interface` | API, event, schema, command, shared type, or user-visible contract | route, schema, handler, contract test |
| `Decision` | Accepted or proposed architectural choice with rationale | ADR, issue, approved design |
| `Constraint` | Rule that bounds valid solutions | compatibility rule, policy, runtime limit, invariant |
| `Evidence` | Source supporting or challenging another node or relation | file, symbol, test result, commit, command output |
| `Risk` | Plausible adverse outcome with impact and trigger | failure mode, regression path, operational gap |
| `Unknown` | Material question whose answer changes the decision | missing owner, unresolved behavior, conflicting sources |

## Relation types

Relations are directed and written as `source → relation → target`.

| Relation | Meaning |
| --- | --- |
| `depends_on` | The source cannot operate or remain correct without the target. |
| `implemented_by` | The source contract or decision is realized by the target. |
| `constrained_by` | The target limits valid behavior or changes to the source. |
| `verified_by` | The target provides observable evidence for the source. |
| `supersedes` | The source replaces the target while preserving history. |
| `blocked_by` | The source cannot safely progress until the target is resolved. |

Do not invent relation names for synonyms. Add a plain-language note when the six relations cannot express useful nuance.

## Record shape

Give every important node a stable name within the map:

```yaml
id: interface.account-deletion
type: Interface
label: Account deletion request
status: observed
evidence:
  - api/routes/account.ts#deleteAccount
notes: Returns synchronously at the audited revision.
```

Represent each edge with its own support:

```yaml
source: interface.account-deletion
relation: implemented_by
target: component.delete-account-service
status: observed
evidence:
  - api/routes/account.ts#deleteAccount
```

YAML is illustrative. Use a Markdown table, diagram, or repository-native format when it is clearer.

## Claim status

| Status | Use when |
| --- | --- |
| `observed` | Directly supported by current code, tests, configuration, command output, or an authoritative accepted record. |
| `inferred` | Supported indirectly; state the inference and what would confirm it. |
| `proposed` | Describes a requested or recommended future state that is not yet accepted or implemented. |
| `unknown` | Evidence is absent, stale, or contradictory enough to prevent a reliable claim. |

## Consistency checks

- Every relation references nodes present in the map.
- Every important observed relation has evidence from at least one endpoint; critical cross-boundary relations should be checked at both endpoints.
- Proposed nodes never silently replace observed current-state nodes.
- Unknowns name the decision they block and the next evidence to collect.
- Risks identify an affected node, trigger, consequence, and verification or mitigation.

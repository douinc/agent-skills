# Loop Protocol

## Operational state

Track this concise state for the active task:

```yaml
objective: observable result to achieve
completion_evidence:
  - required check and expected result
constraints:
  - authority, safety, compatibility, and scope boundaries
budget:
  iterations_remaining: 5
  other_limit: user deadline or tool budget when supplied
blocker_occurrences:
  normalized-failure-signature: 0
iteration: 1
hypothesis: claim tested by this iteration
action: smallest authorized intervention
verification: command or observation and expected result
actual_result: evidence produced by verification
decision: retry | replan | complete | blocked | needs-user-decision
```

The five-iteration value is a conservative default when the user and repository supply no better bound. Reserve enough budget for final verification. Change the bound when task risk or cost justifies it, and state the new bound before continuing.

This is operational state, not a reasoning transcript. Record conclusions and evidence, never hidden chain-of-thought.

## PLAN

Select one hypothesis that can be disproved. Name:

- evidence supporting it;
- one action that tests it;
- expected observable result;
- exact verification;
- relevant constraint and budget cost.

If several independent actions are useful, order them by information gained per unit of cost and run one at a time unless parallel execution is demonstrably safe.

## ACT

Perform only the planned action. Preserve user changes and authority boundaries. Prefer reversible and local operations; resolve exact targets before destructive operations.

A terminal instruction such as “finish” or “do not stop” extends persistence toward the objective but does not authorize deployments, purchases, messages, deletion, or other new external effects.

## VERIFY

Run the check selected during PLAN. Capture the command or observation, exit status when applicable, and relevant result.

Classify the result:

- `confirmed`: expected evidence appeared;
- `disproved`: evidence contradicts the hypothesis;
- `inconclusive`: the check could not distinguish the hypothesis;
- `new-failure`: the action introduced or revealed a different failure.

Never replace the planned verification with a weaker check because it is easier to pass.

## DECIDE

Choose one transition:

| Transition | Predicate | Next state |
| --- | --- | --- |
| `complete` | Every completion criterion has fresh evidence. | Stop and report; for cross-cutting work, include stable facts, decisions, constraints, evidence, and unknowns as a durable-knowledge handoff. |
| `retry` | The objective is unchanged and new evidence supports a different action. | Decrement budget and PLAN again. |
| `replan` | New evidence changes scope, sequence, or dependency assumptions within existing authority. | Rewrite the affected state, decrement budget, and PLAN again. |
| `blocked` | Progress requires unavailable evidence, capability, authority, or verification, or the same blocker reaches its third occurrence. | Stop and report. |
| `needs-user-decision` | Multiple materially different valid paths depend on user intent or new authority. | Stop and present the decision. |

Count blocker occurrences by normalized condition or failure signature across the active loop, even when other failures occur between them. Do not call unchanged repetition a retry. Apply the no-progress rule in [stop-conditions.md](stop-conditions.md). A handoff does not authorize a documentation edit; apply `graph-engineering` update policy when installed.

## Example iteration

| Field | Value |
| --- | --- |
| Objective | Restore deterministic checkout tests. |
| Hypothesis | Shared clock state leaks between test files. |
| Action | Add one regression test that runs the two files in both orders. |
| Verification | Run the order-sensitive test command twice. |
| Actual result | Failure reproduces only when file B follows file A. |
| Decision | `retry` with new evidence; isolate teardown in the next iteration. |

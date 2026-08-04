---
name: loop-engineering
description: Use when a bounded multi-step task requires autonomous execution, repeated verification, recovery from failed attempts, progress under uncertainty, or an explicit decision to complete, stop, or request user direction.
---

# Loop Engineering

## Overview

Turn autonomous work into a bounded control loop. Every iteration must reduce uncertainty or move an observable result toward completion; activity alone is not progress.

## Entry Contract

Before acting, establish:

- one objective and its boundaries;
- observable completion evidence;
- safety, authority, and compatibility constraints;
- an iteration, time, or tool budget;
- the smallest verification command or observation that can test the next action.

Infer only reversible, low-risk defaults. If missing information would materially change public behavior, cost, scope, or an irreversible action, return `needs-user-decision`.

Read [loop-protocol.md](references/loop-protocol.md) before the first iteration and [stop-conditions.md](references/stop-conditions.md) before declaring an outcome.

## Run the Loop

Repeat `plan → act → verify → decide`:

1. **Plan:** choose one falsifiable hypothesis, one bounded action, and its expected evidence.
2. **Act:** perform the smallest authorized action that tests the hypothesis or advances the objective.
3. **Verify:** run the planned check and compare expected with actual evidence.
4. **Decide:** complete, retry with new evidence, replan, block, or request user direction.

Track the protocol state in task memory or temporary scratch space. Never add loop transcripts, chain-of-thought, or speculative reasoning to durable project documentation.

## Graph Escalation

Use local evidence for a contained change. Broaden the map when any observable condition holds:

- a public interface, shared schema, global configuration, or deployment boundary changes;
- failures appear in multiple components or layers;
- the same dependency knowledge is repeatedly rediscovered;
- impact or rollout order cannot be established from the local module.

When `graph-engineering` is installed, it is a **REQUIRED SUB-SKILL** for those cross-cutting cases. If unavailable, build a compact evidence-backed impact map inline and continue; do not fail only because the companion skill is absent.

`graph-engineering` never needs to invoke this skill.

## Progress and Final Output

During long tool work, give evidence-based progress updates at least every 60 seconds. Report the current decision and next bounded action without exposing private reasoning.

Finish with exactly one outcome:

| Outcome | Required report |
| --- | --- |
| `complete` | acceptance evidence, verification commands, and intentional changes |
| `blocked` | blocking condition, attempts made, recoverable workspace state, and next action |
| `needs-user-decision` | decision required, evidence, and materially different options |

## Common Mistakes

| Mistake | Correction |
| --- | --- |
| Repeating the same action | Require new evidence or replan. |
| Treating a passing check as sufficient | Match it to every completion criterion. |
| Expanding scope after each failure | Expand only across an observed dependency boundary. |
| Calling ambiguity a technical blocker | Use `needs-user-decision` when user intent must govern. |
| Persisting execution history as architecture | Persist only stable, evidence-backed project knowledge. |

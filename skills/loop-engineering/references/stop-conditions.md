# Stop Conditions

Evaluate these conditions during every DECIDE phase and before reporting completion.

## Complete

Return `complete` only when all are true:

- every stated acceptance criterion has fresh observable evidence;
- required focused and repository-level checks have passed or are explicitly out of scope;
- the resulting diff or artifact contains only intentional changes;
- no unresolved safety or authority boundary affects the outcome.

Previous runs, confidence, partial checks, and “should pass” are not completion evidence.

## Retry or replan

Continue only when all are true:

- budget remains after reserving final verification;
- the last iteration produced new evidence or completed an irreversible unit of progress;
- the next hypothesis or action differs in a way that can change the result;
- the action remains within scope and authority.

Use `retry` when the objective and scope remain stable. Use `replan` when evidence changes dependencies, ordering, or the authorized implementation route.

## No progress

Stop or replan when either occurs:

- three consecutive iterations produce the same blocking condition or failure signature without new evidence;
- the proposed next action would repeat a failed action for the third time with the same expected evidence.

Do not reset this count by renaming the hypothesis or making unrelated edits. If broader dependencies may explain the stall, apply the Graph Escalation conditions before declaring a block.

## Blocked

Return `blocked` when progress cannot continue within existing intent and authority, including:

- a required dependency, credential, environment, or artifact is unavailable;
- mandatory verification cannot run or remains nondeterministic after bounded investigation;
- the iteration, time, or tool budget is exhausted;
- a safety boundary forbids the required action;
- resolution requires external coordination that the task did not authorize.

Leave the workspace recoverable. Report the exact condition, evidence gathered, attempts made, remaining risk, and first action after unblocking.

## Needs user decision

Return `needs-user-decision` instead of guessing when:

- plausible interpretations change public behavior, data, compatibility, cost, or scope;
- an irreversible, destructive, production, financial, or external action needs new authority;
- user-owned changes conflict with the required implementation;
- the available options express different product or architectural intent.

Present only materially distinct options, their evidence, and their consequences. Do not hide a technical failure behind this outcome when an authorized evidence-gathering step remains.

## Immediate safety stop

Stop immediately when continuing may expose secrets or personal data, target an unresolved destructive path, overwrite unknown user work, or produce an unauthorized external effect. Preserve evidence without reproducing sensitive content in the report.

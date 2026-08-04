# Durable Knowledge Update Policy

## Read before writing

Search for the repository's existing knowledge homes first:

1. architecture documentation and diagrams;
2. accepted or proposed ADRs;
3. package and service README files;
4. contributor or agent instructions;
5. issue, design, and implementation-plan conventions.

Update the closest existing source of truth. Create `docs/agent-context/` only when no suitable home exists and the knowledge will remain useful across multiple tasks.

## Persistence threshold

Persist a claim only when all are true:

- **Durable:** likely to remain useful after the current task.
- **Material:** changes future implementation, review, operations, or safety decisions.
- **Supported:** carries evidence or is explicitly labelled as proposed or unknown.
- **Scoped:** belongs in the selected document without duplicating another source of truth.
- **Safe:** contains no secrets, personal data, hidden reasoning, or ephemeral execution state.

If any condition fails, keep the result in the current response rather than repository documentation.

## Allowed updates

| Situation | Action |
| --- | --- |
| Current evidence confirms existing knowledge | Keep it; refresh the verification marker only if the repository uses one. |
| Current evidence changes a durable fact | Update the fact and cite the new evidence. |
| A decision replaces an older decision | Mark the new decision as `supersedes`; preserve and link the older record. |
| Sources conflict | Record the conflict as `unknown`; do not choose silently. |
| Knowledge is stale but still historically useful | Add a stale or superseded marker and a current pointer. |
| Knowledge is wrong and has no historical value | Remove it only when authorized and the replacement evidence is clear. |

## Authorization boundary

Treat requests to analyze, explain, review, or diagnose as read-only. A request to create or update documentation authorizes only the smallest relevant knowledge change. Do not expand it into repository-wide documentation cleanup.

Before writing, state or internally verify:

- target document and why it is the correct source of truth;
- exact durable claims being added, changed, or superseded;
- evidence for each claim;
- links or indexes that must remain valid.

After writing, verify links, headings, referenced paths, and consistency with adjacent documentation. Report what changed and which unknowns remain.

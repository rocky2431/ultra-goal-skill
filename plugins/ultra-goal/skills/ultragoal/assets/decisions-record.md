<!--
Template for the paired decisions record. Save as `<slug>.decisions.md`.
Four columns, exactly these headings. `Who` is `owner` when the owner chose it and `agent`
when you assumed it or set it outright - an assumption the owner never saw is not an
agreement, and without the column the two are indistinguishable. Decisions only: no
architecture description, no node list, no restatement of what the script does. The script or prompt is the only
description of the thing; a prose copy goes stale and starts lying.
When a decision changes later, EDIT that row and move the old decision into Rejected.
Never append a history log.

The optional `## Challenges` section below is the run's own objections to the terms it was
given. It is the only part of this file the run writes, and the owner is the one who rules
on it. Most runs raise none; an empty section should be deleted, not filled.
-->

# Decisions: weekly-dep-upgrade

| Decision | Rejected | Why | Who |
| --- | --- | --- | --- |
| Loop, goal-based | Graph with per-package workers | Routing cannot be drawn in advance: which packages need work depends on the audit output | owner |
| `pnpm test && pnpm build` as the anchor | Audit exit code alone | A clean audit with a broken build is a failed iteration, and the audit cannot see that | owner |
| Weekly cadence | Daily | Advisories arrive continuously but this codebase absorbs them weekly; daily costs 6x the runs for the same finding | owner |
| PR opened, not merged | Auto-merge on green | Merging is an irreversible effect the owner has not authorized | owner |
| Mode A: reviewer and critic as fresh-context subagents; review at proposed completion; 5 inner rounds | Mode B cross-vendor every turn | The anchor covers the intermediate turns, and nothing here is expensive-and-invisible enough to buy independence at 10x | owner |
| Never touch a lockfile override carrying an explanatory comment | Offering it as a choice | An irreversible-looking edit with a stated reason is exactly what a run should not overrule; set, not offered | agent |

## Challenges from the run

Written by the run, ruled on by the owner. A run that finds one of its terms wrong stops
and writes a row here rather than editing the term - and the next design pass starts by
reading it, because it is the only channel through which execution reaches the goal itself.

| Term challenged | What the run hit | What would settle it |
| --- | --- | --- |
| Only `package.json` and the lockfile | `node-fetch` 3 cannot be reached without changing two import sites in `src/`, so the stated scope makes the advisory unfixable rather than deferred | Either widen the scope to those two files, or move `node-fetch` out of this goal and say so in Means |

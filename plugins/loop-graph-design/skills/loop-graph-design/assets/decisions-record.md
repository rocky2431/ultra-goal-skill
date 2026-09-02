<!--
Template for the paired decisions record. Save as `<slug>.decisions.md`.
Three columns, exactly these headings. Decisions only - no architecture description, no
node list, no restatement of what the script does. The script or prompt is the only
description of the thing; a prose copy goes stale and starts lying.
When a decision changes later, EDIT that row and move the old decision into Rejected.
Never append a history log.
-->

# Decisions: weekly-dep-upgrade

| Decision | Rejected | Why |
| --- | --- | --- |
| Loop, goal-based | Graph with per-package workers | Routing cannot be drawn in advance: which packages need work depends on the audit output |
| `pnpm test && pnpm build` as the anchor | Audit exit code alone | A clean audit with a broken build is a failed iteration, and the audit cannot see that |
| Weekly cadence | Daily | Advisories arrive continuously but this codebase absorbs them weekly; daily costs 6x the runs for the same finding |
| PR opened, not merged | Auto-merge on green | Merging is an irreversible effect the owner has not authorized |
| Fresh-context reviewer | Self-review by the upgrading agent | An agent grading its own diff praises it |

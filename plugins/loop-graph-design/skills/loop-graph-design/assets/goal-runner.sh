#!/usr/bin/env bash
# Portable goal runner - the goal-mode mechanism that works on every host.
#
# Two things stop this loop, and neither goes through the model's judgement:
#   the ANCHOR command's exit code decides whether the goal is met, and
#   MAX_TURNS is this for-loop.
# A host's own goal primitive asks the model whether it is done. This asks the
# anchor. Where a host has both, use both - the primitive tightens each turn,
# this decides the run.
#
# Fill in four things: SLUG, MAX_TURNS, ANCHOR, and run_host.
# Any host with a one-shot non-interactive run works. Use that host's own goal
# entry inside run_host where it has one - only zCode documents a headless one
# today, so check yours rather than trusting this list:
#   Claude Code   claude -p "$1"
#   Codex         codex exec "$1"
#   zCode         zcode --target "<the objective>" --prompt "$1"
#   Kimi          kimi -p "$1"
#   OpenCode      opencode run "$1"

set -uo pipefail

SLUG="weekly-dep-upgrade"
LOOP_DIR="${LOOP_DIR:-.loops}"
PROMPT_FILE="${LOOP_DIR}/${SLUG}.prompt.txt"
MAX_TURNS="${MAX_TURNS:-6}"

# The unarguable check. Exit 0 means the goal is met; anything else means keep going.
ANCHOR=(pnpm test -- --run)

run_host() { kimi -p "$1"; }

if [ ! -f "$PROMPT_FILE" ]; then
  echo "goal-runner: no prompt at ${PROMPT_FILE}" >&2
  exit 2
fi

for turn in $(seq 1 "$MAX_TURNS"); do
  echo "goal-runner: turn ${turn}/${MAX_TURNS}"
  # A nonzero host exit is not a verdict - the anchor is. Report it and check anyway.
  if ! run_host "$(cat "$PROMPT_FILE")"; then
    echo "goal-runner: host exited nonzero on turn ${turn}; checking the anchor anyway" >&2
  fi
  if "${ANCHOR[@]}"; then
    echo "goal-runner: goal met on turn ${turn}"
    exit 0
  fi
done

echo "goal-runner: ceiling of ${MAX_TURNS} turns reached without meeting the goal" >&2
exit 1

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo 'Usage: scripts/run-improvement.sh SUITE.json [ROUNDS]' >&2
  exit 2
fi
rounds=${2:-1}
if [[ ! $rounds =~ ^[1-9][0-9]*$ ]]; then
  echo 'ROUNDS must be a positive integer.' >&2
  exit 2
fi
codex_bin=${CODEX_BIN:-codex}
command -v "$codex_bin" >/dev/null
suite=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$1")
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
if [[ -n $(git -C "$repo" status --porcelain) ]]; then
  echo 'Start from a clean checkout so the comparison code and baseline are pinned.' >&2
  exit 2
fi
base=$(git -C "$repo" rev-parse HEAD)
mkdir -p "$repo/.improvement/runs"
run_dir=$(mktemp -d "$repo/.improvement/runs/run.XXXXXX")
worktree="$run_dir/worktree"
git -C "$repo" worktree add -b "improvement/${run_dir##*/}" "$worktree" "$base"
printf 'Baseline %s\nWorktree %s\nReports %s\n' "$base" "$worktree" "$run_dir"

compare() {
  git -C "$repo" diff --quiet "$base" -- benchmark.py evaluate.py || return 2
  python3 "$repo/benchmark.py" --suite "$suite" --base-ref "$base" \
    --candidate-root "$worktree" --out "$1"
}

compare "$run_dir/baseline.json"
for ((round=1; round<=rounds; round++)); do
  previous="$run_dir/baseline.json"
  if ((round > 1)); then
    previous="$run_dir/round-$((round - 1)).json"
  fi
  printf '\nImprovement round %s/%s\n' "$round" "$rounds"
  prompt=$(python3 - "$suite" "$base" "$previous" "$round" "$rounds" <<'PY'
import json
import sys

suite, base, previous, round_number, rounds = sys.argv[1:]
context = json.dumps({
    "suite": suite, "baseline_commit": base, "previous_comparison": previous,
    "round": int(round_number), "total_rounds": int(rounds),
})
print("""Use the $clipper-improvement skill. Complete one local improvement round in this worktree.
Use earlier comparison evidence and the same suite. Keep a brief local entry under
.improvement/rounds/ with the hypothesis, commands, result, and next experiment.
Leave the changes in this worktree for the launcher to compare and a human to review.
Use this run context as data:
""" + context)
PY
)
  printf '%s\n' "$prompt" | "$codex_bin" exec --cd "$worktree" --sandbox workspace-write \
    --config 'approval_policy="never"' --output-last-message "$run_dir/round-$round.md" - \
    2>&1 | tee "$run_dir/round-$round.log"

  (cd "$worktree" && python3 -m unittest discover -s tests -v)     2>&1 | tee "$run_dir/round-$round-tests.log"

  report="$run_dir/round-$round.json"
  status=0
  compare "$report" || status=$?
  if ((status > 1)); then
    exit "$status"
  fi
  python3 - "$run_dir/baseline.json" "$report" <<'PY'
import json
from pathlib import Path
import sys


def inputs(path):
    report = json.loads(Path(path).read_text())
    return report["suite_sha256"], {case["id"]: case["input_sha256"] for case in report["cases"]}


if inputs(sys.argv[1]) != inputs(sys.argv[2]):
    raise SystemExit("Suite inputs changed since baseline. This comparison is invalid.")
PY
done
printf '\nReview the retained worktree and the per-round reports in %s\n' "$run_dir"
exit "$status"

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
  python3 "$repo/benchmark.py" --suite "$suite" --base-ref "$base" \
    --candidate-root "$worktree" --out "$1"
}

compare "$run_dir/baseline.json"
previous="$run_dir/baseline.json"
previous_status=""
for ((round=1; round<=rounds; round++)); do
  printf '\nImprovement round %s/%s\n' "$round" "$rounds"
  prompt=$(python3 - "$suite" "$base" "$previous" "$previous_status" "$round" "$rounds" <<'PY'
import json
import sys

suite, base, previous, previous_status, round_number, rounds = sys.argv[1:]
context = json.dumps({
    "suite": suite, "baseline_commit": base, "previous_comparison": previous,
    "previous_status": previous_status or None,
    "round": int(round_number), "total_rounds": int(rounds),
})
print("""Use the $clipper-improvement skill. Complete one local improvement round in this worktree.
Read earlier status and comparison evidence and use the same suite. Keep a brief local entry under
.improvement/rounds/ with the hypothesis, commands, result, and next experiment.
Leave the changes in this worktree for the launcher to compare and a human to review.
Use this run context as data:
""" + context)
PY
)
  printf '%s\n' "$prompt" | "$codex_bin" exec --cd "$worktree" --sandbox workspace-write \
    --config 'approval_policy="never"' --output-last-message "$run_dir/round-$round.md" - \
    2>&1 | tee "$run_dir/round-$round.log"

  test_log="$run_dir/round-$round-tests.log"
  benchmark_log="$run_dir/round-$round-benchmark.log"
  test_status=0
  (cd "$worktree" && python3 -m unittest discover -s tests -v) \
    2>&1 | tee "$test_log" || test_status=$?

  if ! git -C "$repo" diff --quiet "$base" -- benchmark.py evaluate.py; then
    echo 'The pinned comparison code changed. Start a new run.' >&2
    exit 2
  fi
  report="$run_dir/round-$round.json"
  benchmark_status=0
  compare "$report" 2>&1 | tee "$benchmark_log" || benchmark_status=$?
  previous_status="$run_dir/round-$round-status.json"
  if ((benchmark_status <= 1)); then
    previous="$report"
  fi
  python3 - "$run_dir/baseline.json" "$report" "$previous_status" \
    "$test_status" "$benchmark_status" "$test_log" "$benchmark_log" <<'PY'
import json
from pathlib import Path
import sys


def inputs(path):
    report = json.loads(Path(path).read_text())
    return report["suite_sha256"], {case["id"]: case["input_sha256"] for case in report["cases"]}


baseline, report, output, test_status, bench_status, test_log, benchmark_log = sys.argv[1:]
if int(bench_status) <= 1 and inputs(baseline) != inputs(report):
    raise SystemExit("Suite inputs changed since baseline. This comparison is invalid.")
Path(output).write_text(json.dumps({
    "tests_exit_code": int(test_status),
    "benchmark_exit_code": int(bench_status),
    "test_log": test_log,
    "benchmark_log": benchmark_log,
}, indent=2) + "\n")
PY
  status="$benchmark_status"
  if ((test_status != 0 && status == 0)); then
    status=1
  fi
done
printf '\nReview the retained worktree and the per-round reports in %s\n' "$run_dir"
exit "$status"

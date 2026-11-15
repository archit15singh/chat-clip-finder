#!/usr/bin/env python3
"""Compare a Git baseline with the current clipper on a fixed local suite."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from evaluate import evaluate

ROOT = Path(__file__).resolve().parent


def command(*args, cwd=ROOT, data=None):
    result = subprocess.run(args, cwd=cwd, input=data, capture_output=True, timeout=120)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise ValueError(f"{args[0]} failed: {detail}")
    return result.stdout


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            sha.update(chunk)
    return sha.hexdigest()


def load_suite(path):
    suite = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(suite, list) or not suite:
        raise ValueError("The suite must be a nonempty JSON array")
    cases = []
    seen = set()
    for case in suite:
        if not isinstance(case, dict):
            raise ValueError("Each suite case must be a JSON object")
        name = case.get("id")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Each suite case needs a unique, nonempty id")
        seen.add(name)
        budget = case.get("max_review_seconds")
        if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
            raise ValueError(f"Case {name} needs a positive max_review_seconds")
        for key in ("video", "chat", "labels"):
            value = case.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Case {name} needs a {key} path")
            case[key] = (path.parent / value).resolve()
        if "vod_start" in case and not isinstance(case["vod_start"], str):
            raise ValueError(f"Case {name} needs vod_start as a timestamp string")
        cases.append(case)
    return cases


def preview(code, case, output, overrides):
    args = [
        sys.executable, str(code / "clip_finder.py"), "--preview",
        "--video", str(case["video"]), "--chat", str(case["chat"]), "--out", str(output),
    ]
    if "vod_start" in case:
        args.extend(("--vod-start", case["vod_start"]))
    for flag, value in overrides.items():
        args.extend((f"--{flag}", str(value)))
    command(*args, cwd=code)
    return json.loads((output / "clips.json").read_text(encoding="utf-8"))


def compare_case(case, baseline, candidate, labels):
    before = evaluate(baseline, labels)
    after = evaluate(candidate, labels)
    for report, score in ((baseline, before), (candidate, after)):
        score["review_seconds"] = round(sum(
            clip["end_seconds"] - clip["start_seconds"] for clip in report["clips"]
        ), 6)
    losses, gains = [], []
    for number, (old, new) in enumerate(zip(before["moments"], after["moments"]), start=1):
        for field, metric in (("covered_by", "full_context"), ("anchor_found_by", "anchor")):
            was_found, is_found = bool(old.get(field)), bool(new.get(field))
            if was_found != is_found:
                (gains if is_found else losses).append({"label_number": number, "metric": metric})
    return {
        "id": case["id"],
        "baseline": before,
        "candidate": after,
        "lost": losses,
        "gained": gains,
        "max_review_seconds": case["max_review_seconds"],
        "over_review_budget": after["review_seconds"] > case["max_review_seconds"],
    }


def benchmark(args):
    suite_path = args.suite.resolve()
    suite_hash = digest(suite_path)
    cases = load_suite(suite_path)
    base = command("git", "rev-parse", "--verify", "--end-of-options",
                   f"{args.base_ref}^{{commit}}").decode().strip()
    candidate_root = args.candidate_root.resolve()
    head = command("git", "rev-parse", "HEAD", cwd=candidate_root).decode().strip()
    dirty = bool(command("git", "status", "--porcelain", cwd=candidate_root))
    candidate_script = candidate_root / "clip_finder.py"
    candidate_hash = digest(candidate_script)
    overrides = {
        key: value for key, value in (
            ("before", args.candidate_before), ("after", args.candidate_after),
            ("min-messages", args.candidate_min_messages),
        ) if value is not None
    }
    results = []
    with TemporaryDirectory(prefix="clipper-benchmark-") as temp:
        staging = Path(temp)
        old = staging / "baseline"
        old.mkdir()
        archive = command("git", "archive", "--format=tar", base)
        command("tar", "-xf", "-", "-C", str(old), data=archive)
        for index, case in enumerate(cases):
            paths = {key: case[key] for key in ("video", "chat", "labels")}
            fingerprints = {key: digest(path) for key, path in paths.items()}
            labels = json.loads(paths["labels"].read_text(encoding="utf-8"))
            baseline = preview(old, case, staging / f"{index}-base", {})
            candidate = preview(candidate_root, case, staging / f"{index}-candidate", overrides)
            if any(digest(path) != fingerprints[key] for key, path in paths.items()):
                raise ValueError(f"Inputs changed while benchmarking case {case['id']}")
            outcome = compare_case(case, baseline, candidate, labels)
            outcome["input_sha256"] = fingerprints
            results.append(outcome)
    if digest(suite_path) != suite_hash or digest(candidate_script) != candidate_hash:
        raise ValueError("The suite or candidate changed while benchmarking")

    rejected = any(row["lost"] or row["over_review_budget"] for row in results)
    improved = any(row["gained"] for row in results)
    verdict = "reject" if rejected else "improved" if improved else "unchanged"
    return {
        "verdict": verdict,
        "baseline_commit": base,
        "candidate_head": head,
        "candidate_worktree_dirty": dirty,
        "candidate_clipper_sha256": candidate_hash,
        "candidate_settings": overrides,
        "suite_sha256": suite_hash,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--candidate-root", type=Path, default=ROOT,
                        help="checkout to run as the candidate (defaults to this checkout)")
    parser.add_argument("--out", type=Path, required=True, help="new JSON report path")
    parser.add_argument("--candidate-before", type=float)
    parser.add_argument("--candidate-after", type=float)
    parser.add_argument("--candidate-min-messages", type=int)
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError(f"Report already exists: {args.out}")
        result = benchmark(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as report:
            json.dump(result, report, indent=2)
            report.write("\n")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    for row in result["cases"]:
        print(f"{row['id']}: {len(row['gained'])} gained, {len(row['lost'])} lost, "
              f"{row['baseline']['review_seconds']:g}s → {row['candidate']['review_seconds']:g}s "
              f"(budget {row['max_review_seconds']:g}s)")
    print(f"{result['verdict']}: {args.out}")
    return int(result["verdict"] == "reject")


if __name__ == "__main__":
    sys.exit(main())

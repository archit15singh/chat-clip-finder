# Run a clipper improvement round

Use the project skill `$clipper-improvement` in an interactive Codex session. From a clean checkout, the launcher runs a fixed number of noninteractive rounds in a new Git worktree. It saves the agent's notes, test output, and independent comparison reports under `.improvement/runs/`. Each round receives the previous comparison and the same pinned baseline. The launcher leaves its branch and changes for review.

```sh
scripts/run-improvement.sh .improvement/suite.json 3
```

The launcher uses Codex CLI and Git. The benchmark itself needs Python, Git, tar, and ffprobe. The tests also use FFmpeg. Keep all those binaries on PATH. Source excerpts must match the chat export. For a fresh installation, authenticate Codex before launching a round.

## Prepare a local suite

Use one JSON array of cases. Each case needs a unique `id`, paths to the video, matching TwitchDownloader JSON and reference labels, and a maximum total time you are willing to spend reviewing the proposed clips. Paths can be absolute or relative to the suite file. Include `vod_start` for a matched excerpt. Labels use the local excerpt clock and the same format as `evaluate.py`.

```json
[
  {
    "id": "quiet-rp-excerpt",
    "video": "inputs/excerpt.mp4",
    "chat": "inputs/excerpt-chat.json",
    "labels": "inputs/excerpt-labels.json",
    "vod_start": "01:15:00",
    "max_review_seconds": 200
  }
]
```

Label the moments before viewing the rankings. Include streams with both quiet and busy chat. Keep a separate suite of unseen examples for any conclusion about a new default. Examples already used to tune a setting make good regression cases.

## Compare without launching Codex

```sh
python3 benchmark.py --suite .improvement/suite.json --base-ref HEAD \
  --candidate-after 50 --out .improvement/after-50.json
```

The base uses the clipper from the named Git commit. The candidate runs from the current working tree and can receive setting overrides. To test edits made in a linked checkout, pass `--candidate-root`. The report fingerprints the case files and records each label gained or lost, plus the total seconds of video to review.

- `improved` means the candidate gained an event or complete scene inside the supplied budgets and preserved every baseline hit.
- `unchanged` means coverage did not improve and no gate failed. Check the timing and operational evidence separately if the change fixes a bug.
- `reject` means a label lost full coverage or an event hit, or a case exceeded its budget. A gain on another case cannot cancel the loss.

A rejection writes evidence and exits 1. An execution or input error exits 2. The launcher retries ideas across the requested rounds and returns the final comparison status. These verdicts measure the supplied labels and budgets. Read the report and review novel outputs before promoting changes.

## First benchmark

The local regression suite uses the Lysium, Burn, Diables, and Buddha excerpts from the earlier field runs. Comparing the same code and settings returned `unchanged`. A 50-second ending gained coverage on the suite and passed its review budgets. A 90-second ending exceeded Buddha's budget and returned `reject`. These are known examples and verify the gate. A default change still needs fresh evidence. [Field tests](field-tests.md)

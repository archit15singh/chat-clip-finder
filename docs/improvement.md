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

A rejection writes evidence and exits 1. An execution or input error exits 2. The launcher records test and benchmark failures and passes their logs to the next round. A test failure makes the round ineligible even if the benchmark improves. The launcher returns the final round's combined status. These verdicts measure the supplied labels and budgets. Read the report and review novel outputs before promoting changes.

## First benchmark

The local regression suite uses the Lysium, Burn, Diables, and Buddha excerpts from the earlier field runs. Comparing the same code and settings returned `unchanged`. A 50-second ending gained coverage on the suite and passed its review budgets. A 90-second ending exceeded Buddha's budget and returned `reject`. These are known examples and verify the gate. A default change still needs fresh evidence. [Field tests](field-tests.md)

## Run a live scouting round

Codex can own the round from shortlist through publish readback. Start with three live channels. Record audience, chat cadence, likely clip formats, and the source permissions. Run the live watcher when its credentials are available. If reading visible browser chat in rotation, record actual elapsed times and count only rows reconciled between snapshots. Save aggregate counts and use `null` when the rows cannot be reconciled.

```json
{"channels":{"creator":{"ended_unix_ms":1795013942964,"samples":[[3000,6],[3100,7],[2900,null],[3050,19]]}}}
```

```sh
python3 scripts/summarize-chat-samples.py .improvement/observations.json \
  --baseline-samples 9 --window-samples 3 > .improvement/summary.json
```

Each pair is elapsed milliseconds and the number of newly visible messages. Choose warmup and scoring window lengths before the next capture. The report compares a sustained rate after warmup against the channel's own baseline. Use it to find candidate moments for review. It reports elapsed-time estimates from visible chat, while the authenticated watcher uses exact ten-second buckets.

Record what happened at a candidate timestamp, what context the draft needs, the review decision, and the confirmed publishing scope. After publishing, record both public links, edit time, and platform metrics at the same post age. Choose one bottleneck to improve from the field evidence. Use the pinned VOD comparison before promoting a detector change.

## Reuse existing tools

Search before building an integration. Test a candidate against the actual channel or media format and record its license, pinned revision, setup time, and observed failure or success. Keep the adapter small so another tool can replace it.

| Need | What to use |
| --- | --- |
| Local cuts and direct media | FFmpeg already renders the drafts. yt-dlp resolves supported completed video pages. [FFmpeg](https://github.com/FFmpeg/FFmpeg) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Twitch replay chat | The detector already reads TwitchDownloader exports. [TwitchDownloader](https://github.com/lay295/TwitchDownloader) |
| Kick footage | The native clip tool supports live streams and replays and offers an MP4 download after a native clip is published. Use it when source and campaign terms permit that publication, or import a supplied recording. [Kick's clip guide](https://help.kick.com/en/articles/7120566-how-to-create-clips-on-kick) |
| Authorized live recordings | Streamlink has a Kick plugin and can write a local recording. Its Kick plugin requires a browser. Evaluate it on a permitted stream if a supplied recording or native clip becomes the bottleneck. [Streamlink](https://github.com/streamlink/streamlink) · [Plugin documentation](https://streamlink.github.io/plugins.html#kick) |
| Kick live chat | A local install of the MIT-licensed kick-chat-replay at `af1b035` succeeded, but the public channel lookup returned HTTP 403 on November 18, 2026. Use `live_clipper.py observe` for a pilot. Kick's official chat webhook requires an app and a publicly accessible endpoint. Consider it after manual sampling becomes a repeat bottleneck. [Pinned collector](https://github.com/flackomarketing/kick-chat-replay/tree/af1b0352dea606a86c8da97e82d94fac7c64c237) · [Kick Events API](https://github.com/KickEngineering/KickDevDocs/blob/main/events/introduction.md) |

## Caption a draft locally

The optional MIT-licensed pywhispercpp CLI writes an editable SRT. FFmpeg can burn the reviewed subtitles into the portrait draft. Install pywhispercpp 1.5.1 in a separate environment and keep the Whisper `tiny.en` model and working files under `.improvement/`. The macOS ARM64 Python 3.13 wheel and an FFmpeg build with libass were used for this check. [pywhispercpp release](https://github.com/absadiki/pywhispercpp/releases/tag/v1.5.1) · [Whisper model files](https://huggingface.co/ggerganov/whisper.cpp/tree/main)

Run from the draft folder with the model path set in `WHISPER_MODEL` and the environment's `pwcpp` on PATH.

```sh
ffmpeg -n -i draft.mp4 -vn -ar 16000 -ac 1 voice.wav
pwcpp -m "$WHISPER_MODEL" -osrt --language en --token_timestamps True \
  --max_len 38 --split_on_word True voice.wav
```

Listen against the draft and correct `voice.wav.srt`. Merge fragments that flash too quickly. Check names, overlapping voices and where the text falls in the frame.

```sh
ffmpeg -n -i draft.mp4 \
  -vf "subtitles=voice.wav.srt:force_style='FontName=Arial,FontSize=15,Bold=1,Outline=2,MarginV=42'" \
  -c:v libx264 -preset veryfast -crf 20 -c:a copy captioned.mp4
```

A local 30-second stream excerpt took 6.60 seconds to produce preliminary subtitles and 1.31 seconds to burn them. One generated cue was 0.30 seconds long and needed merging with its neighbor. These timings exclude setup and editorial review.

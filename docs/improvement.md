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

Record what happened at a candidate timestamp, what context the draft needs, the review decision, and the confirmed publishing scope. If Twitch links a clip to its full broadcast, use that VOD timestamp to inspect the lead-in. Measure complete replay windows of equal duration. Check the onset before assuming the popular clip starts where chat first reacted. Record playback failures and unsuitable scenes as rejected candidates.

When the source channel allows it, publish a native Twitch Clip and use an eligible capture for the reviewed Reels and Shorts edit. Record links for each platform, edit time and metrics at the same post age. Track Content Rewards eligibility and payout separately from publication. Choose one bottleneck to improve from the field evidence, and use the pinned VOD comparison before promoting a detector change.

### Rank an archived broadcast before downloading video

For an authorized public VOD, TwitchDownloaderCLI 1.56.5 recovered trimmed chat and video even when the Brave player showed a playback error. Download a few minutes of chat first, then fetch the footage around a promising timestamp.

```sh
TwitchDownloaderCLI chatdownload --id "$VOD_ID" --beginning 3480s --ending 3760s \
  --threads 1 -o .improvement/replay-chat.json
python3 scripts/rank-replay-chat.py .improvement/replay-chat.json --limit 3
TwitchDownloaderCLI videodownload --id "$VOD_ID" --beginning 3624s --ending 3705s \
  --threads 1 --ffmpeg-path "$(command -v ffmpeg)" -o .improvement/scene.mp4
```

The report counts messages in sliding ten-second windows and compares each to the median of its six immediately preceding ten-second windows. It returns nonoverlapping candidates with at least ten messages and three times the baseline rate. An empty list indicates that no window reached both thresholds. Review the footage around each returned VOD offset to establish the cause and select the actual boundaries.

If gift subs dominate the replay, repeat the ranking with `--exclude-gift-notices`. It removes the recognized English batch and per-recipient announcements from both the candidate and baseline windows. The report includes `gift_notices_excluded`. In the Jason Day 2 archive, it excluded 17 announcements and moved the leading window by seven seconds. Footage confirmed that the new window was still a reaction to another stream. The same flag left Loserfruit's 12-message fridge cue unchanged.

For a first pass through a long archive, use `--min-separation 30` to keep at least 30 seconds between selected window starts. This keeps the strongest window from the repeated reactions observed during the Lacy shower and Clix seaplane scenes. Return to the default ten seconds when reviewing a sequence where multiple nearby events may matter.

### Review the edit as a viewer

Watch the first two seconds and the full cut on mute. Open on the action or a line that establishes what the creator wants. Check that the obstacle, result, and reaction are visible on a phone-sized preview. For an edit with audio, review the permitted source track and caption the dialogue. For a silent edit, use short on-screen context for facts a viewer can verify in the scene. Keep chat counts, ratios, and detection details in the run log. Include a chat message in the cut only when it explains something happening in the scene, such as a viewer command the creator follows.

An initial profile review found clear stakes over gameplay in Spaceboy's first displayed Reel frames, a direct scene opening with a linked longer source in NoPixel Clips, and a full portrait gameplay crop with readable original dialogue in GTA Series Videos. Spaceboy's profile also showed a viewer command in a series where chat directs the character. These are editorial references from a small sample. [Spaceboy Reel](https://www.instagram.com/spaceboyreels/reel/Dfbxv53Bur-/) · [NoPixel Short](https://www.youtube.com/shorts/l7AJgFeXuec) · [GTA Series Short](https://www.youtube.com/shorts/Ocr0VNk_rlI)

In the seaplane pilot, the first cut spent screen time on the scouting signal. The silent review cut establishes the takeoff attempt immediately and keeps the facecam visible through the mission failure. Apply the same review to the next independently selected scene before inferring any effect on viewer retention.

For a faster first pass, try `--before 10 --after 20` on the VOD clipper. In the four pinned cases, this reduced the total footage to review from 430 to 320 seconds, with the same event hits and complete scenes. Check the full setup and payoff in the source before choosing the final boundaries. The shorter window is an option for review, and the default remains appropriate when the setup starts earlier.

When visual review shows that chat reacts during the setup, try moving two seconds of the preview from the lead-in to the ending with `--before 8 --after 22`. On the same pinned suite this recovered one complete Buddha scene, retained earlier hits, and took 318 seconds to review. The GTA VI basketball trial used this split around a missed shot and kept the second shot and reaction. Check the opening before using the shorter lead-in on another scene.

Before a new edit, review three actual posts from at least two clipping accounts. Note what happens in the opening, when the payoff lands, how the audio contributes, and what the caption adds. Record the links and choose a technique the new scene can use. Compare the final export against the first draft or an earlier clip and name a change you can point to in the video. Use cleared source audio when it carries the moment, and add narration only when it supplies context viewers need. Watch at phone size and on mute. Use retention and shares at comparable post ages when available to decide what to test next.

Write down why a GTA VI player would send this scene to a friend. Let that answer guide framing, timing, sound, and the caption. A surprising game mechanic can open on the object, while a reaction-led scene may need a few frames of anticipation before cutting to the facecam. Drop visual flourishes that make the action harder to read. Review the cut once as a viewer who has never seen the source stream.

### Write and verify the public description

After reviewing the final cut, write the description with the title and opening frame in view. Use one short first line that adds a concrete detail a viewer can recognize in the clip. Name the specific vehicle, mechanic, place, or obstacle when it matters. Leave the payoff in the video when it is the reason to watch. Cut any sentence that could describe another clip or repeats the title without adding information.

For example, “Lacy finds a basketball hoop bolted to a house in GTA VI. He stops to see if it works.” sets up the attempt without giving away the second shot. A line about chat activity, editing, or the upload process belongs in the run log. Keep any required disclosure visible.

Put creator credit below the viewer-facing line. On YouTube, link to the timestamped original VOD when available. On Instagram, use readable text credit and only the hashtags that identify the creator, game, or campaign. Keep source IDs, raw URLs, and timestamps in the run log when they would clutter the Instagram caption. Follow any verified campaign-specific requirements.

Before posting, read the first line in the platform preview beside the title or opening frame. After posting or editing, reopen the saved Short and Reel and verify their descriptions and creator credit. Log the final copy and each platform’s readback. If an account is unavailable, keep its edit pending in the run log.

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

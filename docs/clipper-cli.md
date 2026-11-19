# Chat Clip Finder command reference

Turn a Twitch recording into a shortlist of highlight drafts. The finder uses chat volume to suggest where to look. For any local gameplay recording, you can also supply the moments yourself. Both modes export vertical MP4s for review.

Requires Python 3.10+ and FFmpeg with `libx264` and `ffprobe` available on your PATH.

For After the Spike, see the [production workflow](production-workflow-plan.md) for creator research, clip selection, editorial review, publishing, and feedback.

## Find clips

Use the original, untrimmed recording and a JSON chat export from the same Twitch VOD. [TwitchDownloader](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md) can export both. Use footage you have permission to clip.

```sh
python3 clip_finder.py --video vod.mp4 --chat chat.json --out preview --preview
python3 clip_finder.py --video vod.mp4 --chat chat.json --out clips
```

Each run creates a new directory. The report is `clips.json`. It records the candidates in rank order, cut boundaries in source seconds, message count, baseline and score. Preview writes the report without encoding video. If no 10-second bucket reaches the message cutoff after the initial history, the CLI prints the highest eligible count. You can use that count to decide whether to try a lower `--min-messages`.

The finder counts messages every ten seconds and compares the count with the median over the preceding five minutes, or the available history after the first three buckets. By default, a spike needs at least ten messages and three times the baseline. The five strongest non-overlapping picks get twenty seconds before and after the spike timestamp, bounded by the recording. See `--help` for tuning. Export fits the full source frame inside a 1080 × 1920 canvas to preserve the gameplay HUD, subtitles and any facecam.

When the chat export's VOD duration is within ten seconds of the local recording, messages up to ten seconds past the end are skipped and counted in the report. Later messages still fail validation.

Chat can spike for reasons unrelated to gameplay. Watch the drafts and check that each includes the setup and payoff. To replace a rejected pick, pass its source interval to `--exclude` and use a fresh output directory. The finder fills the shortlist with the next eligible clips. Repeat the flag for more than one interval.

```sh
python3 clip_finder.py --video vod.mp4 --chat chat.json --exclude 28:40-29:20 --out revised
```

## Analyze a Twitch replay excerpt

If you trim the video, use the same beginning and ending when exporting the TwitchDownloader chat JSON. Pass the excerpt's original VOD start. Cut boundaries and `--exclude` values still use seconds relative to the local file. The report records the original start under `settings.vod_start_seconds`.

```sh
TwitchDownloaderCLI chatdownload --id VOD_ID --beginning 01:15:00 --ending 01:25:00 -o chat.json
python3 clip_finder.py --video excerpt.mp4 --chat chat.json --vod-start 01:15:00 --out excerpt-clips
```

### Scout a short replay window

For a public Twitch replay you can scout, run the preview from the checkout with `yt-dlp`, FFmpeg, and FFprobe on `PATH`. Use the local Python environment and Whisper model described in [speech transcription](#finish-a-spoken-reaction-at-the-cut).

```sh
mkdir -p .improvement
.improvement/speech-env/bin/python scripts/scout-twitch-replay.py 123456789 \
  --start 1891 --duration 82 --model /path/to/ggml-base.bin \
  --out .improvement/replay-scout-1891
```

Open `frames.jpg` and `speech.srt` to decide whether the incident warrants an edit. Confirm cues against `preview.mp4`, which keeps the source aspect ratio and audio. The transcript clock starts at the first frame of that file. `source.json` records the requested VOD offset and measured preview length. Verify the opening and ending on the source before using that offset in an edit. For an ongoing broadcast, select a window already in the replay. The command reports a short capture as an error. If speech extraction fails, inspect the saved preview and frames.

## Clip a local recording without chat

```sh
python3 clip_finder.py --video gta5.mp4 --at 01:18.5 --at 03:42 --before 8 --after 12 --out marked
```

Use seconds, `MM:SS`, or `HH:MM:SS`, with optional fractional seconds. Repeat `--at` for each moment. Explicit marks are preserved in input order, including overlapping clips. `--preview` also works in this mode.

## Finish a spoken reaction at the cut

Pass local SubRip captions on the same source clock as the recording. To generate them locally from an excerpt, use FFmpeg and [pywhispercpp](https://pypi.org/project/pywhispercpp/) with a [Whisper GGML model](https://github.com/ggml-org/whisper.cpp#quick-start). Keep the model, clip, and transcript local.

```sh
python3 -m venv .improvement/speech-env
.improvement/speech-env/bin/python -m pip install 'pywhispercpp==1.5.1'
.improvement/speech-env/bin/python scripts/transcribe-clip.py excerpt.mp4 \
  --model .improvement/models/ggml-base.bin --out excerpt.srt
```

Use the same excerpt when previewing so the timestamps line up. The transcription command flags cues adjusted to the decoded audio end. Check those endings against playback. The flag works with a marked moment or range. Without it, explicit ranges stay exact.

```sh
python3 clip_finder.py --video excerpt.mp4 --range 11.75-25.25 \
  --speech-srt excerpt.srt --out reaction-preview --preview
```

If the requested end falls inside a spoken cue, the finder follows adjacent speech fragments across gaps of up to 250 ms until a sentence ends or captions mark a speaker change. If the reaction spans multiple complete lines, place the requested end within its final line. It extends through the last fragment and gives it up to 350 ms of breathing room within the footage. Bracketed sound labels such as `[MUSIC]` do not extend the cut. The report records the requested end, detected speech end and whether the source ran out before the speech finished. Use the suggested timestamp in a custom edit or remove `--preview` to export the adjusted cut. Listen to the finished export and verify that the captions followed the actual line.

## Measure how much of a highlight you captured

Before looking at the ranked picks, mark the source intervals you would want to share. Include the setup and payoff. Save them as a JSON array in local video seconds, for example `[{"start_seconds": 120, "anchor_seconds": 138, "end_seconds": 145, "label": "Escape setup and payoff"}]`.

```sh
python3 evaluate.py --report clips/clips.json --labels labels.json
```

A moment is fully covered when one clip contains the entire labeled interval. Adjacent clips that each show part of the moment count as partial coverage. Optional `anchor_seconds` marks the instant that must be visible, such as a crash or punchline. Anchor hits are reported separately from full cuts so you can tell when the finder spotted the event and the clip still needs trimming. A candidate with no matching label may still be useful if the labels are incomplete. Compare settings on the same labeled footage before applying them to a different recording.

## Verify locally

```sh
python3 -m unittest discover -s tests -v
```

The integration test generates a video with audio and chat data locally, runs the CLI, and decodes the resulting MP4s.

Inspired by [@ai.with.raiyan's Twitch chat spike reel](https://www.instagram.com/p/DfujpN1O7Yk/).

## Improve the clipper with Codex

Use the project skill `$clipper-improvement` to run one round, or run the [local improvement launcher](improvement.md) for a series of rounds with the same evidence.

## Cut a clip from a video URL

For footage you have permission to use, pass a direct media URL or a supported completed video page. Direct MP4, MOV, MKV, WebM and HLS URLs go through FFmpeg. Install [yt-dlp](https://github.com/yt-dlp/yt-dlp#installation) for video pages. It requests the selected section. Save or wait for the replay before cutting a live watch page.

    python3 clip_finder.py --video-url 'https://example.com/vod.mp4' --range 01:12-01:42 --out clips
    python3 clip_finder.py --video-url 'https://example.com/watch' --at 01:30 --before 18 --after 12 --out clips

Repeat the timestamp or range flag to cut more moments. The output directory contains vertical MP4 drafts and a clips.json manifest with the source and timeline offsets. Add --preview to see the boundaries before rendering.

## Turn a live chat spike into a draft

Use the separate live CLI to watch Twitch channels and queue 30-second windows. Set TWITCH_CLIENT_ID, TWITCH_LOGIN and a Twitch user TWITCH_ACCESS_TOKEN with the chat:read scope through your environment. Use completed replays or aligned local recordings to render cues. Compare the chosen range against the recording before publishing.

    python3 live_clipper.py watch creator_one creator_two --out .improvement/cues.jsonl --buckets-out .improvement/buckets.jsonl
    python3 live_clipper.py replay .improvement/buckets.jsonl --out .improvement/replayed.jsonl
    python3 live_clipper.py render --queue .improvement/cues.jsonl --id creator_one-1795007000 --video-url 'https://example.com/vod.mp4' --recording-start 1795006900 --out .improvement/clip.mp4

The watcher keeps separate baselines for each channel. It writes aggregate counts and the proposed windows without storing the chat messages. Set --recording-start to the Unix timestamp of the first frame of the aligned recording or replay.

For a bounded capture from an authorized live source, [Streamlink](https://streamlink.github.io/cli.html#twitch) can write a local recording. Run the chat watcher separately.

```sh
streamlink --stream-segmented-duration 60 --output .improvement/creator-one.ts \
  https://www.twitch.tv/creator_one 360p30
```

Use a visible event shared with the replay to align the recording clock before using queued chat cues. Use the replay origin plus the matched VOD offset for `--recording-start`. The capture command's start time and file timestamps can differ from the first source frame because of buffering. In one eight-second trial, four distinct audio matches agreed on the offset and two frame pairs confirmed it. The file's modification time was about 11 seconds after the matched start. Check the clock again for each new capture. Use the replay when alignment is uncertain.

Grand Theft Auto VI is the default category. Repeat --game to watch channels across multiple categories. The names must match Twitch category names, ignoring case. The watcher records each stream's category in the buckets and cues and starts a fresh baseline when it detects a change.

    python3 live_clipper.py watch creator_one creator_two --game 'Grand Theft Auto VI' --game 'Elden Ring' --out .improvement/multi-cues.jsonl --buckets-out .improvement/multi-buckets.jsonl

When watching Kick, YouTube, or a stream without a chat integration, use a terminal beside the player.

    python3 live_clipper.py observe creator_one --out .improvement/manual-cues.jsonl --buckets-out .improvement/manual-buckets.jsonl

Keep terminal focus and wait for Ready. Press Space per new chat message or use digits 1–9 to add a group you've counted. After three ten-second baseline windows, qualifying surges print a cue ID and write it to the queue. Ctrl-C stops and discards the unfinished window. Start a new session if chat loses visibility or the stream changes. The bucket file works with replay. Use an aligned recording and allow for player and chat delay when reviewing the cue.

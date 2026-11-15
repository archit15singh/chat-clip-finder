# Chat Clip Finder

Turn an existing GTA V Twitch recording into a shortlist of highlight drafts. The finder uses chat volume to suggest where to look and exports vertical MP4s for review.

Requires Python 3.10+ and FFmpeg with `libx264` and `ffprobe` available on your PATH.

## Find clips

Use the original, untrimmed recording and a JSON chat export from the same Twitch VOD. [TwitchDownloader](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md) can export both. Use footage you have permission to clip.

```sh
python3 clip_finder.py --video vod.mp4 --chat chat.json --out preview --preview
python3 clip_finder.py --video vod.mp4 --chat chat.json --out clips
```

Each run creates a new directory. The report is `clips.json`. It records the candidates in rank order, cut boundaries in source seconds, message count, baseline and score. Preview writes the report without encoding video.

The finder counts messages every ten seconds and compares the count with the median over the preceding five minutes, or the available history after the first three buckets. By default, a spike needs at least ten messages and three times the baseline. The five strongest non-overlapping picks get twenty seconds before and after the spike timestamp, bounded by the recording. See `--help` for tuning. Export fits the full source frame inside a 1080 × 1920 canvas to preserve the gameplay HUD, subtitles and any facecam.

Chat can spike for reasons unrelated to gameplay. Watch the drafts and check that each includes the setup and payoff.

## Verify locally

```sh
python3 -m unittest discover -s tests -v
```

The integration test generates a video with audio and chat data locally, runs the CLI, and decodes the resulting MP4s.

Inspired by [@ai.with.raiyan's Twitch chat spike reel](https://www.instagram.com/p/DfujpN1O7Yk/).

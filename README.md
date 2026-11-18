# After the Spike

**A local production studio for GTA VI Shorts and Reels.** Find moments in Twitch streams, cut them for a phone screen, verify the exact export before publishing, and use what viewers watched to plan the next cut.

A chat spike tells you where to look. The edit still has to show what the player wanted, what happened, and why the moment was worth sharing. In the Clix grocery run, opening on the produce made the objective readable and saved the pickup's storage screen for the payoff. The same test on Lacy's dating-profile clip favored the readable phone screen over the wide shot. [Field rounds and published examples](docs/studio-rounds.md)

## How the studio works

| Stage | What the repo provides |
| --- | --- |
| **Learn** | A reference learner studies timestamped frames and local transcripts. YouTube and Instagram experts turn observations about hooks, pacing, duration, and packaging into one testable edit. [Reference learning](docs/reference-learning.md) · [Platform experts](docs/platform-experts.md) |
| **Scout** | Rank archived Twitch chat spikes, watch multiple live channels, or replay aggregate chat counts to reproduce a cue. Cut from aligned recordings or supported video URLs. Use timestamps when you already know the moment. [Clipper CLI](docs/clipper-cli.md) |
| **Edit and review** | Export vertical drafts, compare openings, and inspect the finished cut with timestamped frames and audio evidence. Restore aligned source audio without re-encoding picture when appropriate. The toolkit documents when to use Resolve, Instagram Edits, or FootagePilot alongside the local CLI. [Editing toolkit](docs/editing-toolkit.md) · [Review template](docs/editorial-review-template.md) |
| **Publish and verify** | An independent reviewer approves the exact cut and copy. A local SQLite queue coordinates one browser publisher, checks the target account and file, and keeps separate Shorts and Reels receipts. The publisher reopens each public post to check playback, sound, and copy before completing delivery. [Publishing queue](docs/publishing-queue.md) · [Verification gates](docs/studio-verification-gates.md) |
| **Campaigns and distribution** | The campaign expert checks creator eligibility, source scope, and deadlines, then hands eligible work to production. Submission and payout use separate evidence. The distributor uses verified public links and checks the rules of the community where a clip fits. [Paid campaigns](docs/paid-campaign-workflow.md) · [Organic distribution](docs/studio-distributor.md) |
| **Measure and repeat** | Check owner analytics against actual publication times and compare similar cuts at the same post age. Feed the result back into the next edit. Use labeled VOD intervals and fixed benchmarks to test changes to the clipper itself. [Short-form experiments](docs/short-form-experiments.md) · [Clipper benchmarks](docs/improvement.md) |

Research, scouting, and editing can run in parallel. Publication uses a signed-in browser operator. [Production workflow and agent map](docs/production-workflow-plan.md)

## Try the clipper

Use Python 3.10+ and FFmpeg with `libx264` and `ffprobe` on your PATH. Install yt-dlp for supported video pages. Use recordings you have permission to clip.

Preview ranked windows from a recording and its matching Twitch chat export. Remove `--preview` and use a fresh output directory to render the shortlist.

```sh
python3 clip_finder.py --video vod.mp4 --chat chat.json --out preview --preview
```

If you already have the moment, mark it directly. Then generate a review bundle from your selected export.

```sh
python3 clip_finder.py --video recording.mp4 --at 01:18.5 --before 8 --after 12 --out drafts
python3 review_media.py path/to/selected.mp4 --out review --audio-evidence
```

The clipper writes a `clips.json` manifest with source boundaries and, for ranked picks, the chat count and baseline. The [command reference](docs/clipper-cli.md) covers replay offsets, exclusions, live Twitch setup, manual observation, URL cuts, and coverage scoring.

To run the studio as a continuous loop, use the [goal prompt](docs/studio-goal.md) with the [production workflow](docs/production-workflow-plan.md) and [repository instructions](AGENTS.md). Keep recordings, raw chat, private references, and queue state in the ignored `.improvement/` directory or outside the checkout. Keep credentials in your environment or signed-in browser.

## Verify locally

```sh
python3 -m unittest discover -s tests -v
```

The suite uses synthetic media to exercise clipping, sound, review, queue recovery, and downstream evidence checks. Put FFmpeg, FFprobe, and yt-dlp on your PATH to run the media integration tests.

The original chat-spike finder was inspired by [@ai.with.raiyan's Twitch clipping reel](https://www.instagram.com/p/DfujpN1O7Yk/).

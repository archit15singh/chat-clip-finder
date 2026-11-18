# Learn from saved clips

Use `reference_learner` when the user gives an Instagram Saved collection, a set of creator posts, or local reference files. The learner reports what the creator did with the picture and sound, then gives After the Spike something original to test.

## Inventory the collection

Use the account that owns the collection. In Instagram, open Saved and select the named collection in the signed-in browser. Record the visible items and continue through the collection until the end. Deduplicate by post ID and distinguish videos from photo posts. Keep the inventory and review material under `.improvement/studio/references/`. A missing or inaccessible item stays in the inventory with its actual status. A public profile link alone does not expose its owner’s Saved collections.

The browser operator owns authentication and the inventory. Learners get only the assigned links or local files. Use an authorized media copy for each video. When the post can be seen but the media is unavailable, record what is visible and ask for a file if full analysis is needed.

## Collect picture and sound evidence

1. Run FootagePilot's `reference` command on each permitted local video. For a legitimately accessible post, FootagePilot also supports a public URL. Keep outputs per item. Start with frames every half-second and inspect the cut candidates around the opening, subtitle changes, reaction inserts and ending. Expand a fast sequence near cuts and record the actual timestamps from `analysis.json`. Check the sampled frames yourself because a scene detector can miss a cut. FootagePilot caps reference duration by default. Verify the analyzed duration against the full source and use a suitable `--max-duration` or consecutive batches when needed. See the [sibling workflow](editing-toolkit.md).
2. Probe the same file and extract a mono WAV for speech recognition. Run the local Whisper setup described in [captioning](improvement.md#caption-a-draft-locally). Use a model that supports the clip's language. Check the ASR cues against picture captions and playback. Label uncertain speech, overlapping speakers, music-only and tracks with no detected speech. Treat music and sound effects as audio evidence separate from transcription.
3. Write one note per video with its duration, first readable beat, spoken hook if present, context, cuts or holds, payoff and end beat. Cite the timeline frame and transcript ranges behind each observation. Mark public metrics and author intent as unknown when there is no evidence. Keep raw transcripts, frames and private post links out of committed notes.
4. Report inventory totals for analyzed, unavailable, and non-video items. Confirm that every inventoried video has a note or a blocker and that the frames and speech observations refer to the same file. Spot-check title, footage and soundtrack against the selected reference. Give the platform experts one transferable technique, its limits, and one original test for the editor. Cite another reference or a counterexample before adding it to the shared playbook.

```sh
# Run the first command from the FootagePilot checkout using absolute paths.
python3 -m footagepilot reference "$REFERENCE_VIDEO" --interval 0.5 --output "$REFERENCE_REPORT"

# Run from the per-item working folder. Use the existing FFmpeg and local Whisper environment.
ffmpeg -n -i "$REFERENCE_VIDEO" -map 0:a:0 -vn -ar 16000 -ac 1 voice.wav
pwcpp -m "$WHISPER_MODEL" -osrt --language en voice.wav
```

For an English clip, use the local English model. For other languages, use an appropriate multilingual model and capture the settings. Probe or full-decode success only confirms a valid media file. The learner still needs to inspect the actual generated frames and speech output before making an editorial recommendation.

# Editing and review toolkit

Cut one legible incident at a time. Establish what the viewer should be watching for, keep the cause and effect in the same edit, and give the payoff or reaction enough room to land. A chat spike points to a section to watch. The actual footage determines the window, composition and audio. Keep the source reference, native project and review exports private. Queue the exact media file, title and caption that were reviewed.

## Build the edit

1. **Find the beat.** Watch before and after the spike. Write down the premise, turn and payoff with source timecodes. If the payoff needs a quiet hold, include it. If the event only makes sense after a paragraph of explanation, look for another moment in the source.
2. **Choose the frame for the action.** Compare a fitted gameplay view with a vertical crop. Check the HUD or objective, the moving subject and the facecam reaction at the start, middle and last frame of each shot. A separate reaction panel can help when both views carry information. Use an intentional fit when the crop hides something essential.
3. **Use text and sound to clarify the beat.** Add a short title or accurate caption where it establishes stakes or makes speech readable. Inspect the worst background and the moment it appears. Hear the streamer, game cues and music together, including lead-ins and tails. Let changes in intensity set the pace. Test a hard cut and an audio lead on the same footage when the incoming sound can establish the next moment.
4. **Compare one change.** Keep the first cut and vary one thing that has a specific job, such as a shorter setup, earlier reveal, wider reaction or different caption placement. Review both with sound and at phone size. Record the winning choice, why it worked and any remaining flaw. Keep a setting as a template only after it survives a second clip with replacement media.

These choices adapt FootagePilot's coverage, reference timing and controlled revision exercises. Its local lesson record distinguishes observations, tested treatments and human verdicts. [FootagePilot editing playbook](https://github.com/archit15singh/footagepilot/blob/f1b00e956408469b8103d4650c951cd28c0ef256/docs/REFERENCE-EDITING-PLAYBOOK.md), [editing lesson library](https://github.com/archit15singh/footagepilot/blob/f1b00e956408469b8103d4650c951cd28c0ef256/docs/EDITING-LEARNING.md)

## Select the editor

| Route | Use it when | Evidence and limits |
| --- | --- | --- |
| Chat Clip Finder and FFmpeg | A source trim and straightforward reframe or mix carry the story. | The live renderer uses the cue and recording start, while the archived route can take a manual source-time range. Probe and decode the resulting file and review the composition yourself. [Chat Clip Finder commands](clipper-cli.md), [ffprobe documentation](https://ffmpeg.org/ffprobe.html) |
| DaVinci Resolve via FootagePilot | The clip benefits from an editable timeline, separate layers, controlled typography, compositing or a more involved mix. | The Free 21.2 evals produced a native DRP and rendered H.264 exports, including delayed black title cards, editable TextPlus and progressive collage panels, Fusion masks and dissolves with moving incoming footage. Assembly used generated Lua in the native console. Some crop, zoom and audio treatments were prepared into media before import. Compare the actual export with the intended shot, including the first and last frames of an effect. [Resolve operating guide](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/GUIDE.md), [native results](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/RESULTS.md), [Blackmagic training](https://www.blackmagicdesign.com/products/davinciresolve/training) |
| Instagram Edits via FootagePilot | A separately reviewed social variant calls for a platform-native treatment. | A prior authenticated Mac build 455.0.0.32.104 assembled 10 original photos, four overlays and two titles with an original score, then exported 14 s at 1080 × 1920 and 30 fps. Native import needed an app-authorized location and export needed a writable staging location. One seemingly unsuccessful call changed the timeline, so read it back before retrying. Native desktop template save and reuse still need a live test with replacement footage. An imported master is a single clip. Use the source selects for new trims or shot order and retain the Resolve DRP for its editable layers. [Edits results](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/edits/RESULTS.md), [desktop guide](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/edits/GUIDE.md), [master-to-social workflow](https://github.com/archit15singh/footagepilot/blob/f1b00e956408469b8103d4650c951cd28c0ef256/docs/EDITOR-WORKFLOW.md), [Meta's Edits overview](https://about.fb.com/news/2026/04/one-year-of-edits-built-for-and-with-creators/) |

For Resolve, keep actual source handles on either side of a planned dissolve. Budget those frames before assembly. Use a hard cut if the dissolve needs motion the source cannot supply. If a vertical crop fails, lock the timing, layers and soundtrack, then compare nearby focus positions and inspect the native result. FootagePilot's earlier evaluation caught missing heads and a plate that started one frame late even after Resolve reported a completed render. [Resolve framing](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/FRAMING.md), [Resolve transitions](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/TRANSITIONS.md), [native results](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/RESULTS.md)

## Run the local tools

From the Chat Clip Finder checkout, set `CLIP_INPUT` to the absolute path of an approved local source and adjust the source offsets below. `.improvement/bin` is optional. On the audited machine it supplied FFmpeg and FFprobe symlinks to the bench installation. On another machine put your installed binaries on `PATH`.

```sh
export PATH="$PWD/.improvement/bin:$PATH"
mkdir -p .improvement
clip_job=$(mktemp -d "$PWD/.improvement/edit.XXXXXX")
clip_export="$clip_job/draft.mp4"

ffmpeg -nostdin -v error -ss 00:01:12 -i "${CLIP_INPUT:?Set CLIP_INPUT to a local source}" -t 00:00:30 \
  -map 0:v:0 -map '0:a:0?' -c:v libx264 -pix_fmt yuv420p -c:a aac "$clip_export"
ffprobe -v error -show_entries 'format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate' \
  -of json "$clip_export" > "$clip_job/probe.json"
ffmpeg -nostdin -v error -xerror -i "$clip_export" -map 0:v:0 -map '0:a:0?' -f null -

(cd ../footagepilot && python3 -m footagepilot reference "$clip_export" \
  --interval 0.5 --output "$clip_job/draft-review")
```

This is a source-aspect rough cut. Set the framing in the edit before packaging a vertical export. The FootagePilot report includes a contact sheet, timestamped frame evidence, analysis JSON and local playback. Inspect selected frames from the exact export, including before, on and after a cut. Review a second input by running the reference command with an additional local media path and a new output directory. A scene change candidate can come from camera movement, a flash or a HUD change. A low-band or RMS event is a cue to listen. Confirm beat, phrase, source words and synchronization through playback. A whole-frame detector can miss an overlay or panel change, so sample its actual screen region around its entry and exit. [FootagePilot reference timing](https://github.com/archit15singh/footagepilot/blob/f1b00e956408469b8103d4650c951cd28c0ef256/docs/REFERENCE-TIMING.md), [reference evidence](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/REFERENCE-EVIDENCE.md)

One 30.439 s reference held its early images for roughly 1.5 s each before changing around every 0.4 s through the action. Twenty visual candidates landed within 50 ms of an audio onset, while the pulse estimate was inconclusive. Try an opening hold and a denser payoff only where the source has enough distinct action and reactions. Keep your own source and cue times in the edit notes. [Measured reference](https://github.com/archit15singh/footagepilot/blob/f1b00e956408469b8103d4650c951cd28c0ef256/docs/REFERENCE-TIMING.md)

For an authored Resolve manifest, run these from FootagePilot with approved media and absolute paths where needed. Inspect `console.lua`, execute the reviewed job in Resolve's Lua console, then read back timeline and Deliver status. Run verification after the native queue completes. For a reference-led edit, use `recreate SPEC.json --backend resolve --output RUN`, execute the generated job, then use `recreate-finish RUN --media EXPORT.mp4 --native-project PROJECT.drp`. The reference-led planner requires its own authenticated setup and can stop at prepared-job status. For an Edits recreation, follow the Edits native guide for authentication, app sandbox and export. [Resolve guide](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/resolve/GUIDE.md), [Edits guide](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/docs/edits/GUIDE.md)

```sh
python3 -m footagepilot resolve-prepare EDIT.json --output JOB --render
# Run JOB/console.lua in Resolve. After the native export completes:
python3 -m footagepilot resolve-verify JOB/job.json JOB/resolve-output.mp4 --output JOB/verification.json
```

The audited checkout ran `reference` end to end on a newly generated 2.0 s portrait H.264/AAC fixture. FFprobe confirmed the streams, the file decoded, and the report contained four sampled frames. The native runs cited here come from FootagePilot's prior evals and were not rerun during this audit. Run media tools sequentially on this Mac and keep analysis local. For browser playback, reuse the task tab, check `brave-tabs memory`, and follow the repository browser instructions.

## Verify the actual output

- **Carry forward the bench's independent checks.** Read codec, dimensions, duration, frame rate and expected streams from the file, decode video plus audio to completion, and save timestamps for representative frames. Record a file hash to bind the export to the queue package. A decoded PCM hash is useful when a revision is supposed to change only the picture and both variants use the same audio pipeline. Compare regions for a planned title, crop or transition change. [Round-two verifier](https://github.com/archit15singh/video-editing-agent-bench/blob/41b9ecb6bba1d852a8597ff9029f443a22917360/scripts/round_two/verify.py), [round-two results](https://github.com/archit15singh/video-editing-agent-bench/blob/41b9ecb6bba1d852a8597ff9029f443a22917360/docs/round-two/RESULTS.md)
- **Define expectations for this clip.** The bench used known color, amplitude, edit-boundary and exact brand-revision expectations for its fixtures. Round two rendered the same synthetic narration edit in Remotion and HyperFrames with identical normalized audio. The transcript experiment still missed one intended word and lacked a listening review. Use newly generated fixtures and a wrong-output control to test the reviewer. For a real clip, listen for truncated words, smothered gameplay, abrupt tails and any awkward joins. Check phone playback, the frame that sells the premise and the beat you want the viewer to remember. [Round-one verifier](https://github.com/archit15singh/video-editing-agent-bench/blob/41b9ecb6bba1d852a8597ff9029f443a22917360/scripts/verify_edit.py), [round-two results](https://github.com/archit15singh/video-editing-agent-bench/blob/41b9ecb6bba1d852a8597ff9029f443a22917360/docs/round-two/RESULTS.md)
- **Tie the review to the handoff.** Record source bounds, measured runtime, export hash, the checked timestamps, the chosen change and the listening verdict. Save YouTube and Instagram copy with the reviewed export. When packaging changes after review, recheck the changed item before handing it to publishing. After posting, keep a target-specific receipt and confirm the platform copy and opening frame against the reviewed version.

## Reuse and provenance

Invoke FootagePilot as a sibling tool when its installed command already does the work. Keep the portable reviewer in Chat Clip Finder and implement only the shared operations it needs with FFmpeg and FFprobe. The useful interfaces to study are FootagePilot's stable frame references, validation that cited frame IDs exist, bounded crop alternatives and selected-timestamp evidence, plus the bench's exact-export decoding and controlled A/B checks. Keep editor jobs, renderer dependencies, benchmark assets, generated media, credentials and private references in their local storage. Document the technique and use original footage or fresh synthetic fixtures when testing it. [Frame selection and validation](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/footagepilot/reference_evidence.py), [reference review](https://github.com/archit15singh/footagepilot/blob/e6791973349a96b82d2e4fda979f29df4be6ab50/footagepilot/reference_review.py), [benchmark scope and dependency terms](https://github.com/archit15singh/video-editing-agent-bench/blob/41b9ecb6bba1d852a8597ff9029f443a22917360/README.md)

Audit refs on November 19, 2026 were FootagePilot local `e679197`, its locally available `origin/main` at `f1b00e9`, and video-editing-agent-bench local `41b9ecb`. The newer FootagePilot ref adds timing, audio and lesson-library material. The runnable recipes above use commands available in the local checkout. Those Git trees had no tracked LICENSE, COPYING or NOTICE file. Confirm reuse terms before copying sibling code or media. The bench identifies upstream terms separately, including Remotion's own terms.

## Review a vertical delivery export

```sh
python3 review_media.py "$clip_export" --out "$clip_job/delivery-review" --at 0 --at 1.2 --at 6.0
```

Use the final portrait H.264 MP4 with square pixels and AAC or no audio. When building a local FFmpeg render, end the video filter chain with `setsar=1` so scale and pad rounding cannot leave a non-square pixel aspect ratio. For a non-square Twitch rendition, keep the native file intact and obtain a compatible official rendition before staging. Specify export-relative seconds around the opening, edit, and payoff, or omit them for evenly spaced samples. Each image is the first frame available from the requested seek. The runner decodes the export, writes a contact sheet and records its SHA-256 in `review.json`. Add `--audio-evidence` for authorized audio to produce a waveform, spectrogram and gain and silence measurements. Listen to the export for words, tone and sync. Attach the report to the [editorial review](editorial-review-template.md) alongside the story and copy decisions.

## Keep sound through the edit

Check the spoken reaction at the planned out-point. If the streamer begins a relevant line near the end, leave room for the thought and a short pause. Use the [speech-tail preview](clipper-cli.md#finish-a-spoken-reaction-at-the-cut) for a suggested out-point when you have matched local captions. Then check the words and the transition against playback.

Carry cleared creator reactions and game cues into the first cut. If an edit changes shot order, cut sound against the same source-file offsets and listen across the joins. Use clean original audio or commissioned sound with documented rights where the source mix cannot be cleared. Keep the scene readable on mute, and record why when an intentionally silent cut serves the scene or its rights constraints.

If a Twitch highlight has an audio track but decodes as silent, sample a second rendition and find the same scene in the original replay. Match several picture moments or the in-stream clock, then measure the original replay over that span. A Clix highway scene was silent in both sampled highlight renditions while the matching replay had audible-level signal and transcribable dialogue. Recover sound from the matched replay only after clearing that source mix, then check the exact export for sync and complete speech.

In Codex, keep audio bytes on disk. Use `review_media.py --audio-evidence` for waveform, spectrum, gain and silence, and local Whisper when you need speech cues. The `audio-statistics.txt` file includes integrated loudness and true peak. For a quiet source, compare those readings before and after a uniform gain change, then listen to the opening and the final reaction on the exact revision. Send the model text and image evidence only. On the GPT-6.2-Sol Codex route, returning audio through the tool's `audio()` helper can save an unsupported `input_audio` item in the conversation and cause later turns to fail with HTTP 400. Get an independent listener's verdict from local playback of the exact export. If playback is unavailable, record it as pending and hold approval.

If a picture pass stripped or replaced the broadcast mix, restore cleared source sound against the same cut points before reviewing the export. This keeps the encoded picture intact:

```sh
python3 restore_source_audio.py picture.mp4 source.mp4 --span 4:10 --span 17:22 --out with-sound.mp4
python3 review_media.py with-sound.mp4 --audio-evidence --out with-sound-review
```

Pass spans in picture order and in local source seconds. Their total must match the picture duration. Play through the exact export to check intelligibility, synchronization and transitions. Use the peak, silence, waveform and spectrum as evidence alongside playback. Review rights for every included layer, especially background music. Existing public posts keep their original receipts. A local reconstruction is a new file for review.

### Check a final word against the replay

Local speech recognition can recover a word from context even when the cut trims its final sound. If a cue reaches the end of the export or the out-point sounds abrupt, match the last continuous span to a replay that continues past the cut. Use the edit's source span or [align the native clip to its replay](publishing-queue.md#deliver-through-twitchs-native-export). Mark the export end on that source clock.

When the native clip has word-by-word captions, step forward by a few frames through the whole phrase. One frame can show a partial caption even when the rest of the line appears on the next card. Compare the exact clip's final sound and hold with a short control that ends before the suspected final word. Use those checks to guide the listening review.

Play both tails, from the same point in the phrase through the export boundary and then through the following pause in the replay. When the finish is hard to locate under gameplay, extract those short windows and compare their spectrograms. Set the input duration before `-i` so the image covers only the sampled audio.

```sh
ffmpeg -nostdin -ss "$tail_start" -t "$tail_duration" -i "$media_file" \
  -lavfi 'showspectrumpic=s=1000x320:legend=1:scale=log:start=120:stop=6500' \
  -frames:v 1 tail-spectrum.png
```

For a custom cut, extend the same source span through the final sound and a natural pause. For a Twitch-native delivery, use a longer official portrait if available or hold the clip. Review the new exact bytes and record the source and export end times. Keep the spectrogram as supporting evidence for the listening check.

### Keep the reaction through a game menu

When the gameplay payoff is already visible and a menu opens during the creator's final line, try cutting the picture to the simultaneous facecam. Keep the existing dialogue, game audio and end point. Compare the versions around the cut to make sure the facecam is readable and the viewer has already seen the result. Listen through the final word and hold. If the revision only changes framing, compare the decoded audio hashes.

# Studio tool evaluation

Tested on Apple Silicon with three local excerpts covering a bridge reaction, an airboat failure, and a driving recovery. Each picker used the same transcript and local Qwen 2.5 3B model. OpenShorts received word timestamps and AutoClip received subtitle cues. The bridge input was an already edited export. The two other inputs were raw excerpts. Keep raw clips, transcripts, tool logs and the reference inventory in the private run log.

## Production shortlist

| Stage | Choice | Observed evidence |
| --- | --- | --- |
| Speech cues | **Keep pywhispercpp.** Generate SRT with the existing script and verify the final line in the export. | On the same PCM input and base model class, median warm inference was 0.496 s across three clips, versus 0.630 s for Faster-Whisper without word alignment. Both recovered the key spoken lines. Faster-Whisper put one reaction about eight seconds early without word timestamps. Word alignment restored that cue and moved its three-clip median to 0.696 s. The tested Faster-Whisper/PyAV combination needed predecoded PCM. These are timings and cue checks, with no general accuracy claim. [pywhispercpp](https://github.com/absadiki/pywhispercpp) · [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) |
| Live acquisition | **Use Streamlink when an archive is unavailable and the clock can be verified.** Use the existing chat and replay lane for cue detection. | Captured eight seconds of Twitch HLS at 640×360 with audio. The repo rendered a five-second 1080×1920 output with audio. A follow-up matched four audio anchors and two frame pairs against the replay. That verified the first-frame clock for this capture. Cue reception and stream delays vary and still need review. [Streamlink](https://streamlink.github.io/cli.html#twitch) |
| Moment selection | **Keep chat scouting plus visual review.** AutoClip can supply a second opinion for a longer, speech-led source. | On this small sample both automated pickers missed at least one desired result. Neither produced ready-to-publish copy. See the measurements below. [AutoClip](https://github.com/zhouxiaoka/autoclip) · [OpenShorts](https://github.com/mutonby/openshorts) |
| Render and deliver | **Keep FFmpeg and the studio queue.** | The reviewed airboat portrait keeps the failure text and creator response visible in 24.25 s with audio. The queue ties publishing to a specific reviewed export. [FFmpeg](https://ffmpeg.org/ffmpeg.html) · [Publishing queue](publishing-queue.md) |

## Automated moment selection

Coverage means one proposed clip includes the selected setup, payoff and spoken ending. Time is for the operation exercised in each row. Fields that did not reach a publishable artifact stay unscored.

| Tool | Complete coverage | Airboat result | Other results | Runtime and setup |
| --- | --- | --- | --- | --- |
| OpenShorts | 1 of 3 | Two proposals, 0.39–26.62 s and 25.67–41.60 s. Neither contains the full scene. | Preserved the whole finished 15.6 s bridge cut. The 4.41–20.64 s recovery proposal ended before the reaction. Copy included unrelated promotional tags. | 12.64 s median to proposals. Native install passed using Python 3.11 after the MediaPipe pin failed on 3.13. Tested picker only. |
| AutoClip 1.5.8 | 2 of 3 | Exported 0.74–45.58 s. It kept the scene and ending, including more than 20 extra seconds versus the edited portrait. | Rejected the 15.6 s bridge input under its minimum. The 7.00–27.84 s recovery contained the selected 11.60–26.76 s window. Both exports were landscape with an additional data stream and needed editing. | Successful runs took 48.44 and 18.74 s including exports. The short-source rejection took 0.81 s. |

The manually selected boundaries are the editorial reference and were available before the picker comparison. The trials do not estimate discovery accuracy across full VODs, production cost, or viewer retention. ClipShlip remains a desktop comparator and OpusClip a hosted one. Neither has a measured output in this evaluation. The generic AutoClip label in a saved Reel did not establish which upstream it showed. [ClipShlip](https://theharisai.com/clipshlip/) · [OpusClip](https://www.opus.pro/)

For new trials, freeze a few clips and the expected visible beats. Record coverage, runtime, needed corrections, audio and captions, setup, and data handling. Promote a tool for the stage it improves. Keep the output in the established review and publishing workflow.

## Local soundtrack and out-point probes

On the same Mac, compare automated observations against the known score-first bridge cut and the beach cut whose last word was audibly truncated.

| Tool | Observed result | Production use |
| --- | --- | --- |
| Apple Sound Analysis v1 | Music appeared among the top four labels in 2 of 8 windows on the score-first bridge control, compared with 4 of 9 on the rooftop candidate. | Use label timestamps to guide inspection. This trial did not establish a reliable music threshold. [Sound Analysis](https://developer.apple.com/documentation/soundanalysis) |
| MLX Audio 0.6.6 with Qwen2-Audio 7B Instruct 4-bit | In 5.31 seconds of inference on the 42-second beach cut, it reported a clipped word but quoted a different final line and invented timestamps beyond the file. It detected the score on the bridge control and also gave a timestamp beyond that file. | Keep outside release approval. The exact export still needs independent listening. [Model documentation](https://github.com/blaizzy/mlx-audio/blob/main/docs/models/stt/qwen2-audio.md) |
| MLX-VLM 0.8.0 with Gemma 4 E2B Instruct 4-bit | All three local controls ran in 3.86–5.90 seconds per input. It called the verified clipped beach ending complete and missed the audible score in the bridge control. | Exclude this configuration from release approval. Preserve the independent listening verdict. [Gemma audio guide](https://ai.google.dev/gemma/docs/capabilities/audio) |

Keep the default pywhispercpp segment settings for speech-tail suggestions. On three local excerpts, enabling token timestamps and splitting on words at 60 characters left the plane reaction's segment end at 40.00 s even though the final word finished near 38.08 s in the narrower source check. It also assigned the last word of the opening question in the wildlife clip a zero-length cue, which the SRT writer discards. The truncated beach control still transcribed as a complete final word. When a long cue overlaps an intended cut, transcribe a shorter source window around the reaction and compare it with the exact export and the replay beyond the cut. [Final-word review](editing-toolkit.md#check-a-final-word-against-the-replay)

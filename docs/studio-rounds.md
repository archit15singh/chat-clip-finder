# After the Spike field rounds

Use the [production plan](production-workflow-plan.md) for the full workflow and the [timing guide](short-form-experiments.md) for comparisons. Keep raw source footage and queue evidence local. Record the public links and the editorial lesson here so the next round starts from what was actually tested.

## Test and merge a reference lesson

Start each Instagram-led round with the [source agent's search batch](reference-learning.md#run-a-gta-vi-instagram-search-batch). Ask the editor to compare two treatments of the same authorized Twitch scene using the proposed variable. Keep the scene, payoff, sound and package constant where they can be held constant. Record the variant, expected effect and metric before publishing. Use the independent review and normal queue for the chosen release.

Read back the exact verified post at a comparable age using the steps below. Compare within the same platform and metric source, and record differences in topic, audience or length. Treat an editorial review as evidence about legibility and timing. Treat an audience improvement as a hypothesis until the available metrics support it.

When a batch gives a reproducible workflow fix or a reference lesson supported by another example or counterexample, open a small PR with the evidence, limits and next test. Commit the reusable change and public evidence while keeping source media and private material local. Have the round owner run the repository checks and review the diff before merging to `main`. Record the PR, merge commit and next batch cursor together. When the evidence is incomplete, use the run checkpoint to continue the comparison.

## Clix grocery run

[Source on Twitch](https://www.twitch.tv/videos/2932204601?t=5h55m7s). On the VOD clock the chat cue was 5:55:13, with 20 messages against a 6.5 median. The crop preserves Clix and the interaction prompts. The scene moves from buying groceries to stowing the bag in the pickup. Local shot times and evidence are under `.improvement/studio/grocery/`.

The experiment compared two silent 26-second exports. The first starts on produce with the visible shopping objective. The second starts on the truck's storage menu. The first 60 decoded frames differ and the following 720 match. The reviewer picked the produce opening because the objective reads immediately and the storage reveal stays in sequence. An earlier draft cut before the storage readout. The final frame check showed the count at 2/4 and the bag-stowed caption.

For the next scene, open on an object or action that explains the premise on a phone screen. Keep the creator's reaction and the payoff in frame. This is an editorial judgment from comparing the cuts. The first public viewing and retention readings will show how the released cut performs with real viewers.

- [YouTube Short](https://www.youtube.com/shorts/Z5pU4hTR5ik) was playable on After the Spike. Studio read back Public, the approved title and description, and completed copyright checks with no issues. First verified at about 19:16 UTC on November 18.
- [Instagram Reel](https://www.instagram.com/reel/Df5PJBAhi51/) appeared on the public After the Spike account. Reopened the Reel, verified the caption and creator credit, and checked the produced framing in the player. Shared at about 19:17 UTC on November 18.
- Both deliveries have verified queue receipts for the same source export. The signed-in Twitch VOD player displayed “Unable to play media” at the source time, so the native Clip path could not be exercised. These posts are showcase work.

## Lacy's dating profiles

[Source on Twitch](https://www.twitch.tv/videos/2932194507?t=6h7m45s). Replaying the archived chat recorded 44 messages against a 14.5 median at 6:07:51. The two 13-second treatments start on either the readable phone screen or the wider bar. The first 60 decoded frames differ and the following 330 match. A short cut back to the bar establishes whose phone we are seeing. The last profile delivers the final joke.

The first round's opening check transferred to a different scene and runtime. The independent reviewer could read Butter's name, age, and bio from frame one in the phone-first version. The bar version needed the later close-up to make the premise apparent. The final framing also keeps Lacy visible and avoids the damaged portion of the source capture. Local evidence and exact edit points are under `.improvement/studio/lacy-phone/`.

- [YouTube Short](https://www.youtube.com/shorts/h9l7UdBh0n0) was Public in Studio and playable on After the Spike, with the reviewed title and description. The publication confirmation was observed at about 19:21 UTC on November 18.
- [Instagram Reel](https://www.instagram.com/reel/Df5Pw7rBuZI/) was reopened on the public After the Spike profile. The phone crop, approved caption, and Lacy credit were visible. The post was shared at about 19:22 UTC on November 18.
- The signed-in Lacy VOD player also displayed “Unable to play media.” Both public destinations have separate verified receipts. This round was showcase work.

## Sound follow-up

Both source recordings contain AAC audio. The two shot-composition renders explicitly stripped it before concatenation. The previous queue permitted that picture-only choice. Restored source audio to local copies using the original shot offsets and verified the encoded video stayed identical. The published cuts remain the silent versions. The new queue records sound intent and checks whether the submitted file has signal.

## Read back performance at comparable ages

Run `python3 studio_queue.py milestones` to list the 24-hour, 72-hour, and seven-day observation times for each verified permalink. Collect the platform's metrics and the actual observation time. Use the corresponding owner analytics surface and leave unavailable values blank. Keep an early technical readback out of the comparison window.

Save each readback as an entry in a local JSON array. Use `platform`, `url`, `observed_at` with its time zone, `metric_source`, and `metrics` with the platform's labels and units. Use `null` for a metric the surface does not show. Then run:

```sh
python3 studio_observations.py .improvement/studio/analytics-readings.json
```

The command checks each post against the publishing queue and outputs its actual age in seconds, using the publication time recorded in the receipt. Keep the checked output alongside the original readings. Use optional `milestone_hours` only for a sample collected in its actual window. The verifier accepts 24–25, 72–75, and 168–175 hours as the standard comparison windows. Save readings outside the available windows without a milestone tag so their actual age stays visible. Compare ages and metric sources before interpreting differences.

For posts published during a 24-hour run, you can also collect a two-hour reading while that run is still active. Record it from two hours through two hours and 15 minutes after publication and set `milestone_hours` to `2`. For public counts the collector accepts `--milestone 2`. Keep this early comparison separate from the 24-hour results and label public and owner readings by source.

When owner insights are unavailable, use public counts as a fallback. With `yt-dlp` on `PATH`, pass a verified permalink and the milestone you are collecting. The command checks the receipt and actual age, then returns the named public counts with unavailable fields set to `null`. Omit `--milestone` for an observation outside the scheduled window. Keep these rows under their public metric source.

```sh
python3 studio_observations.py --milestone 24 --collect-public https://www.youtube.com/shorts/VIDEO_ID
```

The initial YouTube Studio check at about 19:24 UTC showed one view on each Short. The Instagram Reels grid at about 19:23 UTC showed zero views on both Reels. Those checks were within minutes of publishing, at different ages, and contain no retention data. The cuts also differ in length, creator, and subject. Treat the phone-size result as an editorial observation and the audience effect as an open hypothesis. For a future performance comparison, use cuts closer in length and subject and compare metric definitions within each platform. [Measurement guide](short-form-experiments.md)

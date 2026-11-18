# After the Spike pilot notes

These notes capture the initial pilot. Use the [current studio goal](studio-goal.md) and [production plan](production-workflow-plan.md) for ongoing rounds.

## Goal prompt

> Run After the Spike as a GTA VI clipping channel with an editor’s judgment. Work from the Chat Clip Finder checkout. Read docs/gta-vi-pilot.md, docs/improvement.md, and the latest run notes in .improvement/rounds/. Verify current platform state before reposting or editing anything.
>
> Fix the descriptions on the existing After the Spike posts first. Start with Lacy’s basketball Reel. Its caption recaps the outcome, then dumps a VOD ID and timecodes. Replace it with a line a real GTA viewer might write, such as “Lacy spotted a hoop bolted to the house and had to see if GTA VI would let him shoot.” Check the actual footage before using any claim. Keep brief creator credit where needed. Give YouTube a timestamped Twitch link below the lead. Keep raw VOD IDs, timestamp ranges, chat counts, and production notes in the run log. Preserve required credit and disclosures. Reopen the posts to verify the saved copy. Use the next verified account session if a platform is signed out.
>
> Study three actual clips from at least two relevant clipping accounts before the next edit. Look at the first two seconds, cut timing, what the viewer learns before the payoff, use of original sound or narration, caption style, and what makes the clip worth sharing. Record the exact references, the techniques visible in the work, and one or two choices to test. Use available views and engagement as context without assuming they prove why a clip took off. Keep looking for better examples as the loop runs.
>
> Find a fresh GTA VI moment. Shortlist three Twitch creators by live audience, chat activity, visual potential, and reuse permission. Monitor in parallel where possible and fall back to TwitchDownloader and the archived-chat ranker when live playback fails. Treat chat surges as scouting clues. Watch the surrounding footage and reject clips with a weak or missing payoff, missing setup, or rights uncertainty. Log the rejected moments and reasons.
>
> Make one vertical edit around 30 seconds, using the length the scene earns. Get to the action quickly. Make the stakes clear, cut dead time, then land the payoff and reaction. Review the actual export at phone size and on mute. Choose sound deliberately. Use cleared source audio if it adds the creator’s reaction or helps the story. Add narration only when it supplies context the viewer needs and platform and campaign rules allow it. A strong silent edit is fine. Avoid generic synthetic narration, formulaic overlays, and repeating the same layout out of habit. Write the title and captions after the edit. Lead with a scene-specific observation, question, or detail that gives people a reason to watch. Keep the reveal in the video when it is the reason to watch. Write for Reels and Shorts separately, and read the first line beside the opening frame or title before posting. If it sounds like an export log, rewrite it.
>
> Verify reuse rights and account identity before publishing. Create a native Twitch Clip when the controls allow it. Publish to After the Spike Reels and Shorts and open both public links. Record source time, qualifying chat counts, editing time, and views, retention, or shares when available at comparable post ages. Track Content Rewards terms, submission deadlines, eligibility, and payout separately.
>
> Before closing each round, show what got better against a previous cut or a first draft, with a specific frame, timing, sound, or copy change. Use available audience evidence to pick the next experiment. Document reusable lessons in the harness, run python3 -m unittest discover -s tests -v, and run the pinned VOD comparison for detector or boundary changes. Push supported changes, open a PR, and verify the merge to main. Keep media, raw chat, and run evidence out of Git. Continue with another independently selected scene while meaningful authorized work is available.

The toolchain uses FFmpeg and yt-dlp for rendering and supported source pages, TwitchDownloader exports for replay, and one shared cue format for automated Twitch and timed manual observation. Kick's official native clip download is a possible input for an eligible source. The first third-party Kick chat lookup returned HTTP 403, so use timed observation for the pilot. [Tool reuse notes](improvement.md#reuse-existing-tools)

Before relying on native Twitch clipping, verify the account menu in the browser window that will publish it. If it shows **Log In**, leave the form ready for account sign-in and continue public chat and source review in another window. For a Content Rewards submission, verify the eligible source and have the submission form ready before publishing. Both current Reach briefs allow 30 minutes after posting to submit. [Lacy brief](https://reachclipping.com/LACYGTA) · [Clix brief](https://reachclipping.com/ClixGTA)

Use chat activity to select scenes and record the counts in the run log. Open the edit with the creator’s immediate stakes, then show the obstacle, result, and reaction. Put chat on screen only when it drives the action. For the Clix recut, review without audio input and use short context grounded in the visible scene. [Edit review](improvement.md#review-the-edit-as-a-viewer)

## Monetization follow-up

1. **Sell the editing work.** Test one small fixed-fee batch with a creator who already has an audience and can supply footage. Agree on delivery time, revision scope, and who can publish where. Confirm applicable game footage and music rights before commercial delivery or publication. A creator's consent covers the material and rights they control. Rockstar describes its fan policy as non-commercial and provides a licensing contact. [Rockstar's footage policy](https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/policy-on-posting-copyrighted-rockstar-games-material)
2. **Use Instagram as a portfolio and inbound channel.** Once the account exists, publish a small batch of original or properly licensed edits. Include creator credit and a clear editing inquiry in the bio. Evaluate Gifts eligibility in the Professional Dashboard before forecasting any platform revenue. [Instagram Gifts](https://about.fb.com/news/2023/02/earn-money-on-instagram-with-gifts/)
3. **Test YouTube Shorts as a second channel.** Use the same rights-cleared masters where the agreement allows it, with original narration or editorial context that adds to the footage. Shorts ad sharing requires Partner Program eligibility. YouTube reviews reused content separately from whether a creator gave permission to repost. [YouTube reused-content rules](https://support.google.com/youtube/answer/1311392?hl=en-in) · [Shorts monetization](https://support.google.com/youtube/answer/12504220?hl=en)

After the first cross-platform clip, evaluate funded campaigns and fixed-fee editing when a qualified creator can supply usable footage and the terms permit it.

The first commercial milestone is a collected payment for agreed deliverables. For a publishing experiment, compare the same edited clips across eligible channels after seven days. Track views, average watch time, profile visits or subscribers, and qualified creator inquiries. Record each batch's cash collected, direct costs including fees, and hours across outreach, review, editing, and delivery. Use (cash collected − direct costs) ÷ hours worked to decide whether to repeat the batch. Treat views and retention as signals about audience fit.

## Instagram profile

- Display name — **After the Spike | GTA VI Clips**
- Preferred handle — **@afterthespike**. Backup — **@afterthespikeclips**.
- Bio — **GTA VI highlights & breakdowns. Big stream moments in about 30 seconds. DM for collabs.**
- Avatar and covers — A coral waveform on deep aubergine. Use a short plain-language hook on each cover and put creator credit in the caption.
- First posts — An edit with its setup and payoff, a short commentary explaining a mechanic or decision, and a sample that shows the editing service. Use footage whose terms cover each post.

## Test the clip finder

The [live CLI](../live_clipper.py) polls Twitch for GTA VI streams on a watchlist and listens to those channels' chat via Twitch IRC. It retains counts and cue metadata. It uses separate rolling baselines, suppresses overlapping cues within a channel, and queues a 30-second window with 18 seconds before the bucket boundary and 12 after by default. Both watch and replay accept --before to test another split within the same 30 seconds. Set TWITCH_CLIENT_ID, TWITCH_LOGIN, and a user TWITCH_ACCESS_TOKEN issued to that app with the chat:read scope. The CLI needs its own token. [Twitch IRC](https://dev.twitch.tv/docs/chat/irc/) · [Twitch OAuth](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/)

    python3 live_clipper.py watch creator_one creator_two --out .improvement/cues.jsonl --buckets-out .improvement/buckets.jsonl
    python3 live_clipper.py replay .improvement/buckets.jsonl --out .improvement/replayed.jsonl
    python3 live_clipper.py render --queue .improvement/cues.jsonl --id creator_one-1795007000 --video .improvement/partner.mp4 --recording-start 1795006900 --out .improvement/draft.mp4

Each run writes a fresh queue. Replay takes JSON lines with a lowercase channel login, a UTC bucket (Unix seconds divided by ten and rounded down), and a nonnegative message count. For example, {"channel":"creator_one","bucket":179500699,"messages":21}. Feed buckets in ascending order per channel. An optional reset set to true starts a fresh baseline. The watcher writes a reset after a reconnect or a stream change. The watcher uses chat receipt time. Align the local recording's time zero to that clock and check stream delay against a known moment before rendering. The existing VOD CLI accepts matching recordings and chat exports and uses Twitch's VOD offsets.

## Improve one decision at a time

Label partner footage before reviewing picks. Record an event instant, a complete setup-to-payoff interval, and reasons for rejecting drafts. Compare one change at a time across the same labeled material and budget. Track complete scenes and anchor hits per minute of review, plus editing minutes per accepted clip. Keep an unseen example for checking any improvement before changing production defaults. [Improvement guide](improvement.md)

The first replay of four historical GTA V excerpts yielded ten complete 30-second windows. One of ten labeled intervals was fully covered, and one of three marked anchors was captured. This sets a comparison point and shows why a reviewer needs to adjust boundaries before publishing. The existing VOD benchmark reported no change across all four cases.

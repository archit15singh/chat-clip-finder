# Distribute an After the Spike release

The distributor takes one verified Short or Reel and looks for a venue where the scene is worth sharing on its own. The path is **native contribution → verified release → one relevant next action**. In a community, start with something a member could discuss, even if they skip the link. On an owned surface, connect the release to the next story a viewer is likely to want.

## Pick a venue

Start with the release's subject and the audience already discussing it. For the GTA VI grocery cut, a post about how the vehicle carries shopping is a better fit for a world-detail discussion than a generic reel drop. For the dating-profile cut, lead with the readable bio and show why it is funny before asking people to watch another scene. Pitch an owned follow-up, a dedicated clips thread, or an invited creator placement. Prefer the one with demonstrable audience fit and the least friction, and record why the rest were skipped.

| Surface | How to use it |
| --- | --- |
| Owned YouTube | Use a relevant channel-profile link or, where available, a related video from the channel as the next step. YouTube disables clicks on ordinary URLs in Shorts descriptions and comments. Related videos require advanced feature access. Check the actual owner UI and confirm the viewer route. [Link surfaces](https://support.google.com/youtube/answer/13748639) · [Related video](https://support.google.com/youtube/answer/14075157) |
| Instagram | A willing collaborator can use native Repost for a public Reel, which credits the original poster. An authorized owner can use a Story link sticker if their account offers it and the destination is useful. Check which route is visible on the account before writing copy that relies on it. [Reposts](https://about.fb.com/news/2025/08/new-instagram-features-help-you-connect/amp/) · [Story link stickers](https://about.fb.com/ja/news/2021/10/linkaccessstickers/) |
| Reddit | Read the specific subreddit's current rules, pinned threads, and recently accepted examples. Sitewide policy prohibits repeated or unsolicited mass engagement. Community moderators also set local rules, which may restrict self-promotion more tightly. Share only where the specific contribution and link format are welcome. [Spam policy](https://support.reddithelp.com/hc/en-us/articles/360043504051-Spam) · [Community rules](https://support.reddithelp.com/hc/en-us/articles/360043503951-What-are-Reddit-s-rules) |
| Discord or a streamer community | Look for a designated clips channel or moderator invitation and respect the local rules. Share a relevant, credited clip in place. Discord prohibits unsolicited bulk messages and self-bots. Twitch's clip settings affect sharing from its own clip surface and must be read separately from community permission. [Discord Guidelines](https://discord.com/guidelines) · [Server rules](https://discord.com/community/developing-server-rules) · [Twitch clip settings](https://help.twitch.tv/s/article/clips-settings?language=en_US) |

Never use a media placement to exchange or buy views, likes, follows, or subscriptions. Give the audience a clear destination and disclose ownership and any material relationship. If a campaign is attached, ask the campaign agent to verify allowed traffic, placement restrictions, and disclosures before sharing. A placement does not establish that its traffic qualifies for payment. [YouTube fake engagement](https://support.google.com/youtube/answer/3399767)

## Handoff and verify

1. Read `studio_queue.py status` and use a verified destination. Read the actual venue rules and its format. Capture the rule URL, relevant clause or invitation, and check time. When posting or linking is outside the existing authorization, prepare the brief and hand it to the parent for a decision. Respect account-link, join, message, and permission boundaries separately.
2. Save one JSON brief per placement under `.improvement/studio/distribution/`. These are example values for a planning dry run, with a fictional venue and a local publication receipt from the showcase. Replace the venue, rule evidence and times with facts before an actual placement.

```json
{
  "cut": "clix-grocery-01",
  "platform": "youtube",
  "post_url": "https://www.youtube.com/shorts/Z5pU4hTR5ik",
  "venue_url": "https://example.org/community/clips",
  "venue_basis": "rules_allow",
  "rules_checked_at": "2026-11-18T19:30:00Z",
  "rules_evidence": "Example only. Replace with the actual rule or invitation reference.",
  "publisher": "After the Spike",
  "audience_fit": "A thread for people collecting small gameplay details.",
  "copy": "The truck bed tracks groceries as cargo. I clipped the sequence for After the Spike: https://www.youtube.com/shorts/Z5pU4hTR5ik",
  "disclosure": "I made this for After the Spike. Clix is credited in the linked clip.",
  "measurement": "Compare YouTube External and Shorts feed at the same post age, plus any source-side clicks."
}
```

If distributing a campaign release, also record `campaign` and `campaign_distribution_terms` with evidence from the campaign agent. Use `owned` for a controlled surface or `moderator_invited` for a specific invitation. Save the checked brief before the authorized operator makes a placement.

```sh
python3 studio_distribution.py .improvement/studio/distribution/brief.json
```

3. Check the saved brief and venue history for an existing placement. Where the user authorizes this placement, record the attempt locally before sending it. Afterward, reopen the direct placement URL and read audience visibility, exact venue, account, copy and actual destination. For an ephemeral or members-only placement, retain the evidence reference locally and capture readback while it is visible. If the result is unclear, inspect the destination before retrying. If it is removed or rejected, record why and skip further placements there unless the rules or invitation change.
4. Save a readback JSON object containing `brief_sha256`, `placement_url`, `linked_post_url`, `publisher`, `copy`, `placed_at`, `verified_at`, and `evidence`. Use a time zone and the actual observed account and text. The checker confirms the release, exact brief, matching host, and timeline. Its output records the age of the release at placement. Use the actual subreddit or Discord channel URL as the venue. The checker rejects a placement in another community or channel on the same host. For other platforms with a different placement URL structure, record `observed_venue_url` after checking the actual venue. The operator must still verify what was visible there.

```sh
python3 studio_distribution.py .improvement/studio/distribution/brief.json \
  --readback .improvement/studio/distribution/readback.json
```

Keep the checked result alongside the brief. The program only reads files and the queue. It neither opens a public surface nor sends a post.

## Measure the path

Record the native placement permalink and time, any measured impressions or outbound clicks on that surface, and the destination outcome at comparable post ages. In YouTube Studio, compare External with Shorts feed when visible, alongside engaged views and one meaningful downstream action. For Instagram, note available shares, follows, watch time, or available Story link activity and keep totals distinct from identified referrals. Metric availability is account-specific. [YouTube traffic sources](https://support.google.com/youtube/answer/12220281) · [Instagram watch-time insights](https://about.fb.com/news/2023/04/instagram-reels-trending-audio-and-gifts-updates/)

An analytics-enabled web landing page you control may use consistent `utm_source`, `utm_medium`, and `utm_campaign` tags if the venue permits it. Keep the verified video link as the default when it is the shortest honest route. Arbitrary tags on the video URL do not establish that a platform will expose attribution. Use native metrics or mark attribution unavailable. [Google Analytics campaign URLs](https://support.google.com/analytics/answer/10917952)

Use [the round log](studio-rounds.md#read-back-performance-at-comparable-ages) and `studio_observations.py` for destination readings. Send the checked placement, measurement windows, actual metrics and any confounder to the analyst and platform experts. For the next round, choose one question, such as whether a relevant community thread yields attributed traffic beyond feed discovery. A view change alone cannot isolate that placement's effect. Marketplace approval and payout are separate observations from the campaign agent.

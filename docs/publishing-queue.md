# Publishing queue

Research, scouting and editing can run in parallel. A single publisher holds the Brave task tab. The local queue coordinates that handoff and records what the publisher actually verifies on the platform.

Run `python3 studio_queue.py handoff` at the start of a round or after an interruption. It lists cuts awaiting independent review, approved deliveries, any attempt occupying the publisher slot, verified public links, and analytics times derived from the same receipts. Use `inspect CUT` to read the exact review package and `claim` to acquire the publishing lease.

## Prepare the handoff

1. For archived Twitch chat, scout with `scripts/rank-replay-chat.py` and verify the selected moment in the VOD. Use `vod-offset` with seconds from the start of that VOD. For `clip_finder.py` on an excerpt, add the report's `settings.vod_start_seconds` to its local start and end.
2. For `live_clipper.py`, replay the saved buckets and use `unix` with absolute cue bounds in Unix seconds. When rendering from a local recording, subtract its `--recording-start` before trimming. Use `recording-offset` for a source with only a local clock. Record source identity and the verified range in the manifest. Keep the exact edited shot order in the local review sheet.
3. Export two treatments, run [media review](editing-toolkit.md#review-a-vertical-delivery-export) on each, and fill in the [review sheet](editorial-review-template.md). Put everything in `.improvement/`. Prepare a manifest like this one with actual source, file paths, credit, account identities, and permission evidence.

```json
{
  "id": "market-01",
  "scene": "creator-vod123-market",
  "editor": "edit-agent",
  "artifact": "chosen.mp4",
  "media_review": "chosen-review/review.json",
  "source": {
    "id": "vod123",
    "creator": "Creator",
    "reference": "https://www.twitch.tv/videos/123",
    "credit": "Creator on Twitch",
    "clock": "vod-offset",
    "start": 320,
    "end": 346
  },
  "edit": {
    "duration_seconds": 26,
    "hook_seconds": 0,
    "payoff_seconds": 24.5,
    "source_spans": [[320, 346]]
  },
  "sound": {
    "mode": "source",
    "reason": "Keep the game cue and creator reaction in sync",
    "rights_evidence": "Scope includes the source speech and game audio, reviewed for third-party music"
  },
  "editorial_choice": "Open on the produce display before showing the truck",
  "experiment": "Check whether viewers stay for the storage reveal",
  "destinations": {
    "youtube": {
      "account": "channel-id",
      "title": "Exact Short title",
      "caption": "Exact Short description",
      "reuse_cleared": true,
      "rights_evidence": "Permission and scope verified for this destination"
    },
    "instagram": {
      "account": "@handle",
      "caption": "Exact Reel caption",
      "reuse_cleared": true,
      "rights_evidence": "Permission and scope verified for this destination"
    }
  }
}
```

Use both destinations for a normal showcase. When a campaign permits only one, list only that destination so the queue creates exactly one delivery. Use a stable scene ID across alternate edits and copy revisions. The queue rejects reuse of an exact Twitch-native clip under a different scene ID, including when the portrait rendition bytes differ. Use a new cut ID and set `supersedes` to the prior cut ID when replacing a revision. Previously verified platforms keep their receipts on the earlier cut and are omitted from the replacement's work. Exact duplicate staging is idempotent while the source inputs are available. Use `inspect CUT` to recover the staged package if the staging response was lost and the original inputs have moved.

New cuts declare the expected edit length, hook and payoff timestamps in export seconds, and the ordered used spans in the declared source clock. Sample the two exact beat times with `review_media.py --at`. The gate checks that the rendered runtime matches the planned runtime within 50 ms. Source spans must lie within the declared range. Reordering, repeats, and retiming are allowed. For a paid cut, also put the exact `campaign_url` from the commissioned brief into the manifest before staging it.

New cuts declare `sound.mode` as `source`, `original`, or `silent`. Start with the cleared creator and game audio in `source` mode. Use `original` for a replacement soundtrack and record why the broadcast mix was omitted in `sound.source_audio_omission`. Both modes require rights evidence and detectable signal in the exact export. Silent means a trackless export chosen for a specific editorial or rights reason. Include the reason in every case. The audio gate checks the peak, track coverage within 250 ms of the picture at each end, and at least 0.5 seconds of measured signal (half the picture duration for clips shorter than one second). Regenerate older audio reports with the current reviewer before staging a new cut. Listen to check words, mix, timing, and music clearance before approval.

## Independently approve the exact package

```sh
python3 studio_queue.py stage /absolute/path/to/manifest.json
python3 studio_queue.py inspect market-01
python3 studio_queue.py review market-01 /absolute/path/to/approval.json
```

The reviewer opens the spooled export and the review report paths from `inspect`, checks the story, original permission, captions, accounts, opening, payoff, and sound, then writes an approval containing `reviewer`, `evidence`, `verdict: "approve"`, and the staged `package_sha256`. Include a `checks` object with a brief evidence note under each of `source_and_rights`, `hook_and_payoff`, and `sound_and_sync`. The reviewer identity must differ from the editor's. Revise and stage a new cut ID if a check fails. The queue binds the approval to the selected file and both platform packages.

## Publish and verify

1. Use `brave-tabs memory` and the existing task tab. Run `python3 studio_queue.py claim --worker PUBLISHER` when ready. `null` means no approved work is eligible or another attempt owns the browser slot. Check `status` for the cause.
2. Confirm the signed-in channel or profile and the exact file and copy from the claim. Record a preflight JSON with the observed `platform`, `account`, the claimed `package_sha256`, and the `upload_file` you will select. For a paid cut, include `campaign_brief`, the path to its current checked brief. Relative paths resolve next to the preflight file. Run `python3 studio_queue.py begin TOKEN --preflight PREFLIGHT.json` **before** the first platform mutation, including creating a draft. The gate rehashes the selected file and reruns the paid-campaign preflight when declared. Continue only on `submitting`. Run `renew TOKEN` during the operation and before a new mutation if the lease is close to expiry. Stop interacting when the lease has expired. Use `remember TOKEN PUBLIC_URL` as soon as the platform exposes a YouTube video ID or Instagram Reel code that can be represented as a permalink.
   When using the macOS file picker, wait until its Open sheet is visible before selecting a file. If it needs a visible Downloads copy, verify that copy against the claim hash and use the exact row in the picker.
3. Open the published permalink and verify visibility, account, visible video and exact copy. Record the timestamp from platform readback, the account, `visibility: "public"`, `public_url`, `public_at` (ISO format with time zone), `artifact_sha256`, exact `caption`, `title` for YouTube, and `evidence` stating what you checked. The hash identifies the locally selected upload file. Platforms may transcode its bytes. On new cuts, include `playback` with `played: true`, `hook_and_payoff_seen: true`, the observed `duration_seconds`, and the boolean `sound_heard`. Confirm playback with volume on. If it cannot be confirmed, record it with `release TOKEN --evidence REASON` to move the attempt into reconciliation. Retry the readback of that same permalink. Run `python3 studio_queue.py finish TOKEN RECEIPT.json`. An identical finished receipt can be retried safely. Use `history` to audit claims and receipts.

A pre-mutation lease can be released with `release TOKEN --evidence REASON`; an expired claim also returns to ready. A submission with an uncertain result reserves the browser slot in reconciliation, including after expiry. Confirm that the prior worker stopped and check the intended account's public posts, drafts and pending uploads. Run `reconcile TOKEN RECEIPT.json` with `prior_worker_stopped: true` added to the verified receipt if the post exists. If the post and draft are both absent, use `outcome: "absent"`, `account`, `evidence`, and explicit true flags for `prior_worker_stopped`, `pending_uploads_checked`, and `public_posts_checked`. If a draft survives and you cannot safely reconcile it as public or absent, keep the lock and escalate with the draft ID. Recover that existing draft through the verified account before considering a second upload.

Keep the SQLite file and its sibling `.media` folder together. There is one database for the real publisher. Use `--queue` with a separate path for synthetic rehearsals. Native Twitch Clips can be tracked with a separate source receipt when the player and rights allow it.

Existing staged cuts and receipts retain their original contract. A new stage or revision uses all current checks. See the [verification gates](studio-verification-gates.md) for failures and recovery.

## Deliver through Twitch’s native export

Use this route when the creator enables direct social exports for the exact Twitch clip. Verify the destination buttons are available, and review the official portrait rendition that Twitch supplies for that clip. Keep its original bytes as the manifest artifact and run `review_media.py --twitch-native` to accept Twitch’s HEVC portrait rendition. Record the creator opt-in and the native-only scope in both destination rights notes. Add `twitch_native_clip` to the manifest with the Twitch clip permalink.

For a clip you trim in Twitch, verify the saved rendition against a bounded replay excerpt. The editor timeline is relative to its captured window. With NumPy and FFmpeg available, match three independent audio anchors against the replay and record the confirmed range. A silent tail can move the anchors earlier in the clip. Read their positions in the report and inspect the result against source speech and frames at both boundaries.

```sh
python3 scripts/align-clip-audio.py native-portrait.mp4 replay-excerpt.mp4 --replay-start 690
```

At claim, reopen that permalink and confirm the portrait preview and the connected destination account. Fetch or confirm the current official portrait rendition. In preflight use `twitch_native_clip`, `layout: "portrait"`, and `portrait_rendition` instead of `upload_file`. The queue checks the permalink and local rendition hash against the approved package. The operator checks that the active preview uses that same portrait before submitting. The normal lease, campaign evidence, copy, and public playback checks still apply. The receipt hash identifies the reviewed Twitch rendition. Twitch and the destination can transcode it.

### Recover a native share without a permalink

Twitch can return to **Share to More Places** immediately after submission. Check the intended destination before clicking Share again.

- For YouTube, look for the exact title in both **Videos** and **Shorts** in the brand channel’s Studio. During the apple-bowl release, the upload first appeared under Videos. Its public Shorts URL initially showed a playback error and played after processing and a reload.
- For Instagram, check the brand profile’s **Reels** and **Posts** tabs for the exact caption and picture. Use the resulting permalink to verify playback. If the post is still missing, check the brand’s pending uploads and drafts before recording an absent outcome.
- If Brave controls are unavailable after an Instagram share, look up the public Reels list for the brand handle with a read-only connector such as vidIQ. Match caption, runtime, and publication time. Download the public rendition by permalink and check it with `review_media.py --audio-evidence`. Compare the opening and payoff frames with the approved export, and match the public audio to the approved source window with `scripts/align-clip-audio.py` when a longer replay excerpt is available. Document which evidence came from the public rendition and which came from the earlier listening review. If the connector finds no match, keep the attempt in reconciliation until pending uploads and drafts can also be checked.
- If a permalink appears while the attempt is submitting, save it with `remember`. If the lease has already moved to reconciliation, verify that permalink and use `reconcile` with the receipt. An empty first readback or a broken browser connection is evidence for keeping the existing attempt open.

# Publishing queue

Research, scouting and editing can run in parallel. A single publisher holds the Brave task tab. The local queue coordinates that handoff and records what the publisher actually verifies on the platform.

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

Use a stable scene ID across alternate edits and copy revisions. Use a new cut ID and set `supersedes` to the prior cut ID when replacing a revision. Previously verified platforms keep their receipts on the earlier cut and are omitted from the replacement's work. Exact duplicate staging is idempotent while the source inputs are available. Use `inspect CUT` to recover the staged package if the staging response was lost and the original inputs have moved.

New cuts declare `sound.mode` as `source`, `original`, or `silent`. Source or original requires rights evidence and detectable signal in the exact export. Silent means a trackless export chosen for a specific editorial or rights reason. Include the reason in every case. The peak check catches a missing or effectively blank track. Listen to check words, mix, timing, and music clearance before approval.

## Independently approve the exact package

```sh
python3 studio_queue.py stage /absolute/path/to/manifest.json
python3 studio_queue.py inspect market-01
python3 studio_queue.py review market-01 /absolute/path/to/approval.json
```

The reviewer opens the spooled export and the review report paths from `inspect`, checks the story, original permission, captions, accounts, opening, payoff, and sound, then writes an approval containing `reviewer`, `evidence`, `verdict: "approve"`, and the staged `package_sha256`. The reviewer identity must differ from the editor's. Revise and stage a new cut ID if a check fails. The queue binds the approval to the selected file and both platform packages.

## Publish and verify

1. Use `brave-tabs memory` and the existing task tab. Run `python3 studio_queue.py claim --worker PUBLISHER` when ready. `null` means no approved work is eligible or another attempt owns the browser slot. Check `status` for the cause.
2. Confirm the signed-in channel or profile and the exact file and copy from the claim. Run `python3 studio_queue.py begin TOKEN` **before** the first platform mutation, including creating a draft. Continue only on `submitting`. Run `renew TOKEN` during the operation and before a new mutation if the lease is close to expiry. Stop interacting when the lease has expired. Use `remember TOKEN PUBLIC_URL` as soon as the platform exposes a YouTube video ID or Instagram Reel code that can be represented as a permalink.
   When using the macOS file picker, wait until its Open sheet is visible before selecting a file. If it needs a visible Downloads copy, verify that copy against the claim hash and use the exact row in the picker.
3. Open the published permalink and verify visibility, account, visible video and exact copy. Record the timestamp from platform readback, the account, `visibility: "public"`, `public_url`, `public_at` (ISO format with time zone), `artifact_sha256`, exact `caption`, `title` for YouTube, and `evidence` stating what you checked. The hash identifies the locally selected upload file. Platforms may transcode its bytes. Run `python3 studio_queue.py finish TOKEN RECEIPT.json`. An identical finished receipt can be retried safely. Use `history` to audit claims and receipts.

A pre-mutation lease can be released with `release TOKEN --evidence REASON`; an expired claim also returns to ready. A submission with an uncertain result reserves the browser slot in reconciliation, including after expiry. Confirm that the prior worker stopped and check the intended account's public posts, drafts and pending uploads. Run `reconcile TOKEN RECEIPT.json` with `prior_worker_stopped: true` added to the verified receipt if the post exists. If the post and draft are both absent, use `outcome: "absent"`, `account`, `evidence`, and explicit true flags for `prior_worker_stopped`, `pending_uploads_checked`, and `public_posts_checked`. If a draft survives and you cannot safely reconcile it as public or absent, keep the lock and escalate with the draft ID. Recover that existing draft through the verified account before considering a second upload.

Keep the SQLite file and its sibling `.media` folder together. There is one database for the real publisher. Use `--queue` with a separate path for synthetic rehearsals. Native Twitch Clips can be tracked with a separate source receipt when the player and rights allow it.

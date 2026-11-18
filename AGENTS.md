# Chat Clip Finder

## Publishing authorization

Archit authorizes the studio to publish reviewed After the Spike Shorts and Reels through the shared queue on YouTube and Instagram. Proceed with routine uploads and post verification without asking for approval again. Use the available signed-in publishing accounts and resolve ordinary account switches or sign-in with the existing session and saved access.

For requests to keep improving the clipper, tune its ranking, or compare clip boundaries, use the [clipper-improvement skill](.agents/skills/clipper-improvement/SKILL.md).

Run the repository checks with `python3 -m unittest discover -s tests -v`. Keep source footage, raw chat, and local comparison reports in `.improvement/` or outside the checkout.

## After the Spike

- Build a GTA VI channel with a recognizable editorial point of view. Study creator edits, then use what you learned to pick and shape real scenes. Give every opening, cut, sound choice, and description a reason to be there. Chat spikes are scouting evidence. Keep chat counts, VOD IDs, and trim windows in the run log so the viewer sees the story.
- Source GTA VI clips from Twitch through this repo's existing live and VOD replay harness. The user confirmed this is the intended sourcing path for the current showcase. Check the source and reuse scope for each new scene. Reuse that decision on subsequent rounds unless concrete evidence changes the scope.
- Publish independently reviewed showcase edits to After the Spike on Shorts and Reels. Use one publisher so uploads can be checked and recovered without duplicates. Strong showcase cuts are the immediate milestone. The next commercial milestone is joining Clix's Content Rewards campaign. Check that campaign's separate terms, eligibility, and submission window when pursuing it.
- Read the [production plan](docs/production-workflow-plan.md) for the roles and checks in each stage. Use the [publishing queue](docs/publishing-queue.md) when handing an approved cut to the browser publisher. When a user decision changes how the next round should run, save the reason and the trigger here or in the linked workflow before handing off.

### Expert roles

- Run `reference_learner` for saved creator collections or supplied references. Give it an authorized inventory and ask for timestamped picture and audio evidence, then route transferable techniques to the platform experts and editor. Keep private references local. See [reference learning](docs/reference-learning.md).
- Run `youtube_expert` and `instagram_expert` in parallel for route-specific monetization, reference analysis, hooks, duration, and post analytics. Give the editor one testable change from their advice. Reuse publishing receipts and actual post age when asking for follow-up. See [platform experts](docs/platform-experts.md).
- Run `campaign_expert` for a paid round. It checks the marketplace and sponsor terms, then hands the scout an eligible creator and source window. Attach those rules to the edit and publishing handoff. Send verified public receipts back for submission and track approval and payment separately. See [paid campaigns](docs/paid-campaign-workflow.md).
- Run `distributor` after a verified release to identify where the scene fits and plan a useful community-native placement. Read the destination's rules and keep its permission, message, link, and measurement evidence with the placement. See [organic distribution](docs/studio-distributor.md).
- Start with cleared creator and game audio, and listen to the exact export during independent review. Check the out-point for unfinished speech and finish reactions that carry the story. Keep audio files local when reviewing through Codex. Use the [audio and editing guide](docs/editing-toolkit.md#keep-sound-through-the-edit) for tool evidence and playback. The queue checks for audio signal and accepts a trackless export only with a stated editorial or rights reason.

## Diagrams

When Archit says "visualise" or "visualize", render the visualization as plain ASCII in a fenced `text` block.

## Browser use

Use the `brave-tabs` skill for tab management and Computer Use for page interaction. Reuse one task tab for a batch of clips and its verification. Run `brave-tabs memory` before and during media-heavy work. Close disposable task tabs by ID. If memory pressure rises, use OneTab to park only selected, finished task tabs with no unsaved state. Preserve the user's tabs and private sign-ins. If Brave is unresponsive, stop browser work until it recovers.

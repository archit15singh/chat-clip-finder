# Chat Clip Finder

For requests to keep improving the clipper, tune its ranking, or compare clip boundaries, use the [clipper-improvement skill](.agents/skills/clipper-improvement/SKILL.md).

Run the repository checks with `python3 -m unittest discover -s tests -v`. Keep source footage, raw chat, and local comparison reports in `.improvement/` or outside the checkout.

## Browser use

Use the `brave-tabs` skill for tab management and Computer Use for page interaction. Reuse one task tab for a batch of clips and its verification. Run `brave-tabs memory` before and during media-heavy work. Close disposable task tabs by ID. If memory pressure rises, use OneTab to park only selected, finished task tabs with no unsaved state. Preserve the user's tabs and private sign-ins. If Brave is unresponsive, stop browser work until it recovers.

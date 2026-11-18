# Paid clipping campaigns

The `campaign_expert` owns the commercial handoff from one campaign lead to one verified submission and payout readback. Run it in parallel with platform research. Keep brief snapshots, decisions, and account readbacks in `.improvement/campaigns/`. The public showcase demonstrates editing ability. A paid campaign has its own source rights, eligibility, disclosure, submission, and earnings rules.

## Research map

Checked November 19, 2026 IST. Treat listings as leads until the connected account can open the current campaign, show it is accepting work, and satisfy its requirements.

| Provider | Discovery and verification |
| --- | --- |
| Content Rewards | Open Discover, the campaign, its sponsor's full brief, and its linked-account status. Most campaigns accept a fresh public link after posting, with a 30-minute deadline. Pre-approval campaigns require a draft decision on an eligible account before posting and a second review after posting. Check the exact product and account connection, particularly on older Whop instructions. On the submissions page, verify the pending, approved, or rejected record and its payout detail. Approval and payout are separate. [Discover](https://contentrewards.com/c/discover) · [Submit a video](https://help.contentrewards.com/en/articles/15319814-submit-a-video) · [Approval](https://help.contentrewards.com/en/articles/15319801-approval-and-review) · [Payouts](https://help.contentrewards.com/en/articles/15319815-payouts) |
| Vyro | Start at Campaigns and read the official assets, allowed platforms and language, disclosure, payout model, and caps from the order-specific brief. The public board returned a loading shell during this pass. No eligible GTA campaign was verified there. Creator terms describe a live link and source file as the default unless the campaign specifies otherwise. Follow the live submission screen and verify success in the dashboard. Current payout help routes through Whop and varies by country. Older announcements describe different thresholds and withdrawal routes; use the current brief and applicable terms. Paid boosts are prohibited. [Campaigns](https://vyro.com/campaigns) · [Creator terms](https://vyro.com/creator-terms) · [Clips and content](https://vyro.com/help/clips-and-content) · [Payouts](https://vyro.com/help/earnings-and-payments/payouts) · [Paid promotion](https://vyro.com/help/clips-and-content/can-i-use-paid-ads-to-boost-my-views) |
| Clipster | Look in Discover for gaming clipping briefs and source media. Current help specifies a linked public account and a direct URL within 24 hours, subject to the campaign. Check if the brief uses the website or Discord for submissions, then verify the provider's record and balance. No eligible GTA campaign was verified in this pass. [Campaign rules](https://app.clipster.com/help-centre/campaigns-and-rules/how-do-campaigns-work) · [Valid submissions](https://app.clipster.com/help-centre/submissions-and-views/how-do-i-submit-a-clip-and-what-counts-as-a-valid-post) · [Payout timing](https://app.clipster.com/help-centre/earnings-and-payouts/when-do-i-get-paid) |

## First shortlist

| Creator | Why scout and what must clear |
| --- | --- |
| Clix | First choice because it fits the channel and the project already knows how to scout Clix. Reach listed the GTA marathon campaign live and Content Rewards showed it accepting clips. The sponsor lists a $5,000 pool, 400,000 minimum-view requirement, qualifying geography of at least 50% in the stated countries, Clix as the focus, a required hashtag, a 30-minute submission window, and restrictions on logos, AI-generated videos, and engagement manipulation. Treat eligibility for the agent-assisted workflow, exact footage, permitted distribution, linked accounts, and payout route as open until verified. [Listing](https://contentrewards.com/c/campaigns/985dc674-c75e-44fc-ac87-1b1506324389) · [Sponsor brief](https://reachclipping.com/ClixGTA) |
| YourRAGE | A Twitch marathon with a new creator and the same GTA audience. The sponsor lists a $5,000 pool, 500,000 minimum-view requirement, a minimum 50% qualifying audience geography, and the same short submission window. Check the current source availability, caption, allowed promotion and approval rules. [Sponsor brief](https://reachclipping.com/yourRAGE) |
| Lacy | The team has a replay and chat workflow for Lacy, and the sponsor lists a $12,500 pool with a 750,000 minimum-view requirement. Check the exact campaign ID because other Lacy pools also appear in discovery. [Sponsor brief](https://reachclipping.com/LACYGTA) |

Pool figures are campaign budgets. Before choosing work, compare the actual minimum, cap, fees, remaining budget, accessible footage, editing time, and past eligible views. If After the Spike lacks enough audience data, treat likely earnings as unknown and prefer the lower-cost test. The existing Clix and Lacy showcase posts were commissioned for editorial learning. Scout a new source window for the paid brief.

## Run one pass

1. **Discover and qualify.** Search each provider's current list, follow sponsor and footage links, and rank the best eligible creator. Record why each lead is ready, held, or rejected, plus when to recheck. Verify that the accepting campaign and exact source IDs are in scope for paid use, each intended social destination is authorized, the connected accounts qualify, and the owner has an eligible payout route. Read the brief's footage, graphics, audio, use of AI, caption, disclosure and distribution rules. Where sponsor instructions and the provider's current flow differ, verify the applicable flow with the current account. Review prominent disclosures for applicable territories and platform labels. [FTC disclosure guidance](https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers)
2. **Commission.** Send the scout one creator, a source URL and permitted time range, a brief ID and close time, plus an editorial target. Ask for source ID, in/out, moment, exact rights evidence and an alternative moment. Give the editor a hook hypothesis, sound and disclosure choices, deadline, and audience-rule evidence. Use the [production plan](production-workflow-plan.md) for the independent media review. For draft-first campaigns, record the provider's draft approval and permitted account against this exact package. Use a human editor or select a compatible brief when necessary to meet a sponsor's actual workflow rules.
3. **Schedule and upload.** Before the publisher claims the job, save the brief, stage the actual cut, get the independent queue approval, and run the upload preflight below. Check enough time remains for publication and submission. Send exact approved copy, accounts, source scope, package hash and deadline to the [single uploader](publishing-queue.md). For a single-platform campaign, stage a cut with just that destination and verify that the installed publishing queue accepts it. A brief may permit publishing on both while allowing submission on only one. Confirm acceptable distribution with this brief before handoff to the distributor.
4. **Submit and verify.** Check the current campaign and account immediately after each public receipt. Run the local submission check. When the current request authorizes actual submission, use the destination's standard signed-in flow. Confirm the exact campaign account, verified link, and required source file or draft ID; check the dashboard and local ledger for duplicates before submitting. Save the provider submission ID and actual time. If a write times out, reconcile that same post and campaign in the dashboard before retrying.
5. **Reconcile and repeat.** Read back the provider state and supporting evidence. Keep provider approval, credited wallet amount, and actual settled payment separate. Capture rejection reason, cash or wallet currency, edit minutes, time to approval, and time to credited or settled funds when available. Hand policy, audience, sound, or originality failures back to the relevant role. Use the outcome to revise the search next pass, then check which leads are due or look for alternatives. If none can be qualified, hand back the reasons and the next recheck rather than queuing a speculative upload.

Separate account linking, identification documents, acceptance of new terms, and withdrawal or transfer from the clip handoff. Keep credentials and financial account details out of local evidence records.

## Verify the handoffs

Save a JSON brief after qualification, then add the package hash before requesting upload. Set `accounts` to the exact approved publishing destinations. `submission_platforms` can include all or part of that set. Example fields for a synthetic brief:

```json
{
  "provider": "content-rewards",
  "campaign_url": "https://contentrewards.com/c/campaigns/example",
  "commissioned_at": "2026-11-19T08:45:00Z",
  "recheck_at": "2026-11-19T10:00:00Z",
  "closes_at": "2026-11-19T12:00:00Z",
  "submission_window_minutes": 30,
  "preapproval_required": false,
  "package_sha256": "replace-with-the-exact-reviewed-fingerprint",
  "allowed_source_ids": ["twitch:vod:123"],
  "accounts": {"youtube": "channel-id", "instagram": "@handle"},
  "submission_platforms": ["youtube", "instagram"],
  "checks": {
    "active_and_joined": "Campaign open and joined, observed in the account",
    "account_eligibility": "Both destinations linked and audience requirements verified",
    "source_rights": "Approved VOD confirmed for paid use on both destinations",
    "editorial_rules": "Opening, sound, disclosure and exact copy checked against the brief",
    "payout_route": "Eligible payout method is active in the provider account"
  }
}
```

When a sponsor has no fixed close time, use `null` for `closes_at` and choose `recheck_at` from the live brief. Refresh the check before it expires. Keep the original `commissioned_at` timestamp. If the brief requires prior approval, set `preapproval_required` to true and add `draft_approval` with `package_sha256`, `reference`, and `approved_at`.

```sh
python3 studio_campaigns.py preflight BRIEF.json CUT
python3 studio_campaigns.py submission BRIEF.json CUT youtube
python3 studio_campaigns.py readback BRIEF.json CUT youtube PROVIDER-EVIDENCE.json
```

The first command checks independent approval and the exact campaign package; the second returns the canonical public link and applicable deadline. The third verifies that the observed provider record belongs to that post and brief, including historical reads after the campaign closes. The tool reads the local queue, performs no provider writes, and cannot independently authenticate a person's assertions about the paid dashboard. Keep those evidence notes tied to actual owner readback.

Provider evidence contains `campaign_url`, `public_url`, `submission_id`, `submitted_at`, `observed_at`, `status`, and `evidence`. Use `pending`, `approved`, `rejected`, `credited`, or `paid`. A credited or paid record requires a positive provider-reported `amount` as a decimal string and a three-letter `currency`. Use `credited` for a wallet credit, and `paid` only for an observed settled payment. Keep the archived brief, verified output, and provider evidence together.

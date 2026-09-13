# Copilot Integration

**Status: REQUIRES LICENSING VERIFICATION.** This document does not claim
that any specific Copilot API, agent, or MCP server is available to this
company — that is unknown until verified against the real tenant. Do not
implement `RealCopilotAdapter` (`worker/adapters/copilot/real.py`) until the
checklist below has been completed for real. See ADR-005 in `DECISIONS.md`
for why this isolation exists, and CLAUDE.md's explicit instruction: "do not
invent an unofficial API."

The project remains fully usable via `HumanReviewCopilotAdapter` regardless
of the outcome below — that is an acceptable **permanent** state, not a
temporary workaround (ADR-006).

## What "Copilot" could mean here — these are genuinely different products

Microsoft ships several products under the "Copilot" name with very
different automation surfaces. Before writing any code, determine which of
these the company actually has:

1. **Microsoft 365 Copilot** (chat in Word/Outlook/Teams/the M365 Copilot
   app) — primarily a human-facing chat experience. Programmatic invocation
   of a Word/Teams/M365 Copilot chat turn is not a standard, documented
   capability as of this writing; verify against current Microsoft Learn
   docs rather than assuming either way.
2. **Copilot Studio** — a platform for building custom "Copilot" agents,
   which *can* expose programmatic invocation (via a published channel, a
   Direct Line-style API, or — depending on current product capability — an
   agent that other things can call). Requires its own license/capacity.
3. **Copilot agents / "declarative agents"** — agents built for Microsoft
   365 Copilot; invocation model and API surface again need to be checked
   against current docs, as this is a fast-moving product area.
4. **Model Context Protocol (MCP)** — a protocol for connecting tools to
   AI assistants; whether the company's Copilot deployment exposes or
   consumes an MCP server is a tenant-admin-level configuration question,
   not something to assume exists.
5. **Plain Azure OpenAI / Azure AI Foundry access** — technically not
   "Copilot" at all, but if the company has this instead, it would be the
   most straightforward way to get a real `RealCopilotAdapter` working
   with a well-documented REST API. Explicitly flagged as an Azure service,
   which the project brief marks optional — get explicit approval before
   depending on it.

**Do not guess which of these applies. Verify.**

## ✅ Verified finding (2026-09): Copilot Studio Direct Line API

**This resolves the single biggest open question below.** Verified against
Microsoft Learn (not guessed) and cross-checked against a real personal
test tenant with a Copilot Studio trial license (11 existing published
agents found via `pac copilot list`) — see the scope note under "What was
and wasn't verified" at the end of this section.

**Copilot Studio agents CAN be invoked programmatically, via the Direct
Line API — no Azure Bot Service resource, no MCP, and no Graph/Copilot API
required.** This is a standard, documented publishing channel of Copilot
Studio itself:

1. In Copilot Studio, open the agent → **Channels** → **Mobile app** tile.
2. Enabling this channel exposes a **Token Endpoint** URL — a per-agent
   HTTPS endpoint you `GET` with no auth to receive a short-lived Direct
   Line token:
   ```
   GET <token endpoint>
   → {"token": "...", "expires_in": 3600, "conversationId": "..."}
   ```
3. Use that token as a Bearer token against the standard [Bot Framework
   Direct Line REST API](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-concepts)
   (`https://directline.botframework.com/v3/directline/...`) to start a
   conversation, `POST` a message `Activity`, and `GET` activities back
   (poll with a `watermark`, matching Bot Framework's activity protocol —
   the response stream contains both the user's and the agent's messages;
   filter by `From.Name` to isolate the agent's reply).
4. The token expires (`expires_in`, typically 3600s) and can be refreshed
   via `POST .../tokens/refresh` before it does, for longer-running
   conversations — see [Direct Line Authentication](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-authentication#secrets-and-tokens).

This means `RealCopilotAdapter` is very plausibly implementable as: build
one Copilot Studio agent whose only job is "take this normalized
JSON + diff + impact, produce technical doc / user doc / change summary
text" (three separate prompts/turns, or one agent with three topics), wire
`RealCopilotAdapter` to the Direct Line REST API above using Python's
`requests`/`httpx` (no new heavy dependency), and treat the per-agent Token
Endpoint URL as a configuration value (`PPDM_COPILOT_TOKEN_ENDPOINT` — see
"Security considerations" below for why it's sensitive even though it
isn't a traditional secret).

### ⚠️ Live test result on the personal test tenant: blocked by trial license

Attempted the live test on 2026-09-13 against two different existing
published agents (`Productivity Bot PVA`, `AlekTest`) in the personal test
tenant. Clicking **Channels** (or Settings → Security → Web channel
security — same gate) immediately shows a **"Select a Team"** modal stating
**"Wersja próbna wygasła"** ("Trial has expired"), with only two options:
"Learn more" or "Extend trial." This happened identically on both agents,
so it's a tenant-wide license gate, not an agent-specific issue.

**This did not get fixed/clicked through** — extending a trial is a real
licensing/billing decision, not something to do without the account
owner's explicit choice. So: **the Direct Line mechanism above is confirmed
correct per Microsoft's official docs, but was NOT verified end-to-end**,
because this specific tenant's trial state currently blocks the entire
Channels configuration surface (of which Direct Line/Mobile app is one
option among several — Teams, Demo website, etc. are equally blocked).

This is a concrete, useful data point for the company tenant: **whatever
Copilot Studio license the company ends up with must be an active
(non-expired-trial) one** for channel publishing — including Direct Line —
to be configurable at all. A user/Copilot Studio license (even a
non-trial "free" one assigned by an admin once a tenant Copilot Credits
subscription exists) should not hit this gate; only the expired-trial state
does. Verify this doesn't recur on the company tenant during
`docs/CORPORATE_SETUP.md` Phase 7.

### ✅ Follow-up after extending the trial: mechanism confirmed structurally

After the trial was extended (by the tenant owner, not by Claude — a
license/billing decision is not something to take on someone else's
behalf), the Channels page opened fully. Concrete findings:

- The channel is called **"Native app"** ("Aplikacja natywna" in the
  Polish UI tested) rather than "Mobile app" — naming appears to have
  changed since the "Publish an agent to mobile or custom apps" doc was
  written, or is localization-dependent. Same underlying mechanism.
- Opening it now shows a **"Microsoft 365 Agents SDK" connection
  parameters** string (`https://<env-id>.environment.api.powerplatform.com/...`)
  rather than the older doc's plain "Token Endpoint" URL — Microsoft has
  layered a newer, official **Microsoft 365 Agents SDK** (client libraries
  for **.NET, JavaScript, and Python** — [samples on GitHub](https://github.com/microsoft/Agents))
  on top of the same channel. See [Integrate with web or native apps using
  Microsoft 365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-integrate-web-or-native-app-m365-agents-sdk).
- **Important for this project specifically: the Agents SDK does NOT
  support service-principal (app-only/unattended) authentication** — per
  Microsoft's own doc, that's precisely the documented reason to fall back
  to Direct Line instead: *"Use Direct Line API to integrate with Copilot
  Studio... when the Microsoft 365 Agents SDK doesn't support your
  scenario, for example: the Microsoft 365 Agents SDK doesn't support
  service principal tokens."* Since the worker is an unattended background
  process with no interactive user to sign in, **this rules out the newer
  Agents SDK for `RealCopilotAdapter` and confirms Direct Line + a secret
  (not the SDK) is the correct mechanism** — don't be tempted to "upgrade"
  to the newer-looking SDK later without re-reading this.
- **Settings → Security → Web channel security** ("Zabezpieczenia →
  Zabezpieczenia kanału internetowego") is reachable and behaves exactly
  as documented: two independent secrets ("Wpis tajny 1"/"Wpis tajny 2")
  already exist for the agent, each with Regenerate/Copy actions, plus a
  **"Require secured access"** toggle (currently OFF on the test agent —
  meaning, per Microsoft's own warning text shown in the UI, the agent's
  Direct Line channel and demo website are currently open to anyone who
  knows the agent ID, with no secret required).

**What was deliberately NOT done, and why:** the actual secret value was
never retrieved (no "Copy" click, no attempt to read it from the page DOM —
one such attempt, for the *connection parameters* string, was
automatically blocked by the Claude in Chrome extension itself as
cookie/token-like content, which is the correct behavior). The "Require
secured access" toggle was also left untouched — flipping a live security
setting on a real agent (even a personal test one) while unsupervised
isn't something to do without the account owner reviewing it themselves,
and it carries a documented ~2 hour propagation delay. **A full end-to-end
message exchange (get token → post message → read reply) was therefore
not completed** — doing that safely requires the secret to be placed in a
local, git-ignored `.env`/environment variable by the tenant owner
directly, never pasted into a chat/agent conversation, matching this
project's own `SECURITY.md` rules to the letter. This is the same pattern
`RealCopilotAdapter` must follow in production: the Direct Line secret is
an `PPDM_COPILOT_DIRECTLINE_SECRET`-style environment variable, never a
value any AI assistant (including this one) should ever see or handle
directly.

### What was and wasn't verified

- **Verified against official Microsoft Learn docs** (2026, current as of
  this writing): the Direct Line mechanism, its request/response shapes,
  and that it requires no Azure Bot Service resource — this is a fact
  about the product, reusable regardless of which tenant you're on.
- **Verified that Copilot Studio itself is reachable and has real agents**
  against the developer's **personal test tenant** (Copilot Studio trial
  license, Global Admin) via `pac copilot list` — 11 published agents
  exist there. This is **not** the company's tenant.
- **Attempted and blocked**: actually calling the Token Endpoint / Direct
  Line API end-to-end requires enabling the "Mobile app" channel first —
  attempted against two agents on the personal test tenant and blocked by
  an expired-trial gate on the entire Channels area (see above). Still not
  verified end-to-end anywhere. Also not verified: whether the company's
  tenant/license tier (once known) permits enabling this channel, and what
  if any admin policy might block or audit-log Direct Line usage — a
  Copilot Studio admin should confirm this is an acceptable integration
  pattern under company policy before production use, same as any other
  channel.

## Verification checklist (do this before writing any real-adapter code)

- [ ] Which Microsoft 365 / Copilot license SKU(s) does the company hold?
      Check the Microsoft 365 admin center → Billing → Licenses, or ask IT.
- [ ] Is Copilot Studio provisioned/licensed separately? (It often is,
      independent of M365 Copilot seats.)
- [ ] Does the tenant have any Copilot Studio agents already published that
      this project could call, or would a new one need to be built?
- [ ] Is programmatic/API invocation of a Copilot Studio agent enabled for
      this tenant? Check current Microsoft Learn documentation for Copilot
      Studio's supported invocation channels (this changes over time — do
      not rely on this document's product descriptions being current;
      re-check at implementation time).
- [ ] Is an MCP server available/permitted in this tenant for any Microsoft
      365 or Copilot Studio integration? Check current Microsoft
      documentation and any tenant-level admin policy.
- [ ] Does the company have separate Azure OpenAI / Azure AI Foundry
      access that could be used instead (with explicit approval, since it's
      an Azure dependency)?
- [ ] What authentication is required for whichever API surface applies —
      an app registration (client credentials), a user-delegated token, or
      something else? What Azure AD/Entra ID permissions/consent does that
      require, and who can grant them?
- [ ] What are the tenant's data-handling/compliance rules for what can be
      sent to Copilot (even the normalized representation — no raw exports
      — see "Security considerations" below)?
- [ ] If none of the above yields programmatic access: confirm that
      `HumanReviewCopilotAdapter` is an acceptable permanent operating mode
      for this tool (it should be — say so explicitly to stakeholders).

## Required licensing (fill in once verified — do not guess)

| Product | Licensed? | SKU | Notes |
|---|---|---|---|
| Microsoft 365 Copilot | _unknown_ | | |
| Copilot Studio | _unknown_ | | |
| Azure OpenAI / AI Foundry | _unknown_ | | |

## Required permissions (fill in once verified)

- Azure AD/Entra ID app registration scopes: _unknown — depends on chosen API_.
- Consent type (admin consent vs. per-user): _unknown_.
- Any Copilot Studio "agent caller" or equivalent role: _unknown_.

## Authentication (fill in once verified)

Do not assume OAuth client-credentials flow works for whichever API is
chosen — some Copilot-adjacent APIs require delegated (user) auth only.
Verify against the specific product's current documentation.

## Security considerations

- Only the **normalized representation** (see `worker/normalization/`),
  diff, and impact assessment are ever sent to Copilot — never a raw
  solution export, never credentials, never full environment variable
  *values* if any happen to be secret-shaped. See ADR-007 and
  SECURITY.md "Sensitive information handling".
- Whatever Copilot product is used, confirm the company's data-residency
  and training-opt-out settings (does input get used to train models? Is
  data processed/stored outside an approved region?) before sending real
  application data through it.
- `RealCopilotAdapter`'s credentials belong to the worker's service
  identity, scoped as narrowly as the chosen API allows — never a personal
  account's token embedded in config.

## Fallback if automation is unavailable

`HumanReviewCopilotAdapter` (`worker/adapters/copilot/human_review.py`) is
the fully-supported fallback: it writes a self-contained, ready-to-paste
prompt (normalized snapshot + diff + impact, structured output instructions),
marks the job `NEEDS_HUMAN_REVIEW`, and resumes automatically once an
administrator pastes the Copilot result back via
`JobProcessor.resume_needs_human_review()`. This is not a lesser mode — it
is designed to be a completely acceptable steady-state if no programmatic
access ever materializes.

## Implementation note for whoever picks this up later

Once the checklist above is complete, implement `RealCopilotAdapter` using
**Direct Line with a secret**, not the Microsoft 365 Agents SDK — the
Agents SDK is the newer/more prominent option in the Copilot Studio UI, but
it does not support unattended service-principal authentication (confirmed
against Microsoft's own docs, see "Follow-up after extending the trial"
above), which the worker needs since it has no interactive user to sign in.
Concretely:
1. Build the same `context` shape `HumanReviewCopilotAdapter` builds a
   prompt from (see `worker/adapters/copilot/human_review.py
   build_human_prompt()`).
2. Exchange a Direct Line secret (from Settings → Security → Web channel
   security, an env-var-only value — see SECURITY.md) for a token via
   `POST https://directline.botframework.com/v3/directline/tokens/generate`,
   start a conversation, `POST` an `Activity` with the prompt content, and
   `GET` activities back (poll with a `watermark`) filtering by the
   agent's name to isolate its reply.
3. Parse the response into the same three-part structure (technical doc,
   user doc, change summary) the mock/human-review paths produce.
4. Handle failures by raising a normal exception (job processor already
   retries automatically) — do NOT silently fall back to
   `HumanReviewCopilotAdapter` inside `RealCopilotAdapter`; that decision
   belongs in `worker/config.py`/`adapters/factory.py`, not hidden inside
   an adapter.

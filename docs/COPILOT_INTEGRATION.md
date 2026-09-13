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

Once the checklist above is complete, implement `RealCopilotAdapter` to:
1. Build the same `context` shape `HumanReviewCopilotAdapter` builds a
   prompt from (see `worker/adapters/copilot/human_review.py
   build_human_prompt()`).
2. Call the verified API with that content.
3. Parse the response into the same three-part structure (technical doc,
   user doc, change summary) the mock/human-review paths produce.
4. Handle failures by raising a normal exception (job processor already
   retries automatically) — do NOT silently fall back to
   `HumanReviewCopilotAdapter` inside `RealCopilotAdapter`; that decision
   belongs in `worker/config.py`/`adapters/factory.py`, not hidden inside
   an adapter.

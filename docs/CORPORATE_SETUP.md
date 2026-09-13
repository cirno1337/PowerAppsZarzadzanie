# Corporate Setup Guide

This document is written for you personally, for the day you regain access
to your company's network. It is a checklist, in order, to go from "fully
offline mock development" to "connected to the real Power Platform tenant"
— without ever guessing a real value or blocking on something you can't
verify yet. Work through phases in order; each one only needs what's listed
in it.

Nothing in this repository currently contains real tenant IDs, site URLs,
environment URLs, or credentials, and it must stay that way — fill in real
values only in your own local `.env` (git-ignored) or the eventual
production host's secret store, never in a file tracked by Git.

---

## PHASE 1 — Gather information

Work through this list with whatever access you have (colleagues, admin
portals, prior documentation) before touching any code:

- [ ] Power Platform environment URLs (DEV/TEST/UAT/PROD or whatever the
      company's real names are)
- [ ] Environment names (as they appear in the Power Platform admin center)
- [ ] Solution name(s) for the application(s) you'll document first
- [ ] SharePoint site URL where this tool's lists/library will live
- [ ] SharePoint list names to use (can match `sharepoint/lists/*.json`
      exactly, or adapt — record the actual choice here)
- [ ] SharePoint document library name (`PowerPlatformDocumentation` is the
      default assumed throughout this repo)
- [ ] Microsoft account/service identity the worker will authenticate as
- [ ] Worker machine (which VM/server, or "my own machine for now")
- [ ] Network/VPN requirements to reach SharePoint/Power Platform from that
      machine
- [ ] Power Platform permissions available to your account and to the
      intended worker service identity
- [ ] SharePoint permissions available to your account and to the intended
      worker service identity
- [ ] Copilot product/license actually held by the company (see Phase 7)
- [ ] Copilot Studio availability
- [ ] MCP availability (tenant-level, if applicable)
- [ ] API availability for whichever Copilot product applies
- [ ] Security restrictions relevant to this project (data classification
      rules, egress restrictions, approved authentication methods)
- [ ] Service account policy (how to request one, who approves it)

Record answers wherever your company keeps this kind of internal
documentation — not inside this Git repository unless it's genuinely safe
to be there (site/list *names* are fine; URLs are borderline — prefer
keeping URLs in your local `.env` only).

---

## PHASE 2 — Validate Power Platform CLI

See `docs/POWER_PLATFORM_SETUP.md` for the full command reference. Quick
path:

**Safe (read-only) commands:**
```bash
pac --version
pac auth create --url <environment-url>
pac org list
pac solution list
```

**Safe (export-only, non-destructive) commands:**
```bash
pac solution export --name <solution-name> --path ./export --managed false
pac solution unpack --zipfile ./export/<solution>.zip --folder ./unpacked
```

**Do NOT run** without explicit approval: `pac solution import`, any
`pac admin` environment-lifecycle command, anything under `pac data` that
writes. This project's worker never needs these.

- [x] `pac` CLI installed and version confirmed — done against a
      **personal test tenant** (2026-09), not the company tenant: `pac`
      2.12.2 via `dotnet tool install --global Microsoft.PowerApps.CLI.Tool`
      (requires .NET SDK + the `aspnet-runtime` package on Linux — see
      `docs/POWER_PLATFORM_SETUP.md`).
- [x] Authenticated against a real, non-production environment — device
      -code auth (`pac auth create --deviceCode`) confirmed to work well
      for a headless/terminal session. Still REQUIRES CORPORATE ACCESS to
      confirm which auth method (device code vs. service principal vs.
      managed identity) the company allows for the worker's own
      unattended, non-interactive use.
- [x] `pac solution list` succeeds and shows expected solutions — done on
      the personal test tenant.
- [x] `pac solution export` + `pac solution unpack` succeed — done on the
      personal test tenant against a small unmanaged test solution.
- [x] Actual unpacked folder structure compared against what
      `worker/normalization/normalizer.py` assumes — differs substantially
      (real export is XML + Logic-Apps-style JSON, not flat JSON like the
      mock fixtures). `RealPowerPlatformAdapter` +
      `worker/adapters/powerplatform/xml_parsing.py` now implement real
      parsing for solution metadata, flows, environment variables, and
      connection references — see `docs/POWER_PLATFORM_SETUP.md` "Real
      export structure — verified findings" for the full detail. Canvas
      apps, tables, roles, and generic components remain unverified.
- [ ] **Still required**: repeat the above against the actual **company**
      tenant/environment once accessible, and confirm the worker's
      unattended authentication method with whoever administers it.

---

## PHASE 3 — SharePoint

Follow `docs/SHAREPOINT_SETUP.md` and `sharepoint/README.md`. In short:

- [x] **Verified working (2026-09) on a personal test tenant**:
      `scripts/provision_sharepoint_graph.py` (Microsoft Graph, app-only
      auth) created a fresh test site, all 4 lists with exact
      columns, the cross-list lookup, and the `PowerPlatformDocumentation`
      library with `_jobs`/`_templates`/`_logs` folders — in one run,
      idempotent on re-run. This is now the recommended provisioning path
      (ahead of the untested PnP PowerShell script).
- [ ] **Still required for the company tenant**: create (or pick) the real
      site, create an Azure AD app registration with Graph `Sites.Manage.All`
      (Application permission, admin consent granted) scoped to it, run
      `scripts/provision_sharepoint_graph.py` with that tenant's
      `TENANT_ID`/`CLIENT_ID`/`CLIENT_SECRET`/`SHAREPOINT_SITE_URL` in a
      local `.env`.
- [ ] Record any internal-name mangling in `docs/SHAREPOINT_SETUP.md`'s
      table
- [ ] Grant the worker's actual production service identity Contribute
      permission on this site/these lists/this library only — the app
      registration used for one-off provisioning (`Sites.Manage.All`,
      broad) should NOT be the same credential the production worker runs
      as long-term; narrow it once `RealSharePointAdapter` is implemented
      (see SECURITY.md "Least privilege").

---

## PHASE 4 — Power Apps

Follow `powerapps/README.md` screen-by-screen. In short:

- [ ] Create a new canvas app connected to the four SharePoint lists as
      data sources
- [ ] Build the 9 screens per `powerapps/README.md`, using the Power Fx
      formulas there as a starting point (verify connector-specific syntax,
      e.g. the `Person` column patch shape, against your actual connector
      version)
- [ ] Confirm no screen/formula uses a Premium or custom connector, an HTTP
      action, or Dataverse (they shouldn't — the design avoids all three by
      construction, but verify)
- [ ] Share the app with the intended user group; confirm SharePoint list
      permissions flow through correctly (Power Apps uses the running
      user's own SharePoint permissions, not a shared service identity)

---

## PHASE 5 — Power Automate

Follow `powerautomate/README.md`. In short:

- [ ] Build Flow 1 (job status notification) using only the SharePoint and
      Office 365 Outlook standard connectors
- [ ] Optionally build Flow 2 (stale job reminder) and Flow 3 (new
      application registered notification)
- [ ] Confirm the connector inventory used matches
      `powerautomate/README.md`'s table (no Premium/HTTP/custom connector)
- [ ] Test that a flow failure does not affect job processing — it's
      notification-only (ADR-003)

---

## PHASE 6 — Worker

Follow `docs/WORKER_SETUP.md`. In short:

- [ ] Decide where the worker runs for now (your machine is fine to start)
- [ ] Install Python 3.10+ and `pac` CLI on that machine
- [ ] Copy `config/.env.example` to a local, git-ignored `.env`; fill in
      real values (`PPDM_SHAREPOINT_SITE_URL`,
      `PPDM_POWERPLATFORM_ENVIRONMENT_URL`, and set
      `PPDM_POWERPLATFORM_MODE=real` / `PPDM_SHAREPOINT_MODE=real` only
      once their real adapters are implemented — see Phases 2/3/5 of
      ROADMAP.md, Milestones 5/6)
- [ ] Decide the worker's authentication approach (service principal,
      managed identity, etc.) — see SECURITY.md
- [ ] Decide scheduling (`--once` under a scheduled task, or continuous
      mode as a service) — see `docs/DEPLOYMENT.md`
- [ ] Confirm logging output contains no secrets (spot-check before this
      goes anywhere with broader log retention/forwarding)
- [ ] Run `./scripts/run-tests.sh` on the target machine to confirm the
      Python environment works there too

---

## PHASE 7 — Copilot

Follow `docs/COPILOT_INTEGRATION.md` in full — it has the complete
verification checklist, including a **real, verified finding (2026-09)**
that programmatic invocation IS possible via the Copilot Studio Direct
Line API (not the newer Microsoft 365 Agents SDK — that one doesn't
support unattended/service-principal auth, which the worker needs). That
finding was verified against Microsoft's own docs and structurally
confirmed on a personal test tenant; it still needs re-confirming against
the company's actual tenant/license (steps below).

Summary diagnostic steps:

1. **What Copilot license(s) does the company hold?** Check the Microsoft
   365 admin center → Billing → Licenses (or ask IT/procurement). Look
   specifically for Microsoft 365 Copilot seats vs. Copilot Studio capacity
   — they're licensed and provisioned separately. **Also check that it
   isn't an expired/trial license** — a trial-expired state was found to
   block the entire Channels configuration area (not just one channel) on
   a personal test tenant; see `docs/COPILOT_INTEGRATION.md`.
2. **Is Copilot Studio available?** Check
   [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
   (current as of 2026-09; the older `make.powerva.microsoft.com` URL still
   redirects there but verify, product URLs change) for your tenant. If you
   can create/open an agent there, Copilot Studio is available.
3. **Is programmatic invocation possible?** Open an existing (or new)
   agent → **Channels** → **Native app**, and separately check
   **Settings → Security → Web channel security**. If both are reachable
   (not blocked by a trial/licensing gate) and show a connection
   string/secrets, Direct Line invocation is available — this is the
   single most important thing to verify, and confirms/refutes the
   personal-tenant finding above for the *company's* tenant specifically.
4. **Is MCP available?** Check current Microsoft documentation for MCP
   support in whichever Copilot product applies, and check tenant admin
   policy (an admin may need to enable it).
5. **If none of the above give programmatic access:** human-in-the-loop
   (`HumanReviewCopilotAdapter`) is your answer, and that's fine — see
   ADR-006. Confirm with stakeholders that this is an acceptable permanent
   mode of operation (it should be: it still fully automates the
   normalization/diff/impact/version-tracking work, just not the final
   prose generation).

Do NOT invent undocumented procedures — link to official Microsoft
documentation for whatever you find, and record the links + findings in
`docs/COPILOT_INTEGRATION.md`'s tables.

---

## PHASE 8 — First real test

**Must not modify production.**

1. Pick a small, non-production Power Platform solution (ideally a
   throwaway test solution you create specifically for this).
2. Register it in the Applications list (via the Power App, once built, or
   directly in SharePoint for a quick first test).
3. Set `PPDM_POWERPLATFORM_MODE=real`, `PPDM_SHAREPOINT_MODE=real` in your
   local `.env` (only after both real adapters are actually implemented —
   see ROADMAP.md Milestones 5-6).
4. Run `python -m worker.main --once` and confirm:
   - [ ] The job is claimed and processed without error
   - [ ] `snapshot.json`/`solution-info.json`/`diff.json`/`*.md` appear in
         the real document library
   - [ ] The `Applications` and `DocumentationVersions` list rows update
         correctly
   - [ ] No credential or secret appears anywhere in the generated
         documentation, logs, or SharePoint list values
5. Only after this succeeds cleanly against a non-production solution,
   consider registering a real production application.

---

## PHASE 9 — Production readiness

- [ ] **Security:** service account uses least-privilege permissions (see
      SECURITY.md); no credentials in Git/config/docs/SharePoint values
- [ ] **Permissions:** SharePoint site/list/library permissions reviewed;
      Power Platform environment permissions reviewed
- [ ] **Logging:** log retention/forwarding policy confirmed compatible
      with "no secrets, no full payloads" (SECURITY.md "Logging policy")
- [ ] **Backups:** confirm SharePoint's own versioning/retention covers the
      document library and lists adequately, or add an explicit backup step
- [ ] **Retries:** `PPDM_MAX_RETRIES` tuned appropriately for production
      job volume/failure patterns
- [ ] **Monitoring:** alerting configured for jobs stuck `FAILED` or
      `NEEDS_HUMAN_REVIEW` beyond a reasonable threshold
- [ ] **Rollback:** documented and understood (see `docs/DEPLOYMENT.md`
      "Rollback plan" — documentation versions are append-only by design)
- [ ] **Documentation:** this repository's own docs are up to date with
      the real values/decisions made across Phases 1-8 (update
      `docs/DEPLOYMENT.md`'s "Decision record" table at minimum)
- [ ] **Support:** who gets paged/contacted when a job fails repeatedly or
      the worker process dies
- [ ] **Ownership:** who owns this tool going forward (you, a team, a
      service owner) — record it somewhere durable (e.g. this file's
      header, or wherever your company tracks internal tool ownership)

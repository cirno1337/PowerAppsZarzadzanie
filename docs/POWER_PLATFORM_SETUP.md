# Power Platform Setup

**Status: REQUIRES CORPORATE ACCESS for anything beyond installing the CLI
locally.** Nothing in this document has been run against a real tenant from
this repository — verify everything here against
[Microsoft's official Power Platform CLI documentation](https://learn.microsoft.com/power-platform/developer/cli/introduction)
before relying on it.

## Installing the CLI (safe to do offline, verify version once online)

```bash
# via .NET tool (cross-platform)
dotnet tool install --global Microsoft.PowerApps.CLI.Tool

# or via npm
npm install -g @microsoft/powerplatform-cli

pac --version
```

## Commands that are safe to run against a real tenant (read-only)

These only read state — safe to run for reconnaissance once you have
corporate network access:

```bash
pac auth create --url <environment-url>     # interactive sign-in
pac auth list                                 # show authenticated profiles
pac org list                                  # list environments you can access
pac org select --environment <environment-url>
pac solution list                              # list solutions in the selected environment
```

## Commands that read AND export (safe — does not modify the environment)

```bash
pac solution export --name <solution-name> --path ./export --managed false
pac solution unpack --zipfile ./export/<solution>.zip --folder ./unpacked --packagetype Unmanaged
```

Exporting is non-destructive. Do this against a **non-production**
environment for your first real test — see `docs/CORPORATE_SETUP.md` Phase
8.

## Commands that COULD modify an environment — do not run without explicit approval

- `pac solution import` — deploys a solution into an environment.
- `pac solution publish-all` / any `pac admin` environment-lifecycle command
  (create/delete/reset/copy an environment).
- Anything under `pac data` that writes.

**This project's worker never needs any of the above** — it only exports
and reads. If a future feature seems to need one of these, stop and get
explicit approval first (per CLAUDE.md's destructive-action guidance).

## Mapping to `RealPowerPlatformAdapter`

See `worker/adapters/powerplatform/real.py` for the intended (unverified)
mapping from adapter methods to `pac` commands. Implement it only after
running the safe commands above against a real, non-production environment
and confirming the actual output shape (solution export ZIP structure,
`Solution.xml` fields, canvas app JSON schema version, etc.) — Power
Platform's export format has changed across CLI/platform versions, so don't
assume the shape without checking.

## What to verify before writing `RealPowerPlatformAdapter`

- [ ] Exact `pac` CLI version available in the company's approved tooling.
- [ ] Environment URL(s) for DEV/TEST/UAT/PROD (or whatever the company's
      real environment names are) — REQUIRES TENANT CONFIGURATION.
- [ ] Authentication method the worker's service identity will use
      (`pac auth create` supports interactive, device code, service
      principal with client secret, and managed identity — which one the
      company allows is a security decision, not a technical one; see
      SECURITY.md and `docs/CORPORATE_SETUP.md` Phase 1).
- [ ] Minimum Power Platform role needed to export a solution (see
      SECURITY.md "Least privilege").
- [ ] Actual structure of an unpacked solution for a real canvas app + flow
      (field names inside `Solution.xml`, `CanvasApps/*.json`,
      `Workflows/*.json`) — update `worker/normalization/normalizer.py`'s
      raw-input assumptions to match reality; the mock fixtures are a
      simplification, not a guarantee of the real shape.

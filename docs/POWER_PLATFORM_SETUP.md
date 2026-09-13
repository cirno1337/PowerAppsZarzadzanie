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

- [x] Exact `pac` CLI version available in the company's approved tooling.
      **Verified 2026-09 against a personal/test tenant** (not the
      company's own — see note below): `pac` CLI 2.12.2 via
      `dotnet tool install --global Microsoft.PowerApps.CLI.Tool`
      (.NET 10 SDK). Note: the npm package some older guidance/memory
      suggests (`@microsoft/powerplatform-cli`) does **not** exist — the
      only supported install methods per Microsoft Learn are the VS Code
      extension, the .NET Tool, and the Windows MSI. Do not `npm install`
      it.
- [ ] Environment URL(s) for DEV/TEST/UAT/PROD (or whatever the company's
      real environment names are) — REQUIRES TENANT CONFIGURATION. (Still
      unknown for the actual company tenant — the exploration below used a
      personal test tenant, not company infrastructure.)
- [ ] Authentication method the worker's service identity will use
      (`pac auth create` supports interactive, device code, service
      principal with client secret, and managed identity — which one the
      company allows is a security decision, not a technical one; see
      SECURITY.md and `docs/CORPORATE_SETUP.md` Phase 1). Device-code auth
      (`pac auth create --deviceCode`) was confirmed to work well for a
      headless/terminal-only session — useful for the worker's own
      first-time setup on a server with no browser.
- [ ] Minimum Power Platform role needed to export a solution (see
      SECURITY.md "Least privilege") — not yet isolated; the exploration
      below used a Global Admin account, which is *not* representative of
      the worker's eventual least-privilege identity.
- [x] Actual structure of an unpacked solution — **verified against a real
      (personal test tenant, non-production) solution export**, and it
      differs substantially from the simplified mock fixtures. See
      "Real export structure — verified findings" below.

### ⚠️ Important scope note on the verification below

The findings below come from **the developer's own personal Power
Platform trial tenant** (Copilot Studio trial license, Global Admin/Power
Platform Admin/SharePoint Admin on that tenant) — explicitly **not** the
company's tenant referenced elsewhere in this repo. This is enough to
verify *how the Power Platform CLI and export format actually behave*
(a fact about the product, not about any specific company), which is
exactly what was previously unverifiable offline. It does **not** satisfy
`docs/CORPORATE_SETUP.md` Phase 1 (real company environment URLs,
permissions, service account policy) — that phase still requires the
actual company tenant. Treat the structural findings below as trustworthy;
treat any environment name, URL, or org identifier from this exploration
as belonging to a personal test tenant, not the company.

### Real export structure — verified findings

Exported and unpacked a small unmanaged test solution
(`pac solution export --managed false` + `pac solution unpack
--packagetype Unmanaged`). Layout:

```
<unpacked>/
    Other/
        Solution.xml                  # solution manifest — see below
        Customizations.xml            # connection references, and most
                                       # other customizations, live here
    environmentvariabledefinitions/
        <schemaname>/
            environmentvariabledefinition.xml   # type, display name, schema name
            environmentvariablevalues.json       # {"environmentvariablevalues": {"environmentvariablevalue": {"value": "..."}}}
    Workflows/
        <Name>-<Guid>.json             # the actual flow definition
        <Name>-<Guid>.json.data.xml    # workflow entity metadata (name, category, etc.)
```

**`Other/Solution.xml`** is XML, not JSON (the mock's `solution.json` is a
deliberate MVP simplification — `RealPowerPlatformAdapter.get_solution_metadata()`
must parse XML):
```xml
<SolutionManifest>
  <UniqueName>TestConcepts</UniqueName>
  <Version>1.0.0.0</Version>
  <Managed>0</Managed>
  <Publisher><UniqueName>DefaultPublisherorga34f8d56</UniqueName>...</Publisher>
</SolutionManifest>
```
Maps to `worker/normalization/schema.py`'s `solution` fields as:
`name` = `UniqueName`, `version` = `Version`, `publisher` =
`Publisher/UniqueName`. No solution-level `description` field exists in
`Solution.xml` in this tenant's export — `LocalizedNames`/`Descriptions`
under `SolutionManifest` were empty here; treat description as
best-effort/optional in the real adapter, not guaranteed.

**A flow's JSON** (`Workflows/<name>-<guid>.json`) is a full Logic
Apps-style workflow definition, not the mock's flat
`{"actions": ["a", "b"]}` shape:
```json
{
  "properties": {
    "connectionReferences": {"shared_sharepointonline": {"connection": {"connectionReferenceLogicalName": "new_testSharePoint"}, "api": {"name": "shared_sharepointonline"}}},
    "definition": {
      "triggers": {"manual": {"type": "Request", "kind": "Button", ...}},
      "actions": {"Get_items": {"type": "OpenApiConnection", "inputs": {...}, "runAfter": {}}}
    }
  }
}
```
`triggers` and `actions` are **objects keyed by step name**, each with a
`type` and rich `inputs`, not an ordered list of plain strings.
`RealPowerPlatformAdapter`/a real-mode normalizer extension will need to:
1. Take `properties.definition.triggers` — usually exactly one entry —
   and summarize it (e.g. `f"{kind} ({type})"` or a fuller description).
2. Walk `properties.definition.actions`, using each key as the action
   name and `runAfter` to reconstruct execution order (the real format
   has no implicit array order — order is a DAG via `runAfter`), to
   produce the ordered `actions: [...]` list the normalized schema
   expects.
3. Extract `properties.connectionReferences` (a dict keyed by connector
   alias) as an additional cross-check against the solution-level
   connection references in `Customizations.xml`.
   This is real, non-trivial mapping work — do not assume it's a
   one-line change when Milestone 5 is picked up.

**Connection references** live in `Other/Customizations.xml` under
`<connectionreferences>`, one `<connectionreference>` per reference:
```xml
<connectionreference connectionreferencelogicalname="new_testSharePoint">
  <connectionreferencedisplayname>testSharePoint</connectionreferencedisplayname>
  <connectorid>/providers/Microsoft.PowerApps/apis/shared_sharepointonline</connectorid>
  ...
</connectionreference>
```
Maps to the normalized schema's `connection_references[].name` (use
`connectionreferencelogicalname` or `connectionreferencedisplayname` —
decide which once a real canvas app is also inspected) and `.connector`
(derive a friendly name from the last segment of `connectorid`, e.g.
`shared_sharepointonline` → `SharePoint`; there's no built-in friendly-name
mapping in the export itself, so `RealPowerPlatformAdapter` will need a
small lookup table for common standard connectors, or accept the raw
`shared_*` API name as `connector` and let documentation generation render
it as-is).

**Environment variables** get one subfolder per variable
(`environmentvariabledefinitions/<schemaname>/`), split across an XML
definition file (`type` as a numeric code, e.g. `100000004`; no
human-readable type string) and a separate JSON values file holding the
actual default value. `RealPowerPlatformAdapter.get_application_metadata()`
will need a numeric-type-code → friendly-name lookup table (Microsoft
Learn's environment variable type reference) to populate the normalized
schema's `environment_variables[].type` with something readable, rather
than a bare number.

**Not yet verified**: canvas app (`CanvasApps/*.json` / `.msapp`)
structure, security roles, and a managed (vs. unmanaged) export's
differences — do this against a real canvas app solution before finishing
`RealPowerPlatformAdapter`.

### Capstone: full real pipeline run (2026-09) — three more real bugs found

`RealPowerPlatformAdapter` was run through the complete `JobProcessor`
pipeline (together with `RealSharePointAdapter`, see
`docs/SHAREPOINT_SETUP.md`) against the real personal test tenant, twice
— `COMPLETED` both times, correctly producing version `1.0` then `1.1`.
Three real bugs surfaced only by actually running this (all fixed, all now
covered by regression tests — see `ROADMAP.md` Milestone 5 for the fourth,
in `job_processor.py`):

1. **`authenticate()` always ran `pac auth create`**, which starts a
   *fresh* login — harmless when run interactively once, but would hang a
   headless worker indefinitely if an auth profile for the environment
   already exists (as it will, in steady-state operation). Fixed with
   `pac_cli.ensure_authenticated()`: check `pac auth list` for a profile
   already pointed at the target environment and `pac auth select` it;
   only fall back to `pac auth create` if none exists.
2. **`pac solution export` fails if the output path already exists** (no
   overwrite by default) — breaks any re-run using the same export
   directory (a retry, or a later `UPDATE_DOCUMENTATION` job for the same
   solution). Fixed by passing `--overwrite` — the export is a disposable
   working file, not a retained artifact, so overwriting it is safe.
3. **Flow display names retained part of the GUID.** Real workflow
   filenames look like `Button-Getitems-53E8B648-3F25-EE11-9965-6045BD0D0CC5.json`
   — the GUID itself contains internal hyphens, so the original
   `rsplit("-", 1)` only stripped the last hyphen segment
   (`6045BD0D0CC5`), leaving most of the GUID in the "name" used for
   diffing. Fixed with a regex matching the full 8-4-4-4-12 GUID pattern.

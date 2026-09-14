# Contributing

This is currently a solo/internal project developed offline-first. These
notes exist so any future contributor (including a future Claude Code
session) works consistently.

## Before you start

Read `CLAUDE.md` in full — it is the authoritative guide for architectural
principles, conventions, and the "do not do" list. `ARCHITECTURE.md` and
`DECISIONS.md` explain the why behind the structure.

## Local setup

```bash
./scripts/setup.sh      # creates a venv, installs test dependencies
./scripts/run-tests.sh  # runs the full pytest suite against mock adapters
./scripts/demo.sh        # runs the full mock pipeline and prints a summary
```

No network access, corporate VPN, or Microsoft account is required for any
of the above.

## Making a change

1. If the change affects an adapter interface, a schema (normalized
   representation, diff model), or the no-Premium constraint, write an ADR
   in `DECISIONS.md` first.
2. Add or update unit tests alongside the code change — see "Testing
   requirements" in `CLAUDE.md`.
3. Run `./scripts/run-tests.sh` and fix failures before considering the
   change done.
4. Update `ROADMAP.md` status markers and any affected doc under `docs/`.
5. Keep commits scoped to one logical change with a message explaining why,
   not just what.

## Code style

- Python: standard library first, type hints on public functions,
  dataclasses for structured records, `abc.ABC` for adapter interfaces. No
  linters/formatters are wired in yet; keep formatting close to PEP 8 by
  hand until one is added (ask before adding a formatter/linter dependency).
- Docs: Markdown, one topic per file, `<placeholder>` syntax for any value
  that depends on the real corporate tenant.

## What not to do

See the "Do not do" section of `CLAUDE.md` — it is not optional guidance.

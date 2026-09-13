# Local Development

## Day-to-day loop

```bash
source .venv/bin/activate
./scripts/run-tests.sh -k <pattern>   # fast, targeted test run while iterating
./scripts/run-tests.sh                # full suite before considering a change done
./scripts/demo.sh                      # sanity-check the whole pipeline end-to-end
```

## Adding a new normalized component category

1. Add the raw fixture key to `_RAW_LIST_FILES` in
   `worker/adapters/powerplatform/mock.py` (and a corresponding JSON file in
   both `examples/mock_solution/InvoiceApproval/v1.0/` and `v1.1/`).
2. Add a builder function in `worker/normalization/normalizer.py` and wire
   it into `normalize()`.
3. Add a `compare_*` function and a call to `_diff_named_list(...)` in
   `worker/diff/engine.py`.
4. Add a rule branch in `worker/diff/impact.py` `assess_change_impact()`.
5. Render the new category somewhere sensible in
   `worker/documentation/generator.py`.
6. Add unit tests for steps 2-4 and update
   `worker/tests/test_integration_pipeline.py` if the v1.0→v1.1 fixture
   change set should include the new category.

## Adding a new job action

1. Add the value to `JobAction` in `worker/models.py`.
2. Add the SharePoint `Choice` value in `sharepoint/lists/DocumentationJobs.json`.
3. Add a handler method to `worker/job_processor.py` and register it in
   `_handler_for()`.
4. Add a unit test.
5. Document the corresponding Power Apps action in `powerapps/README.md`.

## Changing an adapter interface

Write an ADR in `DECISIONS.md` first (see CLAUDE.md "How to make
architectural decisions") — adapter interfaces are the seam the whole
offline-first strategy depends on.

## Inspecting mock/demo state

Everything the mock adapters write lives under `.local_data/` (git-ignored).
Delete it any time to reset to a clean slate — nothing outside that
directory is mutated by tests or the demo script.

```bash
rm -rf .local_data
```

## Style

See CONTRIBUTING.md and CLAUDE.md "Coding conventions". No linter/formatter
is configured yet — ask before adding one (a new dependency + config choice
that affects the whole repo).

# Getting started

Read `README.md` for implemented behavior and `context.md` for the sleep target.
Use `ml/sleep/README.md` for setup, schema and PC commands. Run Python and C host
checks before a board build.

For firmware, initialize `git submodule update --init --recursive`, import this
existing project into e2 studio, select Debug and use `SETUP_NOTES.md` for the
historical setup. The application runs labelled synthetic replay; `DEMO.md`
describes expected output. Board behavior needs verification.

Preserve generated `ra_gen/`, `ra_cfg/` and vendor `ra/` content. Configure new
peripherals through FSP and regenerate after hardware/pin review.

This machine has a project-local test environment at `.venv/Scripts/python.exe`.
The standalone `py` launcher has no registered interpreter. Historical bearing
scripts moved to `ml/legacy_bearing/`; existing downloads remain at `ml/data/`.

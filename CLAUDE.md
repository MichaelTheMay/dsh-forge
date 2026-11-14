# DSH Forge

A catalog browser and local launcher for DeepSeek Harness (DSH) plugins and forks: discover them, find the hidden gems, install and run them in a sandbox on your own machine.

## Commands
- `make check`: whitespace, syntax, embedded-catalog drift, JS tests, Python tests, gem tests, preview build. **Exactly what CI runs.** Must be green before every commit.
- `make test-py` / `make test-js` / `make test-gems`: one suite only.
- `python3 scripts/serve.py --sync-catalog`: start the app from source.

## Where things are
- `dsh_forge/`: the launcher backend (stdlib only). `scripts/serve.py` is the local HTTP server and app entry.
- `web/index.html` + `web/launcher.js`: the whole interface. No build step.
- `api/`: Vercel functions for the public site (catalog, sign-in, likes, favorites).
- `gems/`: the hidden-gem system. Separate on purpose: it reads catalog files and writes `gem-picks.json`; the app only reads that file. See `gems/README.md`.
- `tests/`: app tests. `gems/tests/`: gem-system tests.
- `docs/PROBLEM.md`: the original brief, verbatim. `docs/decisions.md`: settled decisions (append, don't rewrite). `docs/PLAN.md`: milestones, the source of truth for scope and order. `docs/architecture.md`: system diagram.

## Working rules
- Work through `docs/PLAN.md` one milestone at a time on `feat/platform-v1`. Nothing merges to `main` or deploys to production without Michael's explicit OK.
- Every behaviour change ships with a test in the same commit. Refactors and behaviour changes go in separate commits.
- Conventional Commits, small and atomic.
- **No new dependencies.** Python is stdlib only (3.9+); the web UI has no packages. If something seems to need one, find another way or ask.
- Interface text is plain language. No commit hashes, environment variable names, or container jargon on screen.
- Community code never runs on the host: only inside the Apptainer sandbox.
- Session logs are private. Store counts, never message text; never commit a real session log as a fixture.
- Before reporting a visual change done, open it in a real browser and look at it.
- If a decision changes, append it to `docs/decisions.md`. If components or data flow change, update `docs/architecture.md`.

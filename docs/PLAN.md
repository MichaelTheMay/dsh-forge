# Plan

Approved by Michael on 2026-11-13. Decisions behind it are in [decisions.md](decisions.md); the system diagram is in [architecture.md](architecture.md).

## Context

DSH Forge is a catalog browser and local launcher for DeepSeek Harness plugins and forks. The Discord history shows the same blockers repeated since September: hidden-gem discovery is not the in-depth system Michael wanted, the interface exposes technical details, there is no launch-ready desktop path, and the bigger platform ideas (recommendations from your own sessions, parallel sessions on different saved configurations) were never started.

Current state, verified:
- `origin/main` has discovery v3 (statistics only, never opens a repo), packs, likes, GitHub sign-in (switched off), saved configurations with CLI run, an MCP server and an Assistant tab.
- The daily catalog job has failed since Nov 11 on one upstream entry with an empty description; the site serves the Nov 10 catalog.
- 12 Python tests fail only on machines with a real `dsh` on PATH (test isolation, not bugs).
- Running anything needs Apptainer, which is not installed on this machine.

Outcome wanted: one autonomous build, on an integration branch, that ends with a launch-ready Linux app plus web catalog, a separate and evaluated hidden-gem system, recommendations, and parallel sessions, and a short checklist of the steps only Michael can do.

## Decisions settled in the grilling

| Area | Decision |
|---|---|
| Scope | Launch + hidden-gem system + recommendations + run-in-tabs + parallel sessions. Roadmap only: harness-tab extensions, base harness versions, crowdsourced compute, other harnesses. |
| Launch | Public web catalog + Linux desktop app. Windows/macOS labelled "coming later". No hosted sandbox. |
| Hidden gems | Two stages: existing statistics pass filters all projects; a new deep stage reads the code of top candidates. Lives in its own top-level package with a file contract. |
| Deep reading | Done by me in this build over a decent-sized capped set (target 120 projects, batches of 10) to populate picks with genuinely good projects. Verdict format is source-neutral so a paid model can be plugged in later. |
| Gem scoring | Backtest (did obscure projects it ranks highly later take off) plus ~30 labels from Michael. |
| Recommendations | Local only, rules only, no AI, nothing uploaded. Ask once, then on. Shown after sessions on the home view. |
| Shelves | Add "New this week" and "Best in each category" (measured, no AI). |
| Parallel sessions | One task across 2–4 saved configurations, side by side, user picks one. No auto-merge. |
| PR 41 | Rebuild run-in-tabs on main's styling; closing PR 41 goes on the end checklist. |
| Landing | One integration branch. Draft PR per milestone into it. Nothing merged to `main`, nothing deployed to production, without explicit OK. |
| Accounts | Built and tested with stand-in values; real GitHub OAuth app, Upstash store, Vercel keys and prod deploy are a checklist at the end. |
| Name | Build as DSH Forge; rename is an isolated last step once Michael supplies the name. |
| /kickoff | The skill cannot be invoked by me (user-only). I apply its existing-repo, additive-only steps by hand in M0. |

## Before I start (Michael, once)

```bash
sudo add-apt-repository -y ppa:apptainer/ppa && sudo apt update && sudo apt install -y apptainer
```
I then pull the pinned `node:22-bookworm` image per `docs/apptainer-sandbox.md` and record its digest.

## Milestones

Each milestone = small atomic commits (Conventional Commits, tests in the same commit, refactors separate from behaviour), `make check` green before every commit, then a real-app check in the browser, then a draft PR into the integration branch.

### M0. Baseline
- Commit the pending merge; create `feat/platform-v1` from it as the integration branch.
- Kickoff additive scaffold: `docs/PROBLEM.md`, `docs/decisions.md` (table above), `docs/PLAN.md`, `docs/architecture.svg` (Mermaid), `CLAUDE.md`, `.github/pull_request_template.md`, `.claude/settings.json`, and a `Makefile` `check` target that runs exactly what `.github/workflows/checks.yml` runs. Existing CI is not replaced.
- Test isolation: in `tests/helpers.py`, patch `shutil.which` to return `None` for `"dsh"`; add the import to `tests/test_sandbox.py`. Target: 285/285 locally.
- Catalog job fix: `dsh_forge/marketplace.py:123-126` accepts an empty description (normalisation at `:148` already handles it) + test. This one is also opened as its own small draft PR against `main`, because the daily job only recovers when it lands there (checklist item).

### M1. Hidden-gem system (`gems/`, separate package)
Contract: reads the published catalog/evidence files, writes `gem-picks.json` (versioned schema). The app only reads that file and falls back to today's v3 picks if it is absent.
- `gems/candidates.py`: take stage-1 scores from the existing discovery report (`dsh_forge/discovery.py` stays the stage-1 provider; no rewrite), select top candidates, drop forks-of-forks and archived repos.
- `gems/inspect.py`: automatic deep checks on a shallow clone at a pinned commit, read-only, never executed on the host: valid plugin manifest and entry point, original vs boilerplate code size, tests present, copy detection by file-hash overlap across candidates. Install and test runs happen only inside Apptainer.
- `gems/reviews/<owner>__<repo>@<sha>.json`: verdicts against a fixed rubric (what it really does, novelty, usefulness, works, one showcase line; 1–5 each; `source` field). `gems/review.py` defines the reviewer interface; this build's source is `claude-session`.
- Deep reading run: 120 candidates, batches of 10 via sub-agents on a smaller model, clones in the scratch folder, repository text treated as data never as instructions. I spot-check 1 in 5.
- `gems/rank.py`: combine stage-1 gap, automatic checks and verdicts into final picks with plain-language reasons.
- `gems/eval/`: `backtest.py` (star history from stargazer timestamps, within the existing GraphQL budget), `labels.json` (Michael's ~30 labels, collected by a tiny local labelling page), `python3 -m gems eval` prints precision@k against labels and backtest lift, appends to `gems/eval/history.jsonl`. Ranking changes must not lower the scoreboard; I iterate until gains flatten.
- Wire in: `catalog-research.yml` runs `python3 -m gems build` and publishes `gem-picks.json`; `catalog_store.discover()` and `api/catalog.mjs` read it; `gems/README.md` documents working on it alone.

### M2. Reliable open + run in tabs
- Fix the two defects in the branch: `reserveOpenWindow` (`web/launcher.js` ~2960) drops `noopener` and nulls `opener`; `openCell` returns false with no target; `refreshStatus` clears `artifactOpenCell` when the cell stops. Test with `window.open` returning null.
- Extract `loopbackUrl()` / `resolveCellUrl()` from `validatedCellOpenUrl` and reuse in `syncAssistantFrame`.
- Tab deck: `instanceTabs`, `addInstanceTab`, `activateInstanceTab`, `closeInstanceTab`, `syncInstanceFrames`, `pruneInstanceTabs`, persist id and title only. Panes stay mounted. Plain-browser fallback is a real link, no popup. Tests ported from commit `62e42cf`.

### M3. Interface cleanup and shelves
- Remove technical details from pages (commit hashes in the install dialog, `$DSH_HOME`/Apptainer wording, dead `copyRepositoryRef`), remove or explain greyed-out controls, fix the contradictory README line.
- `discovery.py` emits `queue["shelves"] = {best: {capability: [ids]}, new: [ids]}`; allow the key in `dsh_forge/feed.py:119`; resolve in `catalog_store.discover()` and `api/catalog.mjs` like packs; render two new shelves; "Hidden gems" shelf reads `gem-picks.json`.

### M4. Recommendations
- `dsh_forge/sessions.py`: streaming reader for `session.jsonl.zstd` (Python 3.14 stdlib → `zstd` binary → Node stream → "unavailable"), counts only.
- `SessionIndex` cache in `<state>/session-signals.json` keyed by path+size+mtime, 2-second budget, background thread, never at app start.
- `dsh_forge/recommendations.py`: signal rules onto the eight capabilities (reusing `discovery.capability_strengths`), per-session cap so one huge session counts once, 14-day half-life, top 3 unmet needs × 2 plugins, reviewed gems preferred, installed plugins excluded (`Launcher._discover_profiles`). Each item carries one sentence built from counts.
- `GET /api/v1/recommendations`, `POST .../consent`, CLI `recommend`; consent card and shelf on the home view and Discover. Opt-out deletes the cache.

### M5. Parallel sessions
- First, prove one real headless configuration run reaches a model inside the sandbox (headless cells default to no network). If it cannot, stop and report before building further.
- `dsh_forge/comparisons.py` (`ComparisonRegistry`, mirrors `ConfigurationRegistry`); `Launcher.run_comparison(ids, task)` over existing `run_configuration`; `Launcher.cell_result()` reads the cell's final answer with the M4 reader, falling back to `logs()`.
- Routes `POST/GET /api/v1/comparisons`, `.../choose`; CLI `compare run|show`; a compare tab in the M2 deck with one column per configuration and "Pick this one".
- Follow-on slice if `--resume` works headless: continue from an existing session.

### M6. Launch readiness
- `scripts/install.sh` (one command: checks Python, Apptainer, pulls and pins the image, creates a launcher entry) and a first-run setup check in the app with plain wording.
- Sign-in and likes exercised locally with stand-in keys; `docs/accounts.md` turned into the step-by-step checklist.
- README and landing copy updated; rename script prepared and dry-run only.

## Verification

- Every commit: `make check` (node tests, Python tests, compile check, catalog drift check).
- Every milestone: start the app with `python3 scripts/serve.py --sync-catalog`, drive it in a real browser with `agent-browser`, screenshot each changed screen and look at it, read the server log. With Apptainer installed: install and run one real plugin and one real fork, open them in tabs, run a 3-way comparison.
- Gem system: `python3 -m gems eval` scoreboard recorded per change; final picks list reviewed by eye.
- Major checkpoint before finishing: full pass through every screen as a new user on a clean state directory.
- Final report states plainly anything that failed or was not verified.

## Things I will stop and ask for

Anything costing money, creating accounts or keys, sudo, merging to `main`, production deploys, closing PR 41, posting anywhere, and force-pushes. Pushing the integration branch and opening draft PRs are covered by approving this plan.

## End-of-run checklist for Michael

1. Label ~30 gem picks (10 minutes, local page).
2. Merge the catalog-job fix PR into `main`.
3. Review and merge the integration branch.
4. Create the GitHub OAuth app and Upstash store, paste keys into Vercel, approve the production deploy.
5. Supply the new name and domain; approve the rename.
6. Close PR 41.

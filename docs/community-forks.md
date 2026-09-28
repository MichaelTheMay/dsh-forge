# Community forks

A fork of DeepSeek Harness replaces the whole Harness, so Forge installs it as
a separate local version instead of as a plugin. The flow is built so that the
code that runs is exactly the code you reviewed, and so that it only ever runs
inside the pinned Apptainer sandbox.

## What happens when you install a fork

1. **Review.** `POST /api/v1/forks/plan` resolves the commit Forge will fetch:
   the catalog's captured `head_sha` when it has one, otherwise the current head
   of the fork's default branch (resolved with `git ls-remote`). The dialog
   shows the full commit, the destination folder, and every step. Nothing is
   downloaded yet.
2. **Approve.** `POST /api/v1/forks/install` requires `acknowledge_risk: true`
   and the reviewed commit. If the fork moved in the meantime, the request is
   refused and you review the new commit.
3. **Fetch.** Forge runs Git with system and global configuration ignored,
   hooks pointed at `/dev/null`, an empty template directory, credential
   helpers and prompts disabled, submodules and LFS disabled, symlinks written
   as plain files, and only the HTTPS transport allowed. No GitHub token is
   sent. It fetches just the pinned commit (`--depth=1`) into a staging folder,
   verifies that `HEAD` equals the commit, checks the size limit (4 GiB,
   250,000 files), and only then moves it to
   `~/dsh-versions/forks/<owner>--<repo>@<commit12>`.
4. **Build.** Forge picks fixed commands from the lockfile, never from
   repository text: `corepack pnpm install --frozen-lockfile` then
   `corepack pnpm run build` (pnpm), the yarn equivalents, or `npm ci` then
   `npm run build`. Each step runs inside the pinned Apptainer image with the
   checkout as the only writable project mount, a disposable home that is
   deleted afterwards, no launcher secrets, and host networking so the package
   manager can download dependencies. Each step has a wall-time limit
   (`DSH_FORGE_FORK_BUILD_TIMEOUT`, default 3600 seconds). There is no host
   build fallback.
5. **Register.** Forge rescans and requires a launch-ready DeepSeek Harness
   CLI in the checkout. The tree is classified `community` only while its
   `origin` remote and `HEAD` still match the installation record; any change
   demotes it to `foreign`, which cannot run.

Progress, the current step, and the tail of the install log appear on the
fork's page while the sidecar is connected (`GET /api/v1/forks/<id>/logs`).

## Running a community fork

Installed forks appear under **Local** with a *Community fork* tag. Launch
always opens a confirmation, and the cell request carries
`acknowledge_risk: true`. Community cells:

- run only through the Apptainer cell runner (there is no other path);
- start with a fresh managed home; cloning is limited to that fork's own
  managed sessions, never your host DSH home;
- are never offered as a host for local profiles, plugin packages,
  configurations, or the Forge Assistant.

## Removing a fork

**Remove installed checkout** (or `POST /api/v1/forks/remove`) deletes only a
folder Forge created directly under `~/dsh-versions/forks`, and only when none
of that fork's sessions are running.

## Requirements and limits

- Linux with the pinned Apptainer image configured (see
  [Apptainer cell runner](apptainer-sandbox.md)). Use the full
  `docker://node:22-bookworm` image: it has Node 22 with `corepack` plus the
  Python, `make`, and `g++` needed to compile native modules such as
  `node-pty`, which has no linux-arm64 prebuild. The `-slim` image fails there.
- A Harness fork's `node_modules` and build output take several GB. Point
  `DSH_FORGE_VERSIONS_DIR` at project storage if your home quota is small.
- Building a large monorepo is CPU- and memory-intensive. On DeltaAI, start the
  sidecar inside a compute allocation rather than on a login node.
- Sandboxing reduces risk; it does not remove it. Apptainer shares the host
  kernel, and dependency installation and web cells use host networking.

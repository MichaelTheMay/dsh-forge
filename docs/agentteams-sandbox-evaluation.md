# AgentTeams disposable Apptainer evaluation

AgentTeams is the first candidate for a “Harness used to build the Harness
builder.” This is a separate runtime evaluation, not package-catalog
verification. Do not run the install on a login node or in an existing DSH
home.

## Pinned candidate and compatibility gap

- package: `@nanmicoder/dsh-agent-teams@0.1.16-rc.1`
- npm integrity:
  `sha512-gHrlUXuFnqz4wBw55v3ury/0PhNNCZ8/1eYycXUWGUgz97sxMzOMOLGGtpBijQ2/TzOqgRkv43+i/zKFU5GIZQ==`
- published release source commit:
  `eb09334f9a76dac890a25673449a6a51d5ceffcb`
- published prerelease tag: `v0.1.16-rc.1`
- publisher-reported package SHA-256:
  `624bece6eabcac162d0570d487b947b93f81785ed592464ce2601f5a371d1f26`
- recommended host: `@deepseek-ai/dsh@0.1.2-rc.1`
- host npm integrity:
  `sha512-RPq48TzxvwpdT9/7W1tbhZDBMmeK+bxDrX9cqQC27Wx/LqtgJF8PSa3b3xriU8oxtvhwYmk21w2cej3uMQrnVA==`
- runtime: Node `^22.19.0 || >=24`

The plugin declares support for DSH `0.1.2-rc.1`, `0.1.2-alpha.5`, and
`0.1.2-alpha.2`. The existing Delta `0.1.2-alpha.3` checkout is not in that
list. Build this evaluation around `0.1.2-rc.1`; do not mutate alpha.3.

npm did not expose a release `gitHead` for the original package query. The
publisher's [September 6 release record][agentteams-release] now identifies the
source commit and tag above and reports the package SHA-256. The npm SRI remains
the registry-byte identity used by this evaluation. The September 5 catalog
discovery snapshot remains an immutable record of the earlier observed commit;
it is not silently rewritten as later release provenance arrives.

[agentteams-release]: https://github.com/NanmiCoder/dsh-agent-teams/blob/main/docs/maintenance-2026-09-06/release/README.md

## Allocate Delta compute

From a Delta login node:

```bash
srun -A bfir-dtai-gh \
  --partition=ghx4-interactive \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=8 \
  --mem=16g \
  --gpus=1 \
  --time=01:00:00 \
  --pty bash
```

Activate the environment only to use its shell tools, then verify the existing
pinned SIF instead of replacing it:

```bash
conda activate dsh-forge
export DSH_FORGE_SANDBOX_IMAGE="$HOME/.local/share/dsh-forge/images/node-22-bookworm.sif"
export DSH_FORGE_SANDBOX_IMAGE_SHA256="7db5fca05b59b8e93646d8443ceccc998e6ec0b1747c4cc0faa95bc30852b4f2"
sha256sum "$DSH_FORGE_SANDBOX_IMAGE"
```

Stop unless the printed digest exactly matches the exported value.

## Install only inside a disposable home

Use a new evaluation directory. Nothing below mounts the host home into the
container, forwards launcher/model credentials, or writes to the alpha.3 tree.
Network access is enabled only for the npm installation phase.

```bash
export DSH_AGENTTEAMS_EVAL="$HOME/.local/state/dsh-forge/evaluations/agentteams-rc1"
mkdir -p \
  "$DSH_AGENTTEAMS_EVAL/home" \
  "$DSH_AGENTTEAMS_EVAL/workspace" \
  "$DSH_AGENTTEAMS_EVAL/workspace/npm-cache"
chmod 700 "$DSH_AGENTTEAMS_EVAL" "$DSH_AGENTTEAMS_EVAL/home" "$DSH_AGENTTEAMS_EVAL/workspace"

timeout 900 apptainer exec \
  --containall \
  --cleanenv \
  --no-eval \
  --no-privs \
  --no-mount cwd,hostfs,bind-paths \
  --home "$DSH_AGENTTEAMS_EVAL/home:/home/dsh" \
  --mount "type=bind,src=$DSH_AGENTTEAMS_EVAL/workspace,dst=/workspace" \
  --env DSH_HOME=/home/dsh/.dsh \
  --env npm_config_prefix=/home/dsh/.local \
  --env npm_config_cache=/workspace/npm-cache \
  --env COREPACK_HOME=/home/dsh/.cache/corepack \
  --env PATH=/home/dsh/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --pwd /workspace \
  "$DSH_FORGE_SANDBOX_IMAGE" \
  sh -eu -c '
    mkdir -p /home/dsh/.local/bin
    corepack enable --install-directory /home/dsh/.local/bin
    corepack install --global pnpm@11.7.0
    npm install --global @deepseek-ai/dsh@0.1.2-rc.1
    dsh plugin --profile web add --save-exact @nanmicoder/dsh-agent-teams@0.1.16-rc.1
    dsh --version
    dsh --profile web --dump-config > /workspace/composed-config.txt
  '
```

This deliberately executes community installation code, but only inside the
contained writable home/workspace and the surrounding Slurm allocation. It is
not equivalent to DSH Forge's signed acquisition path: transitive npm
dependencies are still registry-resolved and the package has not been admitted
by a Forge trust root.

Before launch, inspect the exact top-level selection without printing secrets:

```bash
rg -n "dsh-agent-teams|0.1.16-rc.1" \
  "$DSH_AGENTTEAMS_EVAL/home/.dsh/profiles/web" \
  "$DSH_AGENTTEAMS_EVAL/workspace/composed-config.txt"
```

## Open the DeepSeek Web browser

Keep the same compute allocation alive and run the Web profile in the
foreground. The host network is explicit because the browser needs a loopback
port; outbound filtering is not claimed.

```bash
timeout --foreground --signal=TERM --kill-after=5 14400 \
  apptainer exec \
  --containall \
  --cleanenv \
  --no-eval \
  --no-privs \
  --no-mount cwd,hostfs,bind-paths \
  --home "$DSH_AGENTTEAMS_EVAL/home:/home/dsh" \
  --mount "type=bind,src=$DSH_AGENTTEAMS_EVAL/workspace,dst=/workspace" \
  --env DSH_HOME=/home/dsh/.dsh \
  --env PATH=/home/dsh/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --pwd /workspace \
  "$DSH_FORGE_SANDBOX_IMAGE" \
  dsh web --host 127.0.0.1 --port 3181 --no-open \
  2>&1 | tee >(sed -u -E \
    's#([?&]token=)[^[:space:] )]+#\1[REDACTED]#g' \
    > "$DSH_AGENTTEAMS_EVAL/workspace/web.log")
```

From the Mac, create an SSH tunnel to the allocated compute hostname through
Delta's login host, then open `http://127.0.0.1:3181/`. Replace `COMPUTE_HOST`
with the current `ghNNN` hostname:

```bash
ssh -J "$USER"@dtai-login.delta.ncsa.illinois.edu \
  -L 3181:127.0.0.1:3181 \
  "$USER"@COMPUTE_HOST
```

Acceptance evidence is: exact DSH/plugin versions, one AgentTeams bundle in the
composed config, Web boot, visible AgentTeams UI, logs with no duplicate-loader
error, and a clean stop on Ctrl+C. Preserve the evaluation directory and log;
do not label the catalog package sandbox verified until this evidence is tied
to the SIF digest, DSH version, plugin SRI, and host/runtime versions.

No model credential is forwarded by these commands. Routing a Codex-backed
model through DSH requires a separately reviewed, explicit credential/provider
adapter; do not copy a host token into the test home merely to make the demo
run. Installation/UI testing and model-backed team execution are distinct
acceptance steps.

## Delta live result — 2026-09-06

The bounded installation/UI smoke test passed on an NCSA Delta compute
allocation. The result below is sanitized: it omits the user name, compute
hostname, private host paths, Web bearer token, full environment, and session
contents.

- Runtime: Linux ARM64, Node `22.19.0`, Apptainer `1.4.2-111.1`, with one
  allocated NVIDIA GH200 visible to the container.
- Sandbox image: immutable SIF SHA-256
  `7db5fca05b59b8e93646d8443ceccc998e6ec0b1747c4cc0faa95bc30852b4f2`.
- Containment probe: passed as a non-root process with the host home hidden,
  disposable `/home/dsh` and `/workspace`, no default network route in the
  networkless phase, and no forwarded GitHub, npm, OpenAI, or Anthropic token
  variables.
- Exact installation: `@deepseek-ai/dsh@0.1.2-rc.1` and
  `@nanmicoder/dsh-agent-teams@0.1.16-rc.1`; both npm integrity checks passed.
- Composition: one AgentTeams bundle appeared in the disposable Web profile
  and composed configuration.
- Web smoke test: DeepSeek Web booted on loopback, `/workspace` opened, and the
  `/agent-teams [--profile <name>] <goal>` command rendered in the UI.
- Shutdown/log review: the server stopped cleanly, and the saved redacted log
  contained no match for `duplicate`, `uncaught`, `fatal`, `exception`, or
  `error`.
- Deliberate boundary: no model credential was forwarded and no
  `.agent-teams` runtime state was created, so this result does **not** claim a
  model-backed team run, provider compatibility, or end-to-end task execution.

Verdict: the pinned candidate passed containment, exact installation,
composition, and Web command-registration checks in the disposable Delta
environment. This evidence does not admit the unsigned package to a Forge
trust root, authorize one-click installation, or change the package catalog's
`sandbox_verified` field. Those require signed acquisition, reproducible
archive inspection, and a separately scoped model-backed acceptance test.

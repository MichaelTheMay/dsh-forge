# Fleet sandbox preview

The preview pins two immutable official DeepSeek Harness releases:

| Version | Official tag | Commit |
| --- | --- | --- |
| `0.1.2-alpha.3` | `dsh-v0.1.2-alpha.3` | `dd6322d604e00eec1ba5e0c8541159906a21094a` |
| `0.1.2-alpha.2` | `dsh-v0.1.2-alpha.2` | `0a53fb55bea101816fa226bb964ae2bed71c343b` |

The rail does not download or execute a moving package. A Launch button becomes
available only when bounded discovery finds an exact built installation with the
canonical `deepseek-ai/deepseek-harness` Git remote.

## Build the two official installations

DeepSeek Harness is a developer preview. Read its safety notice and build these
only in an environment where running the official dependency installation and
build scripts is acceptable. On DeltaAI, do this in an appropriate compute
allocation, not on a login node.

```bash
mkdir -p ~/dsh-official
git clone --branch dsh-v0.1.2-alpha.3 --single-branch \
  https://github.com/deepseek-ai/deepseek-harness.git ~/dsh-official/alpha-3
git clone --branch dsh-v0.1.2-alpha.2 --single-branch \
  https://github.com/deepseek-ai/deepseek-harness.git ~/dsh-official/alpha-2

test "$(git -C ~/dsh-official/alpha-3 rev-parse HEAD)" = dd6322d604e00eec1ba5e0c8541159906a21094a
test "$(git -C ~/dsh-official/alpha-2 rev-parse HEAD)" = 0a53fb55bea101816fa226bb964ae2bed71c343b

for version in alpha-3 alpha-2; do
  (cd ~/dsh-official/$version && corepack pnpm install --frozen-lockfile && corepack pnpm run build)
done
```

Start Forge with both exact roots:

```bash
cd ~/dsh-forge
python3 scripts/serve.py \
  --scan-root ~/dsh-official/alpha-3 \
  --scan-root ~/dsh-official/alpha-2
```

## What is isolated now

Every one-click Web cell gets a unique available loopback port, a new process
group, a separate writable `DSH_HOME`, and a separate managed workspace. Forge
records PID plus operating-system process-start identity and will not signal a
process whose identity no longer matches. Clone Session creates another port,
home, and workspace from a sanitized snapshot; the source cell keeps running.
That v1 snapshot is best-effort rather than filesystem-atomic, so do not clone a
cell while it is writing irreplaceable state.

CPU, GPU, RAM, PID, and wall-time values come from the required Apptainer
configuration. The runner records the accepted controls and never falls back to
a direct Harness host process. Web cells use the host network for their
loopback port; headless cells default to networkless operation. Apptainer shares
the host kernel, and the surrounding Slurm allocation remains authoritative.

Community checkouts use a separate path: Forge can run a bounded, networkless
CLI probe inside a pinned Apptainer SIF, but cannot start them as fleet cells or
promote them. See [Apptainer community-code test sandbox](apptainer-sandbox.md).

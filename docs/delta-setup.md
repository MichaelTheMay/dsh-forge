# Open DSH Forge from DeltaAI

This starts the loopback launcher sidecar and UI. Do not launch DSH workloads,
build foreign forks, or run model jobs on a login node. Use the login node only
to inspect the UI and discover trees; follow NCSA policy and start the launcher
inside an appropriate interactive compute allocation before launching a cell.

## Clone on Delta

From the existing Delta prompt after cloning the repository:

```bash
cd ~/dsh-forge
```

Once the launcher PR is merged, update and start the UI:

```bash
git switch main
git pull --ff-only origin main
python3 scripts/serve.py
```

If `command -v dsh` prints nothing, restart with
`--scan-root /path/to/deepseek-harness`. The scanner reads only bounded evidence
under that root and never executes candidate code.

Leave that terminal open. The server uses `127.0.0.1:3090`, not a public bind
address. If the PR has not merged, the new files are available only on its
feature branch.

## Create a compatible runtime environment

Serving and browsing DSH Forge needs only Python. Running the JavaScript checks
or launching the current upstream DeepSeek Harness also needs Node. Keep that
runtime out of the base environment:

```bash
conda create -n dsh-forge -c conda-forge python=3.11 nodejs=22.19.0 -y
conda activate dsh-forge
python3 --version
node --version
```

The Node version should print `v22.19.0`. Current upstream Harness declares
`^22.19.0 || >=24.0.0`; an older Node release may pass DSH Forge's frontend
tests but is not a supported Harness runtime.

Run both local suites from the repository root:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/catalog.test.cjs
```

## Open an SSH tunnel from the Mac

In a **new terminal on the Mac**, not inside the Delta shell:

```bash
ssh -N -L 127.0.0.1:3090:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

Complete NCSA authentication, leave the tunnel open, and visit
<http://127.0.0.1:3090/#launch> in the Mac browser. `-N` does not open a
remote shell, so a connected tunnel can appear idle.

Use the **same login node that hosts the server**. The public
`dtai-login.delta.ncsa.illinois.edu` address can select another node. If the
session is no longer on `gh-login03`, run `hostname -f` on Delta and substitute
that exact hostname in the SSH command.

If your access requires the public login gateway, use it as a jump host while
keeping the selected login node as the final destination:

```bash
ssh -N -J ssourav@dtai-login.delta.ncsa.illinois.edu -L 127.0.0.1:3090:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

If local port 3090 is occupied on the Mac, use local port 3091 while leaving the
remote port at 3090, then browse `http://127.0.0.1:3091/#launch`:

```bash
ssh -N -L 127.0.0.1:3091:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

Stop the server and tunnel with Ctrl+C in their respective terminals. No GPU
or extra Conda environment is needed to serve and inspect the launcher; a cell
may have its own runtime requirements.

## Enable the community-code test sandbox

DeltaAI supplies Apptainer. The optional sandbox uses a pinned, read-only SIF,
no network, no inherited launcher secrets, a read-only source mount, disposable
writable state, and runtime-accepted CPU/RAM/PID limits. It never turns a
community checkout into a host process. Follow the complete setup and threat
boundary in [Apptainer community-code test sandbox](apptainer-sandbox.md).

## Download instead of running a server

On Delta, produce a standalone file:

```bash
python3 scripts/package_preview.py dist/DSH_Forge_Fleet_Sandbox_Preview.html
```

Then on the Mac:

```bash
scp ssourav@gh-login03.delta.ncsa.illinois.edu:~/dsh-forge/dist/DSH_Forge_Fleet_Sandbox_Preview.html ~/Downloads/
open ~/Downloads/DSH_Forge_Fleet_Sandbox_Preview.html
```

All JavaScript and catalog data are embedded. Optional web fonts may fall back
to system fonts without internet access. The portable file is explicitly
disconnected; opening it does not launch or install DSH.

NCSA documents [DeltaAI login methods](https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/login.html)
and [access to browser-based tools](https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/vscode/code-server.html).

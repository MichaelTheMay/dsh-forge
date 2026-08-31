# Open DSH Forge from DeltaAI

This serves the static UI prototype only. Do not run DSH workloads, builds of
foreign forks, or model jobs on a login node. Follow NCSA policy for long-lived
services and use a compute allocation when needed.

## Clone on Delta

From the existing `(base) ssourav@gh-login03:~>` prompt:

```bash
cd ~
git clone https://github.com/MichaelTheMay/dsh-forge.git
cd dsh-forge
```

Once the Public Repos PR is merged, update and start the static UI:

```bash
git switch main
git pull --ff-only origin main
python3 scripts/serve.py
```

Leave that terminal open. The server uses `127.0.0.1:3090`, not a public bind
address. If the PR has not merged, the new files are available only on its
feature branch.

## Open an SSH tunnel from the Mac

In a **new terminal on the Mac**, not inside the Delta shell:

```bash
ssh -N -L 127.0.0.1:3090:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

Complete NCSA authentication, leave the tunnel open, and visit
<http://127.0.0.1:3090/#public-repos> in the Mac browser. `-N` does not open a
remote shell, so a connected tunnel can appear idle.

Use the **same login node that hosts the server**. The public
`dtai-login.delta.ncsa.illinois.edu` address can select another node. If the
session is no longer on `gh-login03`, run `hostname -f` on Delta and substitute
that exact hostname in the SSH command.

If your access requires the public login gateway, use it as a jump host while
keeping `gh-login03` as the final destination:

```bash
ssh -N -J ssourav@dtai-login.delta.ncsa.illinois.edu -L 127.0.0.1:3090:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

If local port 3090 is occupied on the Mac, use local port 3091 while leaving the
remote port at 3090, then browse `http://127.0.0.1:3091/#public-repos`:

```bash
ssh -N -L 127.0.0.1:3091:127.0.0.1:3090 ssourav@gh-login03.delta.ncsa.illinois.edu
```

Stop the server and tunnel with Ctrl+C in their respective terminals. No GPU
or extra Conda environment is needed for this static preview.

## Download instead of running a server

On Delta, produce a standalone file:

```bash
python3 scripts/package_preview.py dist/DSH_Forge_Public_Repos.html
```

Then on the Mac:

```bash
scp ssourav@gh-login03.delta.ncsa.illinois.edu:~/dsh-forge/dist/DSH_Forge_Public_Repos.html ~/Downloads/
open ~/Downloads/DSH_Forge_Public_Repos.html
```

All JavaScript and catalog data are embedded. Optional web fonts may fall back
to system fonts without internet access. The UI remains a prototype; opening
it does not launch or install DSH.

NCSA documents [DeltaAI login methods](https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/login.html)
and [access to browser-based tools](https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/vscode/code-server.html).

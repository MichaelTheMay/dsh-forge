# Apptainer community-code test sandbox

DSH Forge can run one bounded capability probe for a detected community
checkout inside a pinned Apptainer SIF. This is the first execution boundary
for foreign code. It does **not** install, merge, promote, or start a community
fork as a fleet cell.

## Boundary

The sidecar fails closed unless the runtime accepts all required controls:

- a locally captured SIF whose SHA-256 matches the configured pin and whose
  filesystem mode is read-only;
- `--containall`, `--cleanenv`, `--no-eval`, and `--no-privs`;
- no host home, current-working-directory, host-filesystem, or administrator
  bind paths;
- a new network namespace using the `none` network (loopback only);
- separate temporary writable home and workspace mounts;
- the detected source checkout mounted read-only, with nested bind propagation
  disabled;
- CPU, memory, PID, and wall-time limits; and
- an explicit environment allowlist that does not include launcher credentials,
  API keys, proxy variables, or inherited `APPTAINER_*` bind settings.

Only a Git revision without tracked changes can be tested. The current action runs the scanner's
captured CLI with `--help`, caps returned output at 64 KiB, and stores the result
against the observed Git revision, executable digest, and image digest. A pass is capability
evidence—not proof of safety, correctness, or Harness compatibility. Direct
host launch remains blocked after a pass.

## Prepare a pinned Node image on DeltaAI

DeltaAI provides Apptainer. Create the image in accordance with NCSA policy and,
when required, inside a compute allocation rather than on a login node:

```bash
mkdir -p ~/.local/share/dsh-forge/images
apptainer pull ~/.local/share/dsh-forge/images/node-22-bookworm.sif \
  docker://node:22-bookworm-slim
chmod 400 ~/.local/share/dsh-forge/images/node-22-bookworm.sif
sha256sum ~/.local/share/dsh-forge/images/node-22-bookworm.sif
```

`docker://node:22-bookworm-slim` is an acquisition reference, not the launch
pin. DSH Forge pins the bytes of the resulting local SIF. Record the printed
digest in a trusted release/configuration record and do not replace that file
under the same name.

## Start Forge

Pass both the community checkout and the exact image digest:

```bash
cd ~/dsh-forge
python3 scripts/serve.py \
  --scan-root ~/src/community-deepseek-harness \
  --sandbox-image ~/.local/share/dsh-forge/images/node-22-bookworm.sif \
  --sandbox-image-sha256 REPLACE_WITH_64_HEX_DIGEST \
  --sandbox-cpus 4 \
  --sandbox-memory 8G \
  --sandbox-pids-limit 256 \
  --sandbox-timeout 30
```

The sidecar prints either `Sandbox: apptainer-networkless-test · ready` or the
specific reason it stayed unavailable. In the Versions rail, each detected
community tree then has a single **Test** action. If no community tree appears,
confirm that the checkout has no tracked changes and contains a recognized,
built DSH CLI artifact.

The same values may be configured with `DSH_FORGE_SANDBOX_IMAGE`,
`DSH_FORGE_SANDBOX_IMAGE_SHA256`, `DSH_FORGE_SANDBOX_BINARY`,
`DSH_FORGE_SANDBOX_CPUS`, `DSH_FORGE_SANDBOX_MEMORY`,
`DSH_FORGE_SANDBOX_PIDS_LIMIT`, and `DSH_FORGE_SANDBOX_TIMEOUT`.

## Deliberate limitations

- The test has no network, GPU, model, API, or web-port access.
- The container shares the host kernel; this is not a virtual machine and is
  not claimed to be immune to kernel/runtime vulnerabilities.
- This alpha does not acquire catalog repositories. A checkout must already be
  present in an explicit scan root.
- Passing the probe does not enable **Launch cell**. Promotion needs the later
  ingester, compatibility policy, stronger test suite, and explicit approval.
- Official/personal fleet cells still use the existing trusted-host path. Their
  displayed CPU/GPU/RAM values are not host-enforced quotas.

Production promotion should additionally pin the acquisition source by digest,
verify a signed image attestation, use an administrator-reviewed seccomp policy,
freeze source bytes by content digest, and run adversarial escape tests on the
exact DeltaAI runtime configuration.

# Sandbox package installation

DSH Forge exposes one end-to-end install transaction only for a locally trusted,
signed recipe and a saved Harness version. Catalog metadata alone never enables
the button.

## Configure a certified recipe

Create and protect your own Ed25519 release key. Build a proposal from the
current hidden-gem queue, review its exact source, requested permissions,
license, and compatibility, then let the research command atomically place the
signed recipe in the launcher's fixed recipe directory:

```bash
python3 -m dsh_forge research certify \
  --proposal /tmp/agent-teams.proposal.json \
  --private-key /secure/path/release-key.pem \
  --public-key /secure/path/release-key.pub.pem \
  --root-id local.agent-teams \
  --expires-at 2027-09-01T00:00:00Z \
  --reviewer "Release curator" \
  --review-source --review-permissions --review-license --review-compatibility \
  --publish-root ~/.local/state/dsh-forge/trusted-package-recipes
```

The slot contains the signed envelope, trust root, original proposal, and
certification receipt. The signed manifest binds the reviewer and completed
checklist; the signature is rechecked when installation starts. See
[Hidden-gem research and publication](hidden-gem-pipeline.md) for proposal
creation and the full trust boundary.

Restart the loopback launcher, open `#packages/agent-teams-builder`, choose a
saved Harness version, and select **Verify, test & install**. The browser sends
only the stable package slug and saved-version ID; it cannot choose filesystem
paths, keys, URLs, commands, or sandbox flags.

The equivalent CLI transaction is:

```bash
python3 -m dsh_forge packages install \
  --bundle ~/.local/state/dsh-forge/trusted-package-recipes/agent-teams-builder/envelope.json \
  --trust-root ~/.local/state/dsh-forge/trusted-package-recipes/agent-teams-builder/trust-root.json \
  --version version_REPLACE_WITH_SAVED_ID \
  --profile web
```

## Enforced transaction

1. Re-verify the DSSE envelope, threshold, expiry, package identity, and trust
   root before acquisition.
2. Acquire exact HTTPS artifacts into the existing read-only SHA-256-addressed
   quarantine.
3. Stream-inspect npm archives without host extraction. Reject traversal,
   duplicate/case-colliding paths, links, devices, excessive files or expansion,
   unexpected native/binary formats, lifecycle hooks, and runtime dependencies.
4. Create a fresh disposable profile, or sanitize-copy the previously promoted
   version. The user's host DSH home is never mounted.
5. Add every signed top-level artifact with `--offline --ignore-scripts` in a
   networkless Apptainer cell. Runtime dependency resolution is forbidden; peer
   dependencies must already exist in the selected Harness profile.
6. Run a networkless composition probe and bounded DeepSeek Web startup probe.
7. Move the tested home into an immutable versioned release directory, then
   atomically replace `current.json`. Previous releases remain rollback targets.

Package-install transactions survive launcher restarts in
`~/.local/state/dsh-forge/package-installations.json`. Failures include a stable
error code and retain bounded logs under `package-profiles/failed/`; the current
profile pointer is not changed.

This boundary still does not claim kernel exploit immunity, a per-profile disk
quota, or safe execution of arbitrary native code. Host fallback is absent.

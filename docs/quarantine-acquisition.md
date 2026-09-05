# Authenticated content-addressed quarantine

`packages acquire` is the only networked package command. It converts a trusted,
signed metadata decision into immutable local bytes without crossing the
installation or execution boundary.

## Order of operations

1. Read the bounded DSSE envelope and explicitly configured trust root.
2. Verify signature threshold, signer identity, trust-root expiry, canonical
   payload bytes, schema, exact versions, repository commits, relations,
   conflicts, and composition digest.
3. Validate each signed URL against its source-kind host policy. Reject URL
   credentials, query strings, fragments, non-HTTPS schemes, and non-443 ports.
4. Fetch directly over certificate-validated HTTPS without ambient proxies,
   cookies, authorization headers, npm tokens, or GitHub tokens.
5. Follow at most three HTTPS redirects, each restricted to the source-kind host
   set. Query strings required by a release CDN are used for that request but
   removed from the receipt.
6. Stream into a mode-0600 temporary file under a per-artifact byte limit and
   wall-clock limit. Reject transfer content encoding and inconsistent length.
7. Recompute the signed npm SHA-512 SRI or SHA-256 pin and a local SHA-256 content
   address before finalization.
8. Create the read-only object without replacing an existing path. Reuse an
   existing object only after checking its type, size, and full digest.
9. Write a read-only receipt keyed by the signed payload digest.

Signature verification occurs before quarantine directories are created or a
downloader can run. A failed download leaves no package receipt. Successfully
verified objects from earlier members may remain in the content-addressed store;
they are inert and reusable, but do not represent a completed package.

## Filesystem layout

```text
quarantine/
  .acquire.lock
  .incoming/
  objects/sha256/ab/<64-hex-digest>/artifact
  receipts/sha256/<signed-payload-sha256>.json
```

Directories are restricted to the current OS user. Objects and receipts are
mode 0400 after finalization. The filename `artifact` deliberately carries no
extension and Forge performs no MIME dispatch, extraction, import, or execution.

The receipt schema is `dsh-forge.quarantine-receipt/v1`. Its two authorization
flags are fixed false:

```json
{
  "installation_authorized": false,
  "execution_authorized": false
}
```

## Enforced limits and host policy

- default maximum: 256 MiB per artifact;
- hard maximum accepted by the CLI boundary: 1 GiB per artifact;
- default package maximum: 1 GiB; hard maximum: 8 GiB;
- default timeout: 60 seconds per artifact and 300 seconds for the package;
- accepted timeout ranges: 1–300 seconds per artifact and 1–3,600 seconds total;
- maximum redirects: three;
- npm: `registry.npmjs.org` only;
- GitHub archives: `github.com` and `codeload.github.com`;
- MCPB releases: `github.com`, `release-assets.githubusercontent.com`, and
  `objects.githubusercontent.com`.

An npm URL must encode the exact signed version in its tarball filename. A
GitHub archive URL must contain the full signed commit. The fixed host list is
not configurable in v1. Adding private registries or arbitrary origins requires
a separate policy and credential-isolation review.

## Explicit non-goals

Acquisition does not establish that a plugin is safe, compatible, useful, or
licensed for redistribution. It does not inspect archive members, resolve
dependencies, run lifecycle scripts, write a package manager cache, create a
Harness profile, or communicate with the launcher. Passing bytes to Apptainer,
static archive inspection, sandbox testing, promotion, and installation are
later boundaries.

The process shares the host kernel and user account. Mode bits and an advisory
lock protect against accidents and cooperating Forge processes, not a malicious
process already running as the same OS user. Production multi-user storage needs
service-level identity and stronger filesystem isolation.

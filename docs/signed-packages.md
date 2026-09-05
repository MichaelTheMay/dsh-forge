# Signed package schema and offline composer

DSH Forge packages describe an ordered set of immutable plugin artifacts. This
release defines the public metadata contract and a local composer; it does not
publish, download, install, or execute any artifact.

## Files and versions

- `dsh-forge.package-spec/v1` is the human-authored composition input.
- `dsh-forge.package/v1` is the normalized manifest produced by Forge.
- `application/vnd.dsh-forge.package.v1+json` is the DSSE payload type.
- `dsh-forge.trust-root/v1` is an explicitly configured local trust anchor.

The machine-readable contracts live in `schemas/`. Unknown fields are rejected.
Every selected plugin requires one exact package version, an HTTPS artifact URL,
an artifact integrity value, an HTTPS repository URL, and a full repository
commit. npm artifacts require SHA-512 SRI; MCPB and GitHub archives require
SHA-256. Tags, ranges, `latest`, floating branches, redirects discovered at
runtime, and local paths are not accepted as pins.

Plugin IDs, permissions, dependencies, conflicts, compatibility declarations,
platforms, and load order are part of the signed payload. Permissions are
publisher declarations, not observations by Forge. The composer fails on:

- duplicate plugin IDs or duplicate load-order entries;
- a missing required plugin or a selected conflict;
- two versions or digests for the same source identity;
- unknown permission names;
- incomplete load order;
- unpinned versions, malformed integrity, mutable Git references, or non-HTTPS
  source locations.

## Canonical bytes and signatures

The composer normalizes sets, sorts plugin records by stable ID, and calculates
a SHA-256 digest over the compatibility, plugin, and load-order selection. The
manifest uses the number-free, ASCII-object-key profile declared as
`RFC8785-JCS-ascii-key-no-number-profile/v1`. This constrained profile produces
the same bytes as the relevant portion of the
[JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) while
rejecting numeric and non-ASCII-key ambiguity.

Signing wraps those exact UTF-8 bytes in a
[DSSE](https://github.com/secure-systems-lab/dsse/blob/master/envelope.md)
pre-authentication encoding and uses Ed25519. A key ID is the SHA-256 digest of
the DER SubjectPublicKeyInfo public key. Verification checks the DSSE signature,
distinct trusted signer threshold, key status and identity, trust-root expiry,
canonical payload bytes, schema normalization, pins, relations, and composition
digest. It returns `execution_authorized: false`: a valid signature authenticates
metadata; it does not establish compatibility, safety, or permission to run.

The local trust root follows the same high-level separation used by
[The Update Framework](https://theupdateframework.github.io/specification/latest/):
trusted keys, threshold, and expiry are configured separately from signed target
metadata. This v1 does not fetch or rotate trust roots. Administrators must
distribute them through an authenticated channel.

## Offline workflow

Start with the documented, explicitly unsigned example:

```bash
python3 -m dsh_forge packages compose \
  --spec examples/package-spec.v1.json \
  --output /tmp/review-stack.manifest.json
```

Generate a development Ed25519 key locally. Never commit the private key:

```bash
openssl genpkey -algorithm Ed25519 -out /tmp/dsh-forge-dev-private.pem
chmod 600 /tmp/dsh-forge-dev-private.pem
openssl pkey -in /tmp/dsh-forge-dev-private.pem -pubout \
  -out /tmp/dsh-forge-dev-public.pem
```

Create a signed DSSE envelope and a local trust root:

```bash
python3 -m dsh_forge packages sign \
  --manifest /tmp/review-stack.manifest.json \
  --private-key /tmp/dsh-forge-dev-private.pem \
  --output /tmp/review-stack.dsse.json

python3 -m dsh_forge packages trust-root \
  --public-key /tmp/dsh-forge-dev-public.pem \
  --root-id local.development \
  --expires-at 2027-01-01T00:00:00Z \
  --output /tmp/dsh-forge-dev-root.json

python3 -m dsh_forge packages verify \
  --bundle /tmp/review-stack.dsse.json \
  --trust-root /tmp/dsh-forge-dev-root.json
```

All four commands are local and bounded. They do not construct the launcher,
read Harness homes, call GitHub or npm, resolve dependencies, or process artifact
bytes. Output files are created atomically and existing paths are not overwritten
unless `--force` is explicit.

Composition itself needs only Python 3.9+. Signing, trust-root creation, and
verification require an OpenSSL build with Ed25519 `pkey`/`pkeyutl` support; CI
runs a real sign-and-tamper test rather than mocking that boundary.

## Deliberately deferred

The package catalog remains empty. This release does not provide publisher
accounts, upload authorization, moderation, registry storage, trusted-root
distribution, artifact acquisition, dependency installation, configuration
merging, or sandbox execution. Those require separate reviewable boundaries.

The next execution-oriented change must verify a signed envelope first, acquire
each artifact by the exact signed URL into a content-addressed quarantine,
recompute every integrity value, reject redirects outside an allowlist, and only
then pass immutable bytes to a disposable networkless Apptainer test cell. It
must never install into a user's existing Harness tree directly.

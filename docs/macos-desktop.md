# macOS desktop application

The release workflow builds `DSH Forge.app` for both Apple silicon and Intel
Macs, then places each application in a platform-specific `.dmg`. Users open
the disk image and drag DSH Forge into Applications. Application state is kept
in `~/Library/Application Support/DSH Forge` so upgrades do not remove saved
paths, preferences, or the last verified catalog snapshot.

The application bundles the Python sidecar and static interface. It opens a
focused Edge, Chrome, or Chromium app window when one is installed, then uses
the default browser as a fallback. This keeps the package small and avoids
shipping a second browser engine. Startup discovers local DSH installations
without executing candidate code and refreshes the public catalog in the
background.

## macOS isolation boundary

Catalog browsing, DSH discovery, and local metadata inspection work natively
on macOS. The current hostile-code sandbox is a pinned Apptainer cell on Linux.
Plugin, fork, and isolated Harness execution therefore remains disabled in the
macOS process. Forge reports this restriction in the desktop UI and does not
fall back to direct community-code execution.

## Public release requirements

The release job uses the native arm64 `macos-15` runner and the x86-64
`macos-15-intel` runner. Each app receives the same stable bundle identifier,
`app.dshforge.launcher`, and a generated DSH Forge application icon. The job
then applies the hardened runtime, signs the app and disk image with a
Developer ID Application certificate, submits the disk image to Apple, staples
the accepted notarization ticket, and runs the packaged loopback API smoke
test.

Configure these encrypted GitHub Actions secrets before creating a release
tag:

- `MACOS_SIGNING_CERTIFICATE_BASE64`: base64-encoded Developer ID Application
  certificate and private key in PKCS#12 format
- `MACOS_SIGNING_CERTIFICATE_PASSWORD`: password for that PKCS#12 file
- `MACOS_NOTARY_APPLE_ID`: Apple ID used for notarization
- `MACOS_NOTARY_PASSWORD`: app-specific password for the Apple ID
- `MACOS_NOTARY_TEAM_ID`: Apple Developer Team ID

The job fails if any credential is missing, the signing identity is not a
Developer ID Application identity, notarization is rejected, or the signed app
cannot start its loopback API. The empty entitlements file deliberately avoids
debugging and unsigned-executable-memory exceptions.

## Build locally

Install the pinned Python build dependency on the matching Mac architecture.
The production build command also requires the three notarization environment
variables listed above:

```bash
python3 -m venv .venv-build
source .venv-build/bin/activate
python3 -m pip install -r packaging/macos/requirements-build.txt
packaging/macos/build.sh 0.1.0 arm64 "Developer ID Application: Example (TEAMID)"
```

Artifacts and SHA-256 checksums are written to `dist/macos`. A public build is
never emitted as an unsigned or unnotarized disk image.

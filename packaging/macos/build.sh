#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: build.sh VERSION ARCH DEVELOPER_IDENTITY" >&2
  exit 2
fi

version="$1"
arch="$2"
identity="$3"
if [[ ! "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$ ]]; then
  echo "VERSION must use semantic versioning" >&2
  exit 2
fi
if [[ "$arch" != "arm64" && "$arch" != "x86_64" ]]; then
  echo "ARCH must be arm64 or x86_64" >&2
  exit 2
fi
if [[ "$identity" != Developer\ ID\ Application:* ]]; then
  echo "A Developer ID Application identity is required" >&2
  exit 2
fi
for name in MACOS_NOTARY_APPLE_ID MACOS_NOTARY_PASSWORD MACOS_NOTARY_TEAM_ID; do
  if [[ -z "${!name:-}" ]]; then
    echo "$name is required for a public macOS build" >&2
    exit 2
  fi
done

repo_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
build_root="$repo_root/build/macos-$arch"
output_root="$repo_root/dist/macos"
entitlements="$repo_root/packaging/macos/entitlements.plist"

reset_repo_directory() {
  local target
  target="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
  case "$target" in
    "$repo_root"/*) ;;
    *) echo "Refusing to replace a directory outside the repository: $target" >&2; exit 1 ;;
  esac
  rm -rf -- "$target"
  mkdir -p -- "$target"
}

reset_repo_directory "$build_root"
mkdir -p -- "$output_root"

metadata="$build_root/build-version.json"
printf '{"version":"%s","repository":"MichaelTheMay/dsh-forge"}\n' "$version" > "$metadata"

icon_png="$build_root/DSH-Forge-1024.png"
iconset="$build_root/DSHForge.iconset"
swift "$repo_root/packaging/macos/generate_icon.swift" "$icon_png"
mkdir -p -- "$iconset"
for item in "16:icon_16x16.png" "32:icon_16x16@2x.png" "32:icon_32x32.png" "64:icon_32x32@2x.png" "128:icon_128x128.png" "256:icon_128x128@2x.png" "256:icon_256x256.png" "512:icon_256x256@2x.png" "512:icon_512x512.png" "1024:icon_512x512@2x.png"; do
  pixels="${item%%:*}"
  filename="${item#*:}"
  sips -z "$pixels" "$pixels" "$icon_png" --out "$iconset/$filename" >/dev/null
done
icon="$build_root/DSHForge.icns"
iconutil -c icns "$iconset" -o "$icon"

python3 -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name "DSH Forge" \
  --osx-bundle-identifier "app.dshforge.launcher" \
  --target-architecture "$arch" \
  --codesign-identity "$identity" \
  --osx-entitlements-file "$entitlements" \
  --icon "$icon" \
  --distpath "$build_root/bundle" \
  --workpath "$build_root/work" \
  --specpath "$build_root/spec" \
  --hidden-import tkinter \
  --hidden-import tkinter.filedialog \
  --add-data "$repo_root/web/index.html:web" \
  --add-data "$repo_root/web/launcher.js:web" \
  --add-data "$repo_root/web/support.js:web" \
  --add-data "$repo_root/web/vendor:web/vendor" \
  --add-data "$repo_root/data:data" \
  --add-data "$repo_root/dsh_forge/assistant_server.mjs:dsh_forge" \
  --add-data "$metadata:." \
  "$repo_root/scripts/serve.py"

app="$build_root/bundle/DSH Forge.app"
if [[ ! -d "$app" ]]; then
  echo "PyInstaller did not produce DSH Forge.app" >&2
  exit 1
fi
plist="$app/Contents/Info.plist"
release_version="${version%%-*}"
plutil -replace CFBundleDisplayName -string "DSH Forge" "$plist"
plutil -replace CFBundleShortVersionString -string "$release_version" "$plist"
plutil -replace CFBundleVersion -string "$release_version" "$plist"
lipo -archs "$app/Contents/MacOS/DSH Forge" | tr ' ' '\n' | grep -Fx "$arch" >/dev/null
codesign --force --options runtime --timestamp --entitlements "$entitlements" --sign "$identity" "$app"
codesign --verify --deep --strict --verbose=2 "$app"

case "$arch" in
  arm64) label="AppleSilicon" ;;
  x86_64) label="Intel" ;;
esac
dmg="$output_root/DSH-Forge-$version-macOS-$label.dmg"
rm -f -- "$dmg"
hdiutil create -volname "DSH Forge" -srcfolder "$app" -ov -format UDZO "$dmg"
codesign --force --timestamp --sign "$identity" "$dmg"
xcrun notarytool submit "$dmg" \
  --apple-id "$MACOS_NOTARY_APPLE_ID" \
  --team-id "$MACOS_NOTARY_TEAM_ID" \
  --password "$MACOS_NOTARY_PASSWORD" \
  --wait
xcrun stapler staple "$dmg"
xcrun stapler validate "$dmg"
codesign --verify --verbose=2 "$dmg"

checksum="$output_root/SHA256SUMS-macOS-$label.txt"
shasum -a 256 "$dmg" | sed "s#  .*/#  #" > "$checksum"
printf 'macOS artifact:\n  %s\n  %s\n' "$dmg" "$checksum"

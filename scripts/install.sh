#!/bin/sh
# Set up DSH Forge on Linux from a checkout of this repository.
#
#   ./scripts/install.sh              set everything up
#   ./scripts/install.sh --dry-run    show what would happen, change nothing
#   ./scripts/install.sh --browse-only   skip the isolated container (browse, no running)
#
# It checks what is needed, prepares the isolated container that plugins and forks
# run in, and creates a `dsh-forge` command and a desktop menu entry. Nothing is
# installed system-wide and nothing needs administrator rights. If Apptainer is
# missing, it says how to install it and sets up browsing only.
set -eu

DRY_RUN=0
BROWSE_ONLY=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --browse-only) BROWSE_ONLY=1 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $argument (try --help)" >&2; exit 2 ;;
  esac
done

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
BIN_DIR=${DSH_FORGE_BIN_DIR:-"$HOME/.local/bin"}
IMAGE_DIR="$DATA_HOME/dsh-forge/images"
IMAGE="$IMAGE_DIR/node-22-bookworm.sif"
IMAGE_SOURCE="docker://node:22-bookworm"
LAUNCHER="$BIN_DIR/dsh-forge"
DESKTOP_ENTRY="$DATA_HOME/applications/dsh-forge.desktop"

say() { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then say "  would run: $*"; else "$@"; fi
}

step "Checking what DSH Forge needs"
if ! command -v python3 >/dev/null 2>&1; then
  say "Python 3 is required and was not found. Install it, then run this again." >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  say "Python 3.9 or newer is required. Found: $(python3 --version 2>&1)" >&2
  exit 1
fi
say "  Python: $(python3 --version 2>&1)"
if [ ! -f "$REPO/scripts/serve.py" ]; then
  say "This script must be run from a DSH Forge checkout." >&2
  exit 1
fi

CONTAINER=0
if [ "$BROWSE_ONLY" -eq 1 ]; then
  say "  Isolated container: skipped (--browse-only)"
elif command -v apptainer >/dev/null 2>&1; then
  CONTAINER=1
  say "  Apptainer: $(apptainer --version 2>&1)"
else
  say "  Apptainer: not installed."
  say ""
  say "  Plugins and forks only run inside an isolated container, which needs Apptainer."
  say "  You can browse without it. To be able to run things, install it and run this"
  say "  script again:"
  if command -v apt-get >/dev/null 2>&1; then
    say "    sudo add-apt-repository -y ppa:apptainer/ppa && sudo apt update && sudo apt install -y apptainer"
  elif command -v dnf >/dev/null 2>&1; then
    say "    sudo dnf install -y apptainer"
  else
    say "    https://apptainer.org/docs/admin/main/installation.html"
  fi
fi

IMAGE_SHA256=""
if [ "$CONTAINER" -eq 1 ]; then
  step "Preparing the isolated container"
  if [ -f "$IMAGE" ]; then
    say "  Already downloaded: $IMAGE"
  else
    say "  Downloading the container image (about 400 MB, once)."
    run mkdir -p "$IMAGE_DIR"
    run apptainer pull "$IMAGE" "$IMAGE_SOURCE"
    run chmod 400 "$IMAGE"
  fi
  if [ -f "$IMAGE" ]; then
    # The app only ever runs this exact file: its checksum is recorded now and
    # checked on every start.
    IMAGE_SHA256=$(sha256sum "$IMAGE" | cut -d ' ' -f 1)
    say "  Recorded its checksum."
  elif [ "$DRY_RUN" -eq 0 ]; then
    say "The container image could not be downloaded. Run this again to retry." >&2
    exit 1
  fi
fi

step "Creating the dsh-forge command"
write_launcher() {
  mkdir -p "$BIN_DIR"
  {
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' '# Created by scripts/install.sh. Run it again to update this file.'
    if [ -n "$IMAGE_SHA256" ]; then
      printf 'export DSH_FORGE_SANDBOX_IMAGE="%s"\n' "$IMAGE"
      printf 'export DSH_FORGE_SANDBOX_IMAGE_SHA256="%s"\n' "$IMAGE_SHA256"
    fi
    printf 'exec python3 "%s/scripts/serve.py" --desktop --sync-catalog "$@"\n' "$REPO"
  } > "$LAUNCHER.tmp"
  chmod 755 "$LAUNCHER.tmp"
  mv "$LAUNCHER.tmp" "$LAUNCHER"
}
write_desktop_entry() {
  mkdir -p "$(dirname "$DESKTOP_ENTRY")"
  {
    printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=DSH Forge'
    printf '%s\n' 'Comment=Discover and run DeepSeek Harness plugins and forks'
    printf 'Exec=%s\n' "$LAUNCHER"
    printf 'Icon=%s/web/favicon.svg\n' "$REPO"
    printf '%s\n' 'Terminal=false' 'Categories=Development;'
  } > "$DESKTOP_ENTRY.tmp"
  mv "$DESKTOP_ENTRY.tmp" "$DESKTOP_ENTRY"
}
if [ "$DRY_RUN" -eq 1 ]; then
  say "  would write: $LAUNCHER"
  say "  would write: $DESKTOP_ENTRY"
else
  write_launcher
  write_desktop_entry
  say "  Wrote $LAUNCHER"
  say "  Wrote $DESKTOP_ENTRY"
fi

step "Done"
if [ "$CONTAINER" -eq 1 ]; then
  say "DSH Forge is set up to browse, install and run."
else
  say "DSH Forge is set up to browse. Running plugins and forks needs Apptainer (see above)."
fi
case ":$PATH:" in
  *":$BIN_DIR:"*) say "Start it with:  dsh-forge" ;;
  *) say "Start it with:  $LAUNCHER"
     say "(Add $BIN_DIR to your PATH to start it with just: dsh-forge)" ;;
esac

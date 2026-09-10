"""Stable command-line contract for the DSH Forge local cell registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Sequence

from .acquisition import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DEFAULT_QUARANTINE_ROOT,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOTAL_TIMEOUT_SECONDS,
    acquire as acquire_package,
)
from .installation import DEFAULT_INSTALL_ROOT, inspect_acquisition
from .launcher import Launcher, LauncherError
from .packages import (
    PackageError,
    canonical_bytes,
    compose as compose_package,
    create_trust_root,
    read_json,
    sign as sign_package,
    verify as verify_package,
    write_json,
)


CLI_API_VERSION = "dsh-forge.cli/v1"


class CliError(Exception):
    """A structured CLI policy or capability failure."""

    def __init__(self, message: str, code: str, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m dsh_forge",
        description="Discover Harness versions, control local cells, and manage signed package artifacts.",
    )
    parser.add_argument("--scan-root", action="append", default=[], metavar="PATH", help="add a bounded Harness scan root")
    parser.add_argument("--dsh-home", action="append", default=[], metavar="PATH", help="scan a DSH home for installed profiles")
    parser.add_argument("--state-dir", metavar="PATH", help="override the persistent DSH Forge state directory")
    parser.add_argument("--json", action="store_true", help="emit the stable compact JSON envelope")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="report runtime capabilities and registry health")

    versions = commands.add_parser("versions", help="inspect detected Harness versions")
    version_commands = versions.add_subparsers(dest="versions_command", required=True)
    version_commands.add_parser("list", help="list detected local Harness versions")
    add_version = version_commands.add_parser("add", help="save and scan a local Harness directory")
    add_version.add_argument("path", nargs="+", metavar="PATH")
    remove_version = version_commands.add_parser("remove", help="forget a saved directory without deleting it")
    remove_version.add_argument("version_id")
    configure_version = version_commands.add_parser("configure", help="save one-click launch preferences")
    configure_version.add_argument("version_id")
    configure_version.add_argument("--gpu", choices=("none", "allocated"))
    configure_version.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="open DSH Web automatically after launch",
    )
    version_commands.add_parser("rescan", help="rescan all configured and saved directories")

    catalog = commands.add_parser("catalog", help="import and search the local catalog store")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_commands.add_parser("status", help="report the imported catalog store and its provenance")
    import_catalog = catalog_commands.add_parser("import", help="build the local store from a validated snapshot")
    import_catalog.add_argument("snapshot", nargs="?", help="path to an unsigned catalog snapshot JSON file")
    import_catalog.add_argument("--package-feed", help="optional validated package catalog feed")
    import_catalog.add_argument("--envelope", help="signed DSSE catalog snapshot to verify and import")
    import_catalog.add_argument("--trust-root", dest="trust_root", help="trust root required to verify --envelope")
    sign_catalog = catalog_commands.add_parser("sign", help="wrap a catalog snapshot in a signed DSSE envelope")
    sign_catalog.add_argument("snapshot", help="path to the catalog snapshot JSON file")
    sign_catalog.add_argument("--key", required=True, help="Ed25519 private key PEM")
    sign_catalog.add_argument("--output", required=True, help="path to write the signed envelope")
    sign_catalog.add_argument("--force", action="store_true", help="overwrite an existing envelope")
    search_catalog = catalog_commands.add_parser("search", help="search the imported catalog store")
    search_catalog.add_argument("query", nargs="?", default="", help="free-text query; omit to browse")
    search_catalog.add_argument("--type", action="append", default=[], choices=["package", "plugin", "fork"], dest="types")
    search_catalog.add_argument("--sort", default="relevance", choices=["relevance", "rank", "stars", "recent", "name"])
    search_catalog.add_argument("--limit", type=int, default=25)
    search_catalog.add_argument("--cursor", default="", help="continue from a previous page")
    search_catalog.add_argument("--featured", action="store_true", help="only administrator-curated entries")
    search_catalog.add_argument("--licensed", action="store_true", help="only entries reporting a license")
    search_catalog.add_argument("--no-archived", action="store_true", help="exclude archived repositories")

    profiles = commands.add_parser("profiles", help="inspect and run installed DSH profiles")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    profile_commands.add_parser("list", help="list profiles found under configured DSH homes")
    run_profile = profile_commands.add_parser("run", help="run one detected profile in the current terminal")
    run_profile.add_argument("profile_id")
    run_profile.add_argument("--tree", dest="tree_id", help="use a specific detected DSH tree")
    run_profile.add_argument("--task", default="", help="task text required by a headless profile")
    run_profile.add_argument("args", nargs="*", metavar="ARG", help="arguments forwarded after --")

    configurations = commands.add_parser("configurations", aliases=["configs"], help="save and run reviewed Harness configurations")
    configuration_commands = configurations.add_subparsers(dest="configurations_command", required=True)
    configuration_commands.add_parser("list", help="list saved and MCP-drafted configurations")
    save_configuration = configuration_commands.add_parser("save", help="save a configuration without installing code")
    save_configuration.add_argument("--name", required=True)
    save_configuration.add_argument("--description", default="")
    save_configuration.add_argument("--version", required=True, dest="version_id")
    save_configuration.add_argument("--package", dest="package_slug")
    save_configuration.add_argument("--select", action="append", default=[], metavar="TYPE:ID")
    save_configuration.add_argument("--surface", choices=("web", "headless"), default="web")
    save_configuration.add_argument("--task", default="")
    save_configuration.add_argument("--profile", default="web")
    save_configuration.add_argument("--port", default="auto")
    save_configuration.add_argument("--network", choices=("none", "host"))
    save_configuration.add_argument("--gpu", choices=("none", "allocated"), default="none")
    save_configuration.add_argument("--open-browser", action=argparse.BooleanOptionalAction, default=False)
    save_configuration.add_argument("--draft", action="store_true", help="require a separate approve step before run")
    approve_configuration = configuration_commands.add_parser("approve", help="approve an inert draft for later CLI run")
    approve_configuration.add_argument("configuration_id")
    remove_configuration = configuration_commands.add_parser("remove", help="forget a configuration without deleting Harness files")
    remove_configuration.add_argument("configuration_id")
    run_configuration = configuration_commands.add_parser("run", help="run a reviewed configuration in Apptainer")
    run_configuration.add_argument("configuration_id")
    run_configuration.add_argument("--task", help="override the task of a headless configuration")

    cells = commands.add_parser("cells", help="control persistent local cells")
    cell_commands = cells.add_subparsers(dest="cells_command", required=True)
    cell_commands.add_parser("list", help="list cells, including recovered processes")

    inspect_command = cell_commands.add_parser("inspect", help="inspect one cell and its lineage")
    inspect_command.add_argument("cell_id")

    start = cell_commands.add_parser("start", help="start a fail-closed Apptainer cell")
    start.add_argument("--tree", required=True, dest="tree_id", help="detected tree ID from versions list")
    start.add_argument("--surface", choices=("web", "headless"), default="web")
    start.add_argument("--task", default="", help="required task text for the headless surface")
    start.add_argument("--port", default="auto", help="web port or 'auto'")
    start.add_argument("--profile", default="tui-min")
    start.add_argument("--home", choices=("fresh",), default="fresh", dest="home_mode")
    start.add_argument("--network", choices=("auto", "none", "host"), default="auto")
    start.add_argument("--gpu", choices=("none", "allocated"), default="none")

    stop = cell_commands.add_parser("stop", help="stop one identity-verified cell process group")
    stop.add_argument("cell_id")
    stop.add_argument("--timeout", type=float, default=3.0)

    restart = cell_commands.add_parser("restart", help="restart a cell from a sanitized state clone")
    restart.add_argument("cell_id")

    clone = cell_commands.add_parser("clone", help="start a parallel cell from a sanitized state clone")
    clone.add_argument("cell_id")

    logs = cell_commands.add_parser("logs", help="read captured process stdout and stderr")
    logs.add_argument("cell_id")
    logs.add_argument("--limit", type=int, default=100)
    logs.add_argument("--follow", action="store_true")

    open_url = cell_commands.add_parser("open-url", help="print a cell's authenticated loopback URL")
    open_url.add_argument("cell_id")

    artifacts = cell_commands.add_parser("artifacts", help="list files in a managed cell workspace")
    artifacts.add_argument("cell_id")
    artifacts.add_argument("--limit", type=int, default=100)

    prompt = cell_commands.add_parser("prompt", help="deliver a prompt when a verified adapter is available")
    prompt.add_argument("cell_id")
    prompt.add_argument("prompt")

    session_log = cell_commands.add_parser("session-log", help="read a normalized Harness session when an adapter is available")
    session_log.add_argument("cell_id")

    packages = commands.add_parser("packages", help="compose and verify signed package metadata offline")
    package_commands = packages.add_subparsers(dest="packages_command", required=True)

    compose = package_commands.add_parser("compose", help="compose a deterministic package manifest without fetching code")
    compose.add_argument("--spec", required=True, metavar="JSON")
    compose.add_argument("--output", required=True, metavar="JSON")
    compose.add_argument("--force", action="store_true")

    sign = package_commands.add_parser("sign", help="wrap a manifest in a DSSE envelope and sign it with Ed25519")
    sign.add_argument("--manifest", required=True, metavar="JSON")
    sign.add_argument("--private-key", required=True, metavar="PEM")
    sign.add_argument("--output", required=True, metavar="JSON")
    sign.add_argument("--force", action="store_true")

    trust = package_commands.add_parser("trust-root", help="create an explicit local trust root from an Ed25519 public key")
    trust.add_argument("--public-key", required=True, metavar="PEM")
    trust.add_argument("--root-id", required=True)
    trust.add_argument("--expires-at", required=True, metavar="UTC")
    trust.add_argument("--output", required=True, metavar="JSON")
    trust.add_argument("--force", action="store_true")

    verify = package_commands.add_parser("verify", help="verify DSSE signatures, canonical bytes, pins, and composition rules")
    verify.add_argument("--bundle", required=True, metavar="JSON")
    verify.add_argument("--trust-root", required=True, metavar="JSON")

    acquire = package_commands.add_parser(
        "acquire",
        help="verify a signed package and download exact artifacts into non-executable quarantine",
    )
    acquire.add_argument("--bundle", required=True, metavar="JSON")
    acquire.add_argument("--trust-root", required=True, metavar="JSON")
    acquire.add_argument(
        "--quarantine",
        default=str(DEFAULT_QUARANTINE_ROOT),
        metavar="DIR",
        help="content-addressed quarantine root (default: ~/.local/state/dsh-forge/quarantine)",
    )
    acquire.add_argument(
        "--max-artifact-bytes",
        type=int,
        default=DEFAULT_MAX_ARTIFACT_BYTES,
        metavar="N",
    )
    acquire.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
    )
    acquire.add_argument(
        "--max-total-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_BYTES,
        metavar="N",
    )
    acquire.add_argument(
        "--total-timeout",
        type=float,
        default=DEFAULT_TOTAL_TIMEOUT_SECONDS,
        metavar="SECONDS",
    )

    inspect = package_commands.add_parser(
        "inspect",
        help="re-verify acquired artifacts and inspect npm archives without host extraction",
    )
    inspect.add_argument("--bundle", required=True, metavar="JSON")
    inspect.add_argument("--trust-root", required=True, metavar="JSON")
    inspect.add_argument("--receipt", required=True, metavar="JSON")
    inspect.add_argument("--output", metavar="JSON")
    inspect.add_argument("--force", action="store_true")

    install = package_commands.add_parser(
        "install-sandbox",
        help="install a signed acquired package into a fresh Apptainer DSH profile",
    )
    install.add_argument("--bundle", required=True, metavar="JSON")
    install.add_argument("--trust-root", required=True, metavar="JSON")
    install.add_argument("--receipt", required=True, metavar="JSON")
    install.add_argument("--tree", required=True, dest="tree_id")
    install.add_argument("--profile", default="web")
    install.add_argument("--install-root", default=str(DEFAULT_INSTALL_ROOT), metavar="DIR")
    install.add_argument("--timeout", type=int, default=900, metavar="SECONDS")

    transact = package_commands.add_parser(
        "install",
        help="acquire and promote a signed package for one saved Harness version",
    )
    transact.add_argument("--bundle", required=True, metavar="JSON")
    transact.add_argument("--trust-root", required=True, metavar="JSON")
    transact.add_argument("--version", required=True, dest="version_id")
    transact.add_argument("--profile", default="web")
    transact.add_argument("--timeout", type=int, default=900, metavar="SECONDS")

    return parser


def _command_name(args: argparse.Namespace) -> str:
    if args.command == "cells":
        return f"cells.{args.cells_command}"
    if args.command == "versions":
        return f"versions.{args.versions_command}"
    if args.command == "profiles":
        return f"profiles.{args.profiles_command}"
    if args.command == "catalog":
        return f"catalog.{args.catalog_command}"
    if args.command in {"configurations", "configs"}:
        return f"configurations.{args.configurations_command}"
    if args.command == "packages":
        return f"packages.{args.packages_command}"
    return str(args.command)


def _envelope(command: str, ok: bool, *, data: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"api_version": CLI_API_VERSION, "ok": ok, "command": command}
    if ok:
        payload["data"] = data
    else:
        payload["error"] = error or {"code": "unknown", "message": "Unknown error"}
    return payload


def _write(payload: dict[str, Any], compact: bool, *, stream: Any = None) -> None:
    if stream is None:
        stream = sys.stdout
    if compact:
        stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    else:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    stream.flush()


def _start_spec(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "tree_id": args.tree_id,
        "surface": args.surface,
        "task": args.task,
        "port": args.port if args.surface == "web" else None,
        "profile": args.profile,
        "home_mode": args.home_mode,
        "workspace": "managed",
        "open_browser": False,
        "network": ("host" if args.surface == "web" else "none") if args.network == "auto" else args.network,
        "resources": {"gpu": args.gpu},
    }


def _configuration_selections(values: Sequence[str]) -> list[dict[str, str]]:
    selections: list[dict[str, str]] = []
    for value in values:
        kind, separator, identity = value.partition(":")
        if not separator or kind not in {"package", "plugin", "fork"} or not identity:
            raise CliError("Each --select value must be TYPE:ID (package, plugin, or fork).", "invalid_argument")
        selections.append({"type": kind, "id": identity})
    return selections


def _configuration_launch(args: argparse.Namespace) -> dict[str, Any]:
    network = args.network or ("host" if args.surface == "web" else "none")
    return {
        "surface": args.surface,
        "profile": args.profile,
        "task": args.task,
        "port": args.port,
        "open_browser": args.open_browser,
        "network": network,
        "resources": {"gpu": args.gpu},
        "workspace": "managed",
    }


def _follow_logs(launcher: Launcher, args: argparse.Namespace, command: str) -> None:
    seen: list[dict[str, str]] = []
    try:
        while True:
            current = launcher.logs(args.cell_id, limit=500)
            common = 0
            for old, new in zip(seen, current):
                if old != new:
                    break
                common += 1
            for line in current[common:]:
                if args.json:
                    _write(_envelope(command, True, data={"cell_id": args.cell_id, "line": line}), True)
                else:
                    print(line["msg"], flush=True)
            seen = current
            state = launcher.cell(args.cell_id).get("state")
            if state in {"stopped", "exited", "identity-mismatch"}:
                return
            time.sleep(0.5)
    except KeyboardInterrupt:
        return


def run(
    argv: Sequence[str] | None = None,
    *,
    launcher_factory: Callable[..., Launcher] = Launcher,
    acquirer: Callable[..., dict[str, Any]] = acquire_package,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    command = _command_name(args)
    try:
        if command == "packages.compose":
            manifest = compose_package(read_json(args.spec))
            write_json(args.output, manifest, force=args.force)
            data = {
                "output": str(Path(args.output).expanduser()),
                "package": manifest["package"],
                "plugin_count": len(manifest["plugins"]),
                "composition_digest": manifest["composition_digest"],
            }
        elif command == "packages.sign":
            manifest = read_json(args.manifest)
            envelope = sign_package(manifest, args.private_key)
            write_json(args.output, envelope, force=args.force)
            payload = canonical_bytes(manifest)
            data = {
                "output": str(Path(args.output).expanduser()),
                "keyid": envelope["signatures"][0]["keyid"],
                "payload_digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
        elif command == "packages.trust-root":
            root = create_trust_root(args.public_key, args.root_id, args.expires_at)
            write_json(args.output, root, force=args.force)
            data = {
                "output": str(Path(args.output).expanduser()),
                "root_id": root["root_id"],
                "keyids": [key["keyid"] for key in root["keys"]],
                "expires_at": root["expires_at"],
            }
        elif command == "packages.verify":
            verification = verify_package(read_json(args.bundle), read_json(args.trust_root))
            manifest = verification.pop("manifest")
            data = {
                **verification,
                "package": manifest["package"],
                "plugin_count": len(manifest["plugins"]),
                "composition_digest": manifest["composition_digest"],
                "execution_authorized": False,
            }
        elif command == "packages.acquire":
            data = acquirer(
                read_json(args.bundle),
                read_json(args.trust_root),
                args.quarantine,
                max_artifact_bytes=args.max_artifact_bytes,
                max_total_bytes=args.max_total_bytes,
                timeout_seconds=args.timeout,
                total_timeout_seconds=args.total_timeout,
            )
        elif command == "packages.inspect":
            data = inspect_acquisition(
                read_json(args.bundle),
                read_json(args.trust_root),
                args.receipt,
            )
            if args.output:
                write_json(args.output, data, force=args.force)
                data = {**data, "output": str(Path(args.output).expanduser())}
        elif command == "packages.install-sandbox":
            launcher = launcher_factory(scan_roots=args.scan_root, state_root=args.state_dir, dsh_homes=args.dsh_home)
            data = launcher.install_acquired_package(
                tree_id=args.tree_id,
                envelope=read_json(args.bundle),
                trust_root=read_json(args.trust_root),
                receipt_path=args.receipt,
                install_root=args.install_root,
                profile=args.profile,
                timeout_seconds=args.timeout,
            )
        elif command == "packages.install":
            launcher = launcher_factory(scan_roots=args.scan_root, state_root=args.state_dir, dsh_homes=args.dsh_home)
            data = launcher.install_package(
                version_id=args.version_id,
                envelope=read_json(args.bundle),
                trust_root=read_json(args.trust_root),
                profile=args.profile,
                timeout_seconds=args.timeout,
            )
        else:
            launcher = launcher_factory(scan_roots=args.scan_root, state_root=args.state_dir, dsh_homes=args.dsh_home)
            if command == "doctor":
                status = launcher.status()
                data = {
                    "mode": status["mode"],
                    "registry": status["registry"],
                    "sandbox": status["sandbox"],
                    "capabilities": status["capabilities"],
                    "tree_count": len(status["trees"]),
                    "cell_count": len(status["cells"]),
                }
            elif command == "versions.list":
                status = launcher.status()
                data = {
                    "versions": status["trees"],
                    "saved_versions": status["saved_versions"],
                    "versions_directory": status["versions_directory"],
                    "coverage_gaps": status["coverage_gaps"],
                }
            elif command == "versions.add":
                status = launcher.add_scan_roots(args.path)
                data = {
                    "versions": status["trees"],
                    "saved_versions": status["saved_versions"],
                    "versions_directory": status["versions_directory"],
                    "coverage_gaps": status["coverage_gaps"],
                }
            elif command == "versions.remove":
                status = launcher.remove_saved_version(args.version_id)
                data = {
                    "versions": status["trees"],
                    "saved_versions": status["saved_versions"],
                    "versions_directory": status["versions_directory"],
                    "coverage_gaps": status["coverage_gaps"],
                }
            elif command == "versions.configure":
                updates = {}
                if args.gpu is not None:
                    updates["gpu"] = args.gpu
                if args.open_browser is not None:
                    updates["open_browser"] = args.open_browser
                if not updates:
                    raise CliError(
                        "Choose --gpu, --open-browser, or --no-open-browser.",
                        "invalid_argument",
                    )
                status = launcher.update_saved_version(args.version_id, updates)
                data = {
                    "versions": status["trees"],
                    "saved_versions": status["saved_versions"],
                    "versions_directory": status["versions_directory"],
                    "coverage_gaps": status["coverage_gaps"],
                }
            elif command == "versions.rescan":
                status = launcher.scan()
                data = {
                    "versions": status["trees"],
                    "saved_versions": status["saved_versions"],
                    "versions_directory": status["versions_directory"],
                    "coverage_gaps": status["coverage_gaps"],
                }
            elif command == "catalog.status":
                data = launcher.catalog_store.status()
            elif command == "catalog.import":
                if bool(args.snapshot) == bool(args.envelope):
                    raise LauncherError("Provide either a snapshot path or --envelope, not both")
                data = launcher.import_catalog(
                    read_json(args.snapshot) if args.snapshot else None,
                    package_feed=read_json(args.package_feed) if args.package_feed else None,
                    envelope=read_json(args.envelope) if args.envelope else None,
                    trust_root=read_json(args.trust_root) if args.trust_root else None,
                )
            elif command == "catalog.sign":
                from .catalog_store import sign_snapshot

                envelope = sign_snapshot(read_json(args.snapshot), args.key)
                write_json(args.output, envelope, force=args.force)
                data = {
                    "output": str(Path(args.output).expanduser()),
                    "payload_type": envelope["payloadType"],
                    "signers": [item["keyid"] for item in envelope["signatures"]],
                }
            elif command == "catalog.search":
                data = launcher.catalog_search(
                    query=args.query,
                    types=args.types,
                    sort=args.sort,
                    limit=args.limit,
                    cursor=args.cursor,
                    featured_only=args.featured,
                    licensed_only=args.licensed,
                    include_archived=not args.no_archived,
                )
            elif command == "profiles.list":
                status = launcher.status()
                data = {"profiles": status["profiles"], "dsh_homes": status["dsh_homes"]}
            elif command == "profiles.run":
                extra_args = list(args.args)
                if extra_args[:1] == ["--"]:
                    extra_args = extra_args[1:]
                exit_code = launcher.run_profile_foreground(
                    args.profile_id,
                    tree_id=args.tree_id,
                    task=args.task,
                    extra_args=extra_args,
                )
                data = {"profile_id": args.profile_id, "exit_code": exit_code}
            elif command == "configurations.list":
                data = {"configurations": launcher.configurations()}
            elif command == "configurations.save":
                data = launcher.save_configuration(
                    name=args.name,
                    description=args.description,
                    version_id=args.version_id,
                    package_slug=args.package_slug,
                    selections=_configuration_selections(args.select),
                    launch=_configuration_launch(args),
                    draft=args.draft,
                )
            elif command == "configurations.approve":
                data = launcher.approve_configuration(args.configuration_id)
            elif command == "configurations.remove":
                data = {"configurations": launcher.remove_configuration(args.configuration_id)}
            elif command == "configurations.run":
                data = launcher.run_configuration(args.configuration_id, task=args.task)
            elif command == "cells.list":
                status = launcher.status()
                data = {"cells": status["cells"], "registry": status["registry"]}
            elif command == "cells.inspect":
                data = launcher.cell(args.cell_id)
            elif command == "cells.start":
                data = launcher.launch(_start_spec(args))
            elif command == "cells.stop":
                if args.timeout <= 0 or args.timeout > 30:
                    raise CliError("Stop timeout must be greater than 0 and at most 30 seconds.", "invalid_argument")
                data = launcher.stop(args.cell_id, timeout=args.timeout)
            elif command == "cells.restart":
                data = launcher.restart(args.cell_id)
            elif command == "cells.clone":
                data = launcher.clone(args.cell_id)
            elif command == "cells.logs":
                if args.follow:
                    _follow_logs(launcher, args, command)
                    return 0
                data = {"cell_id": args.cell_id, "lines": launcher.logs(args.cell_id, limit=args.limit)}
            elif command == "cells.open-url":
                data = {"cell_id": args.cell_id, "url": launcher.open_url(args.cell_id)}
            elif command == "cells.artifacts":
                data = {"cell_id": args.cell_id, "artifacts": launcher.artifacts(args.cell_id, limit=args.limit)}
            elif command == "cells.prompt":
                raise CliError(
                    "Prompt delivery is unavailable until a versioned Harness transport adapter is verified.",
                    "capability_unavailable",
                    4,
                )
            elif command == "cells.session-log":
                raise CliError(
                    "A normalized Harness session transcript is unavailable; use cells logs for process output.",
                    "capability_unavailable",
                    4,
                )
            else:
                raise CliError("Unknown command", "unknown_command")
    except CliError as error:
        _write(
            _envelope(command, False, error={"code": error.code, "message": str(error)}),
            args.json,
            stream=sys.stderr,
        )
        return error.exit_code
    except PackageError as error:
        _write(
            _envelope(command, False, error={"code": error.code, "message": str(error)}),
            args.json,
            stream=sys.stderr,
        )
        return 2
    except LauncherError as error:
        _write(
            _envelope(command, False, error={"code": "launcher_error", "message": str(error)}),
            args.json,
            stream=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as error:
        _write(
            _envelope(command, False, error={"code": "local_io_error", "message": str(error)}),
            args.json,
            stream=sys.stderr,
        )
        return 2
    _write(_envelope(command, True, data=data), args.json)
    return 0


def main() -> int:
    return run()

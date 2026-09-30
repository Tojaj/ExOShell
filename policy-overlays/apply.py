#!/usr/bin/env python3
"""Compose and load an OpenShell sandbox network policy from overlays.

Usage
-----
  apply.py --sandbox NAME [OVERLAY ...]              apply overlays to live policy
  apply.py --sandbox NAME --revert [OVERLAY ...]     start from BASE_FILE policy

Overlay resolution
------------------
  - A bare name (no slashes, no .yaml suffix) -> <repo>/policy-overlays/<name>.yaml
  - A bare name with .yaml -> <repo>/policy-overlays/<name>
  - Any path containing a slash or starting with . -> used as-is

Composition semantics
---------------------
  Each overlay entry replaces the `network_policies` entry with the same name
  as a whole. Entries with distinct names compose. Overlay files must contain
  exactly one root key, `network_policies`.

Static-section handling
-----------------------
  The sandbox supervisor enriches filesystem paths at startup, and policy set
  validates that existing paths are not removed. This script always derives the
  static sections (filesystem_policy, landlock, process) from the LIVE policy
  (`openshell policy get --base -o json`). Only `network_policies` is composed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is required: pip install pyyaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
OVERLAY_DIR = REPO_ROOT / "policy-overlays"
PUBLIC_BASE_FILE = REPO_ROOT / "policies" / "policy.yaml"
LOCAL_CONFIG_FILE = REPO_ROOT / ".exoshell.local.toml"


class PolicyError(ValueError):
    """A concise, user-actionable policy composition error."""


class DuplicateKeyError(ValueError):
    """Raised by the YAML loader instead of silently overwriting a key."""


class StrictLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys at every depth."""


def construct_mapping(loader: StrictLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise DuplicateKeyError(f"mapping key {key!r} is not a scalar") from error
        if duplicate:
            raise DuplicateKeyError(f"duplicate YAML key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


def default_base_file(config_path: Path = LOCAL_CONFIG_FILE) -> Path:
    """Return the local launcher policy, or the portable public baseline."""
    if not config_path.is_file():
        return PUBLIC_BASE_FILE
    try:
        with config_path.open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PolicyError(f"cannot load launcher configuration {config_path}: {error}") from error
    policy = config.get("policy")
    if policy is None:
        return PUBLIC_BASE_FILE
    if not isinstance(policy, str) or not policy:
        raise PolicyError(f"configuration key 'policy' must be a non-empty string: {config_path}")
    path = Path(policy).expanduser()
    return (path if path.is_absolute() else config_path.parent / path).resolve(strict=False)


# ---------------------------------------------------------------------------
# YAML loading and structural validation
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> Any:
    """Load YAML safely, reporting duplicate and syntax errors with their file."""
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.load(stream, Loader=StrictLoader)
    except OSError as error:
        raise PolicyError(f"cannot read {path}: {error.strerror or error}") from error
    except DuplicateKeyError as error:
        raise PolicyError(f"{path}: {error}") from error
    except yaml.YAMLError as error:
        raise PolicyError(f"cannot parse YAML {path}: {error.problem or error}") from error


def validate_network_policies(
    document: Any, source: str, *, overlay: bool
) -> dict[str, dict[str, Any]]:
    """Validate the small, stable structure needed to compose policy entries."""
    if not isinstance(document, dict):
        raise PolicyError(f"{source}: document root must be a mapping")

    if overlay and set(document) != {"network_policies"}:
        raise PolicyError(f"{source}: document root must contain exactly 'network_policies'")
    if "network_policies" not in document:
        raise PolicyError(f"{source}: missing 'network_policies'")

    policies = document["network_policies"]
    if not isinstance(policies, dict):
        raise PolicyError(f"{source}: 'network_policies' must be a mapping")

    for key, entry in policies.items():
        field = f"{source}: network_policies.{key!r}"
        if not isinstance(key, str):
            raise PolicyError(f"{source}: network_policies keys must be strings")
        if key.startswith("_"):
            raise PolicyError(f"{field}: reserved policy keys cannot start with '_'")
        if not isinstance(entry, dict):
            raise PolicyError(f"{field}: policy entry must be a mapping")
        for name in ("endpoints", "binaries"):
            if name in entry and not isinstance(entry[name], list):
                raise PolicyError(f"{field}.{name}: must be a list")
        for index, endpoint in enumerate(entry.get("endpoints", [])):
            if not isinstance(endpoint, dict):
                raise PolicyError(f"{field}.endpoints[{index}]: must be a mapping")

    return policies


def load_overlay(path: Path) -> dict[str, dict[str, Any]]:
    """Load one strictly-shaped overlay file."""
    return validate_network_policies(load_yaml(path), str(path), overlay=True)


def load_base_network_policies(path: Path) -> dict[str, dict[str, Any]]:
    """Load the network portion of a full policy file used by --revert."""
    return validate_network_policies(load_yaml(path), str(path), overlay=False)


# ---------------------------------------------------------------------------
# Overlay resolution and composition
# ---------------------------------------------------------------------------

def resolve_overlay(name: str) -> Path:
    """Resolve a bare overlay name or an explicit path to an absolute Path."""
    path = Path(name)
    if "/" in name or name.startswith("."):
        if not path.is_file():
            raise PolicyError(f"overlay not found: {name}")
        return path.resolve()

    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    candidate = OVERLAY_DIR / filename
    if not candidate.is_file():
        raise PolicyError(f"overlay not found: {candidate}")
    return candidate.resolve()


def resolve_overlays(names: list[str]) -> list[Path]:
    """Resolve all requested overlays in command-line order."""
    return [resolve_overlay(name) for name in names]


def compose_network_policies(
    base: dict[str, dict[str, Any]], overlays: list[tuple[Path, dict[str, dict[str, Any]]]]
) -> dict[str, dict[str, Any]]:
    """Replace colliding entries wholesale while composing distinct policy keys."""
    seen_keys: dict[str, Path] = {}
    composed = dict(base)
    for path, policies in overlays:
        for key, entry in policies.items():
            if key in seen_keys:
                raise PolicyError(
                    f"network_policies key {key!r} appears in both "
                    f"{seen_keys[key]} and {path}"
                )
            seen_keys[key] = path
            composed[key] = entry
    return composed


# ---------------------------------------------------------------------------
# Local invariants
# ---------------------------------------------------------------------------

def effective_ports(endpoint: dict[str, Any], field: str) -> list[int]:
    """Mirror OpenShell's port precedence for the GraphQL selector identity."""
    if "ports" in endpoint:
        ports = endpoint["ports"]
        if not isinstance(ports, list) or not all(type(port) is int for port in ports):
            raise PolicyError(f"{field}.ports: must be a list of integers")
        if ports:
            return [port for port in ports if port > 0]

    port = endpoint.get("port", 0)
    if type(port) is not int:
        raise PolicyError(f"{field}.port: must be an integer")
    return [port] if port > 0 else []


def validate_invariants(network_policies: dict[str, dict[str, Any]]) -> None:
    """Check stable local invariants; OpenShell remains the ambiguity authority."""
    graphql_selectors: dict[tuple[str, int, str], str] = {}
    for key, entry in network_policies.items():
        for index, endpoint in enumerate(entry.get("endpoints", [])):
            field = f"network_policies.{key}.endpoints[{index}]"
            if "access" in endpoint and "rules" in endpoint:
                raise PolicyError(f"{field}: 'access' and 'rules' are mutually exclusive")
            if endpoint.get("protocol") != "graphql":
                continue

            host = endpoint.get("host", "")
            path = endpoint.get("path", "")
            if not isinstance(host, str):
                raise PolicyError(f"{field}.host: must be a string")
            if not isinstance(path, str):
                raise PolicyError(f"{field}.path: must be a string")
            for port in effective_ports(endpoint, field):
                selector = (host, port, path)
                previous = graphql_selectors.get(selector)
                if previous is not None:
                    raise PolicyError(
                        f"duplicate GraphQL selector host={host!r} port={port} path={path!r} "
                        f"in {previous} and {field}"
                    )
                graphql_selectors[selector] = field


# ---------------------------------------------------------------------------
# Diff and OpenShell execution
# ---------------------------------------------------------------------------

def summarise_diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return a short list of changed network_policies keys."""
    lines = []
    for key in sorted(set(before) | set(after)):
        if key not in before:
            lines.append(f"  + {key}")
        elif key not in after:
            lines.append(f"  - {key}")
        elif before[key] != after[key]:
            lines.append(f"  ~ {key} (changed)")
    return lines or ["  (no network_policies changes)"]


def get_live_policy(sandbox: str) -> dict[str, Any]:
    """Fetch the live policy so static sections remain untouched."""
    result = subprocess.run(
        ["openshell", "policy", "get", sandbox, "--base", "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PolicyError(f"openshell policy get failed:\n{result.stderr.strip()}")
    try:
        policy = json.loads(result.stdout)["policy"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise PolicyError("openshell policy get returned invalid JSON") from error
    if not isinstance(policy, dict):
        raise PolicyError("openshell policy get returned a non-mapping policy")
    return policy


def apply_policy(policy: dict[str, Any], sandbox: str, *, wait: bool, timeout: int) -> None:
    """Write the policy temporarily and hand it to the OpenShell CLI."""
    temporary = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8")
    try:
        yaml.safe_dump(policy, temporary, sort_keys=False)
        temporary.close()
        command = ["openshell", "policy", "set", sandbox, "--policy", temporary.name]
        if wait:
            command += ["--wait", "--timeout", str(timeout)]
        result = subprocess.run(command)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    finally:
        try:
            os.unlink(temporary.name)
        except OSError:
            pass


def parser(base_file: Path) -> argparse.ArgumentParser:
    """Build the command-line parser after resolving the default baseline."""
    argument_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    argument_parser.add_argument("overlays", nargs="*", metavar="OVERLAY")
    argument_parser.add_argument("-s", "--sandbox", required=True, metavar="NAME")
    argument_parser.add_argument(
        "-b",
        "--base-file",
        default=str(base_file),
        help=f"Base policy file for --revert (default: {base_file})",
    )
    argument_parser.add_argument("--revert", action="store_true")
    argument_parser.add_argument("-n", "--dry-run", action="store_true")
    argument_parser.add_argument("--print", action="store_true", dest="print_yaml")
    argument_parser.add_argument("--no-wait", action="store_true")
    argument_parser.add_argument("--timeout", type=int, default=60, metavar="N")
    return argument_parser


def main() -> None:
    try:
        args = parser(default_base_file()).parse_args()
        print(f"Fetching live base policy for sandbox '{args.sandbox}' ...", file=sys.stderr)
        live_policy = get_live_policy(args.sandbox)
        live_network = validate_network_policies(live_policy, "live policy", overlay=False)

        if args.revert:
            composed_base = load_base_network_policies(Path(args.base_file))
            print(f"--revert: starting from network_policies in '{args.base_file}'", file=sys.stderr)
        else:
            composed_base = live_network

        overlay_paths = resolve_overlays(args.overlays)
        overlays = [(path, load_overlay(path)) for path in overlay_paths]
        composed_network = compose_network_policies(composed_base, overlays)
        validate_invariants(composed_network)

        for path, policies in overlays:
            print(f"Applied overlay: {path.name} ({', '.join(policies)})", file=sys.stderr)

        final_policy = dict(live_policy)
        final_policy["network_policies"] = composed_network
        print("network_policies changes:", file=sys.stderr)
        for line in summarise_diff(live_network, composed_network):
            print(line, file=sys.stderr)

        if args.print_yaml or args.dry_run:
            print(yaml.safe_dump(final_policy, sort_keys=False))
        if args.dry_run:
            print("(dry run - not applied)", file=sys.stderr)
            return

        apply_policy(final_policy, args.sandbox, wait=not args.no_wait, timeout=args.timeout)
        print(f"Policy applied to sandbox '{args.sandbox}'.", file=sys.stderr)
    except PolicyError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()

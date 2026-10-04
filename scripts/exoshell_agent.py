#!/usr/bin/env python3
"""Validated configuration and command construction for the agent launcher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any, Sequence


CONTAINER_WORKSPACE = "/workspace"
CONTAINER_HOME = "/sandbox"
AGENTS: dict[str, dict[str, Any]] = {
    "codex": {
        "executable": "codex",
        "providers": ["exoshell-codex"],
    },
    "claude": {
        "executable": "claude",
        "providers": [],
    },
    "opencode": {
        "executable": "opencode",
        "providers": [],
    },
}
DEFAULTS: dict[str, Any] = {
    "agent": "codex",
    "image": "localhost/exoshell-local:latest",
    "providers": [],
    "policy": None,
    "kubeconfig": None,
    "github_host": None,
    "gitlab_host": None,
    "keep": False,
}
CONFIG_KEYS = (set(DEFAULTS) - {"keep"}) | {"agents", "host_share"}
PATH_KEYS = {"host_share", "policy", "kubeconfig"}
HOST_RE = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*\Z"
)


class LauncherError(Exception):
    """An actionable user configuration error."""


def parser(*, prog: str = "run-exoshell-agent.sh") -> argparse.ArgumentParser:
    """Build the launcher command-line parser."""
    result = argparse.ArgumentParser(
        prog=prog,
        description="Create an OpenShell sandbox and start a coding agent in PROJECT.",
        epilog="Arguments after -- are passed unchanged to the selected agent.",
    )
    result.add_argument("--agent", choices=AGENTS, help="coding agent (default: codex)")
    result.add_argument("--config", type=Path, help="TOML configuration file")
    result.add_argument("--image", help="sandbox OCI image")
    result.add_argument(
        "--keep",
        action="store_true",
        help="retain the sandbox after the agent exits (for debugging)",
    )
    result.add_argument("--host-share", type=Path, help="host directory mounted at /workspace")
    providers = result.add_mutually_exclusive_group()
    providers.add_argument("--provider", action="append", dest="providers", metavar="NAME")
    providers.add_argument("--no-providers", action="store_true")
    _nullable_path_option(result, "policy", "sandbox policy YAML")
    _nullable_path_option(result, "kubeconfig", "kubeconfig file")
    _nullable_host_option(result, "github", "GitHub")
    _nullable_host_option(result, "gitlab", "GitLab")
    result.add_argument("project", nargs="?", type=Path, help="project directory (default: current directory)")
    return result


def _nullable_path_option(target: argparse.ArgumentParser, name: str, help_text: str) -> None:
    group = target.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", type=Path, help=help_text)
    group.add_argument(f"--no-{name}", action="store_true", help=f"clear configured {name}")


def _nullable_host_option(target: argparse.ArgumentParser, name: str, display_name: str) -> None:
    group = target.add_mutually_exclusive_group()
    group.add_argument(f"--{name}-host", help=f"configure a {display_name} host")
    group.add_argument(f"--no-{name}-host", action="store_true", help=f"disable {display_name} host configuration")


def split_agent_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split launcher arguments from agent arguments at the first ``--``."""
    try:
        separator = argv.index("--")
    except ValueError:
        return list(argv), []
    return list(argv[:separator]), list(argv[separator + 1 :])


def _resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _provider_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list) or any(type(item) is not str or not item for item in value):
        raise LauncherError(f"configuration key '{key}' must be an array of non-empty strings")
    _reject_duplicates(value, "provider")
    return value


def load_config(path: Path, *, required: bool) -> dict[str, Any]:
    """Load and validate launcher settings from a TOML file."""
    if not path.exists():
        if required:
            raise LauncherError(f"configuration file does not exist: {path}")
        return {}
    if not path.is_file():
        raise LauncherError(f"configuration path is not a file: {path}")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise LauncherError(f"cannot load configuration {path}: {error}") from error
    unknown = sorted(set(data) - CONFIG_KEYS)
    if unknown:
        raise LauncherError(f"unknown configuration key(s): {', '.join(unknown)}")

    for key, value in data.items():
        if key == "providers":
            _provider_list(value, key)
        elif key == "agents":
            if not isinstance(value, dict):
                raise LauncherError("configuration key 'agents' must be a table")
            unknown_agents = sorted(set(value) - AGENTS.keys())
            if unknown_agents:
                raise LauncherError(f"unknown agent configuration(s): {', '.join(unknown_agents)}")
            for agent, agent_config in value.items():
                if not isinstance(agent_config, dict):
                    raise LauncherError(f"configuration key 'agents.{agent}' must be a table")
                unknown_agent_keys = sorted(set(agent_config) - {"providers"})
                if unknown_agent_keys:
                    raise LauncherError(
                        f"unknown configuration key(s) for agents.{agent}: {', '.join(unknown_agent_keys)}"
                    )
                if "providers" in agent_config:
                    _provider_list(agent_config["providers"], f"agents.{agent}.providers")
        elif key == "agent":
            if type(value) is not str or value not in AGENTS:
                raise LauncherError(f"configuration key 'agent' must be one of: {', '.join(AGENTS)}")
        elif type(value) is not str or not value:
            raise LauncherError(f"configuration key '{key}' must be a non-empty string")

    for key in PATH_KEYS & data.keys():
        data[key] = _resolve_path(data[key], path.parent)
    return data


def _reject_duplicates(values: Sequence[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise LauncherError(f"duplicate {label}(s): {', '.join(duplicates)}")


def resolve_settings(args: argparse.Namespace, config: dict[str, Any], *, cwd: Path) -> dict[str, Any]:
    """Merge defaults, configuration, and CLI overrides into validated settings."""
    settings = {**DEFAULTS, **config}
    if args.agent is not None:
        settings["agent"] = args.agent
    if args.image is not None:
        if not args.image:
            raise LauncherError("--image cannot be empty")
        settings["image"] = args.image
    if args.keep:
        settings["keep"] = True

    if args.host_share is not None:
        settings["host_share"] = _resolve_path(args.host_share, cwd)

    if args.providers is not None:
        if any(not provider for provider in args.providers):
            raise LauncherError("--provider cannot be empty")
        _reject_duplicates(args.providers, "provider")
        settings["providers"] = args.providers
    elif args.no_providers:
        settings["providers"] = []
    else:
        common = list(settings["providers"])
        configured_agents = config.get("agents", {})
        selected = configured_agents.get(settings["agent"], {}).get(
            "providers", AGENTS[settings["agent"]]["providers"]
        )
        settings["providers"] = common + list(selected)
        _reject_duplicates(settings["providers"], "provider")

    for key in ("policy", "kubeconfig"):
        if getattr(args, f"no_{key}"):
            settings[key] = None
        elif getattr(args, key) is not None:
            settings[key] = _resolve_path(getattr(args, key), cwd)

    for key in ("github_host", "gitlab_host"):
        if getattr(args, f"no_{key}"):
            settings[key] = None
        elif getattr(args, key) is not None:
            settings[key] = getattr(args, key)

    project = _resolve_path(args.project or cwd, cwd)
    host_share = settings.get("host_share")
    settings["project"] = canonical_directory(project, "project")
    settings["host_share"] = canonical_directory(
        _resolve_path(host_share, cwd) if host_share is not None else project, "host share"
    )
    try:
        relative_project = settings["project"].relative_to(settings["host_share"])
    except ValueError as error:
        raise LauncherError(f"project {settings['project']} is outside host share {settings['host_share']}") from error
    settings["container_project"] = str(Path(CONTAINER_WORKSPACE) / relative_project)

    for key in ("policy", "kubeconfig"):
        value = settings[key]
        if value is not None:
            value = value.resolve(strict=False)
            if not value.is_file():
                raise LauncherError(f"{key} file does not exist: {value}")
            settings[key] = value.resolve(strict=True)
    for key, display_name in (("github_host", "GitHub"), ("gitlab_host", "GitLab")):
        host = settings[key]
        if host is not None and not HOST_RE.fullmatch(host):
            raise LauncherError(f"invalid {display_name} host: {host!r}")
    settings.pop("agents", None)
    return settings


def canonical_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise LauncherError(f"{label} does not exist: {path}") from error
    if not resolved.is_dir():
        raise LauncherError(f"{label} is not a directory: {resolved}")
    return resolved


def project_label(project: Path) -> str:
    """Normalize a project directory basename for an OpenShell label value."""
    normalized = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-")
    return normalized[:63] or "project"


def mount_config(settings: dict[str, Any]) -> dict[str, Any]:
    """Build Podman mount configuration for the sandbox."""
    mounts: list[dict[str, Any]] = [
        {
            "type": "bind",
            "source": str(settings["host_share"]),
            "target": CONTAINER_WORKSPACE,
            "read_only": False,
            "selinux_label": "shared",
        }
    ]
    if settings["kubeconfig"] is not None:
        mounts.append(
            {
                "type": "bind",
                "source": str(settings["kubeconfig"]),
                "target": f"{CONTAINER_HOME}/.kube/config",
                "read_only": True,
                "selinux_label": "shared",
            }
        )
    # Provision storage even when GWS is attached after sandbox creation.
    mounts.append({"type": "tmpfs", "target": "/tmp/gws", "mode": 0o777})
    return {"podman": {"mounts": mounts}}


def git_identity(project: Path) -> tuple[str, str]:
    values: list[str] = []
    for key in ("user.name", "user.email"):
        try:
            result = subprocess.run(
                ["git", "-C", str(project), "config", "--get", key],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise LauncherError(
                f"Git {key} is not configured for {project}; configure it locally or globally"
            ) from error
        value = result.stdout.rstrip("\n")
        if not value:
            raise LauncherError(f"Git {key} is empty for {project}")
        values.append(value)
    return values[0], values[1]


def environment_args(settings: dict[str, Any], name: str, email: str) -> list[str]:
    environment = ["UV_CACHE_DIR=/tmp/uv-cache"]
    environment.extend(
        [
            f"GIT_AUTHOR_NAME={name}",
            f"GIT_AUTHOR_EMAIL={email}",
            f"GIT_COMMITTER_NAME={name}",
            f"GIT_COMMITTER_EMAIL={email}",
        ]
    )
    git_config = [("user.name", name), ("user.email", email)]
    if settings["kubeconfig"] is not None:
        environment.append(f"KUBECONFIG={CONTAINER_HOME}/.kube/config")
    if settings["github_host"] is not None:
        host = settings["github_host"]
        environment.append(f"GH_HOST={host}")
        git_config.extend(
            [
                (f"credential.https://{host}.helper", "!/usr/bin/gh auth git-credential"),
                (f"url.https://{host}/.insteadOf", f"git@{host}:"),
            ]
        )
    if settings["gitlab_host"] is not None:
        host = settings["gitlab_host"]
        environment.append(f"GITLAB_HOST={host}")
        git_config.extend(
            [
                (f"credential.https://{host}.helper", '!f(){ echo username=oauth2; echo "password=$GITLAB_TOKEN"; };f'),
                (f"url.https://{host}/.insteadOf", f"git@{host}:"),
            ]
        )
    environment.append(f"GIT_CONFIG_COUNT={len(git_config)}")
    for index, (key, value) in enumerate(git_config):
        environment.extend([f"GIT_CONFIG_KEY_{index}={key}", f"GIT_CONFIG_VALUE_{index}={value}"])
    result: list[str] = []
    for value in environment:
        result.extend(["--env", value])
    return result


def create_command(settings: dict[str, Any], agent_args: Sequence[str], name: str, email: str) -> list[str]:
    """Build the complete OpenShell sandbox creation command."""
    command = ["openshell", "sandbox", "create", "--from", settings["image"]]
    if not settings["keep"]:
        command.append("--no-keep")
    for label in (
        "managed-by=exoshell",
        f"project={project_label(settings['project'])}",
        f"agent={settings['agent']}",
    ):
        command.extend(["--label", label])
    for provider in settings["providers"]:
        command.extend(["--provider", provider])
    if settings["policy"] is not None:
        command.extend(["--policy", str(settings["policy"])])
    command.extend(environment_args(settings, name, email))
    command.append("--driver-config-json=" + json.dumps(mount_config(settings), separators=(",", ":")))
    command.extend(
        [
            "--", "/usr/local/bin/exoshell-agent", settings["container_project"], "--",
            AGENTS[settings["agent"]]["executable"], *agent_args,
        ]
    )
    return command


def is_local_image(image: str) -> bool:
    return image.startswith("localhost/")


def run(argv: Sequence[str], *, root: Path, cwd: Path) -> int:
    launcher_args, agent_args = split_agent_args(argv)
    args = parser().parse_args(launcher_args)
    config_path = _resolve_path(args.config, cwd) if args.config is not None else root / ".exoshell.local.toml"
    config = load_config(config_path.resolve(strict=False), required=args.config is not None)
    settings = resolve_settings(args, config, cwd=cwd)
    if is_local_image(settings["image"]):
        try:
            image_result = subprocess.run(["podman", "image", "exists", settings["image"]])
        except FileNotFoundError as error:
            raise LauncherError("podman is required to check a localhost image") from error
        if image_result.returncode:
            raise LauncherError(
                f"local image is missing: {settings['image']} (build sandboxes/local-user first)"
            )
    name, email = git_identity(settings["project"])
    try:
        return subprocess.run(create_command(settings, agent_args, name, email)).returncode
    except FileNotFoundError as error:
        raise LauncherError("openshell command was not found") from error


def main() -> int:
    try:
        return run(
            sys.argv[1:], root=Path(__file__).resolve().parents[1], cwd=Path.cwd()
        )
    except LauncherError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

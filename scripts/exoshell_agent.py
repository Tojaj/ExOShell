#!/usr/bin/env python3
"""Validated configuration and command construction for the agent launcher."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Sequence


CONTAINER_WORKSPACE = "/workspace"
CONTAINER_HOME = "/sandbox"
CONTAINER_SKILLS_SNAPSHOT = "/tmp/exoshell-skills"
SYSTEM_CONFIG_FILE = Path("/etc/exoshell/exoshell.local.toml")
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
    "model": None,
    "effort": None,
    "skills": [],
}
CONFIG_KEYS = (set(DEFAULTS) - {"keep", "model", "effort"}) | {"agents", "host_share"}
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
        epilog=(
            "Load only the first configuration file: --config PATH, "
            ".exoshell.local.toml in the caller's current directory, "
            "$XDG_CONFIG_HOME/exoshell/exoshell.local.toml (default: "
            "~/.config/exoshell/exoshell.local.toml), then "
            "/etc/exoshell/exoshell.local.toml. Unset, empty, or relative "
            "XDG_CONFIG_HOME uses ~/.config. Missing keys use built-in defaults. "
            "Arguments after -- are passed unchanged to the selected agent."
        ),
    )
    result.add_argument("--agent", choices=AGENTS, help="coding agent (default: codex)")
    for key in ("model", "effort"):
        group = result.add_mutually_exclusive_group()
        group.add_argument(f"--{key}", help=f"starting agent {key} (overrides per-agent config)")
        group.add_argument(
            f"--no-{key}", action="store_true",
            help=f"ignore the configured {key}; use native agent defaults",
        )
    result.add_argument(
        "--config", type=Path,
        help="TOML file (any filename; relative to caller's directory; bypasses discovery)",
    )
    result.add_argument(
        "-v", "--verbose", action="store_true",
        help="report the selected configuration file and effective settings on stderr",
    )
    result.add_argument("--image", help="sandbox OCI image")
    result.add_argument(
        "--keep",
        action="store_true",
        help="retain the sandbox after the agent exits (for debugging)",
    )
    result.add_argument("--host-share", type=Path, help="host directory mounted at /workspace")
    skills = result.add_mutually_exclusive_group()
    skills.add_argument("--skill", action="append", dest="skills", metavar="PATH",
                        help="skill or collection directory (repeatable; replaces configured skills)")
    skills.add_argument("--no-skills", action="store_true", help="ignore configured skill sources")
    result.add_argument(
        "--no-share", action="store_true",
        help="use a disposable /workspace without host project or kubeconfig mounts",
    )
    providers = result.add_mutually_exclusive_group()
    providers.add_argument("--provider", action="append", dest="providers", metavar="NAME")
    providers.add_argument("--no-providers", action="store_true")
    policy = result.add_mutually_exclusive_group()
    policy.add_argument(
        "--policy", type=Path,
        help="sandbox policy YAML file (required unless configured or --no-policy is supplied)",
    )
    policy.add_argument(
        "--no-policy", action="store_true",
        help="clear configured policy and let OpenShell select an environment, image, or default policy",
    )
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


def discover_config(explicit: Path | None, *, cwd: Path) -> Path | None:
    """Select one config, without inheriting settings from later candidates."""
    if explicit is not None:
        return _resolve_path(explicit, cwd)

    xdg_home = os.environ.get("XDG_CONFIG_HOME", "")
    user_directory = Path(xdg_home) if Path(xdg_home).is_absolute() else Path.home() / ".config"
    candidates = (
        cwd / ".exoshell.local.toml",
        user_directory / "exoshell" / "exoshell.local.toml",
        SYSTEM_CONFIG_FILE,
    )
    for candidate in candidates:
        try:
            # lstat also selects dangling symlinks so loading reports an error.
            candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise LauncherError(f"cannot inspect configuration {candidate}: {error}") from error
        return candidate
    return None


def load_config(path: Path, *, required: bool) -> dict[str, Any]:
    """Load and validate launcher settings from a TOML file."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as error:
        if required:
            raise LauncherError(f"configuration file does not exist: {path}") from error
        return {}
    except OSError as error:
        raise LauncherError(f"cannot inspect configuration {path}: {error}") from error
    if not stat.S_ISREG(mode):
        raise LauncherError(f"configuration path is not a file: {path}")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise LauncherError(f"cannot load configuration {path}: {error}") from error
    unknown = sorted(set(data) - CONFIG_KEYS)
    if unknown:
        raise LauncherError(f"unknown configuration key(s): {', '.join(unknown)}")

    for key, value in data.items():
        if key == "skills":
            if not isinstance(value, list) or any(type(item) is not str or not item.strip() for item in value):
                raise LauncherError("configuration key 'skills' must be an array of non-empty paths")
        elif key == "providers":
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
                unknown_agent_keys = sorted(set(agent_config) - {"providers", "model", "effort"})
                if unknown_agent_keys:
                    raise LauncherError(
                        f"unknown configuration key(s) for agents.{agent}: {', '.join(unknown_agent_keys)}"
                    )
                if "providers" in agent_config:
                    _provider_list(agent_config["providers"], f"agents.{agent}.providers")
                for setting in ("model", "effort"):
                    if setting in agent_config:
                        selected = agent_config[setting]
                        if type(selected) is not str or not selected.strip():
                            raise LauncherError(
                                f"configuration key 'agents.{agent}.{setting}' must be a non-empty string"
                            )
        elif key == "agent":
            if type(value) is not str or value not in AGENTS:
                raise LauncherError(f"configuration key 'agent' must be one of: {', '.join(AGENTS)}")
        elif type(value) is not str or not value:
            raise LauncherError(f"configuration key '{key}' must be a non-empty string")

    for key in PATH_KEYS & data.keys():
        data[key] = _resolve_path(data[key], path.parent)
    if "skills" in data:
        data["skills"] = [_resolve_path(item, path.parent) for item in data["skills"]]
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
    settings["no_share"] = args.no_share
    if args.no_share:
        for option, value in (
            ("--host-share", args.host_share), ("--kubeconfig", args.kubeconfig),
            ("a positional project", args.project),
        ):
            if value is not None:
                raise LauncherError(f"--no-share cannot be combined with {option}")
    if args.agent is not None:
        settings["agent"] = args.agent
    selected_agent = config.get("agents", {}).get(settings["agent"], {})
    for key in ("model", "effort"):
        value = getattr(args, key)
        if value is not None and not value.strip():
            raise LauncherError(f"--{key} cannot be empty")
        settings[key] = None if getattr(args, f"no_{key}") else (
            value if value is not None else selected_agent.get(key)
        )
    if args.image is not None:
        if not args.image:
            raise LauncherError("--image cannot be empty")
        settings["image"] = args.image
    if args.keep:
        settings["keep"] = True
    selected_skills = [] if args.no_skills else (
        args.skills if args.skills is not None else settings["skills"]
    )
    if any(not str(item).strip() for item in selected_skills):
        raise LauncherError("--skill cannot be empty")
    # Keep the final symlink's name: it may be a deliberate skill alias.
    settings["skills"] = [Path(os.path.abspath(_resolve_path(item, cwd))) for item in selected_skills]

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

    if args.no_share:
        settings.update(
            project=None, host_share=None, kubeconfig=None, container_project=CONTAINER_WORKSPACE,
        )
    else:
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
    if settings["policy"] is None and not args.no_policy:
        raise LauncherError(
            "no sandbox policy selected; use --policy PATH or set 'policy' in your TOML "
            "configuration, or explicitly use --no-policy to let OpenShell select its policy "
            "(which may come from the image rather than the restrictive default)"
        )
    return settings


def canonical_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise LauncherError(f"{label} does not exist: {path}") from error
    if not resolved.is_dir():
        raise LauncherError(f"{label} is not a directory: {resolved}")
    return resolved


def project_label(project: Path | None) -> str:
    """Normalize a project directory basename for an OpenShell label value."""
    if project is None:
        return "ephemeral"
    normalized = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-")
    return normalized[:63] or "project"


def select_skills(sources: Sequence[Path]) -> dict[str, Path]:
    """Select individual skills or immediate collection children, preserving aliases."""
    selected: dict[str, Path] = {}
    try:
        for source in sources:
            if not stat.S_ISDIR(source.stat().st_mode):
                raise LauncherError(f"skill source is not a directory: {source}")
            if (source / "SKILL.md").exists():
                candidates = [source]
            else:
                candidates = []
                for child in sorted(source.iterdir()):
                    if stat.S_ISDIR(child.stat().st_mode) and (child / "SKILL.md").exists():
                        candidates.append(child)
            for skill in candidates:
                if not (skill / "SKILL.md").is_file():
                    raise LauncherError(f"SKILL.md is not a regular file: {skill}")
                if not skill.name:
                    raise LauncherError(f"skill directory needs a name: {skill}")
                if skill.name in selected:
                    raise LauncherError(f"duplicate skill '{skill.name}': {selected[skill.name]} and {skill}")
                selected[skill.name] = skill
    except (OSError, RuntimeError) as error:
        raise LauncherError(f"cannot inspect skill sources: {error}") from error
    return selected


def copy_skill_snapshot(source: Path, destination: Path,
                        ancestors: frozenset[tuple[int, int]] = frozenset()) -> None:
    """Materialize links without following a directory cycle or copying special files."""
    try:
        metadata = source.stat()
        if stat.S_ISDIR(metadata.st_mode):
            identity = (metadata.st_dev, metadata.st_ino)
            if identity in ancestors:
                raise LauncherError(f"skill directory cycle: {source}")
            destination.mkdir(mode=0o700)
            for child in sorted(source.iterdir()):
                copy_skill_snapshot(child, destination / child.name, ancestors | {identity})
        elif stat.S_ISREG(metadata.st_mode):
            shutil.copyfile(source, destination)
            destination.chmod(0o600 | (metadata.st_mode & 0o111))
        else:
            raise LauncherError(f"unsupported special file in skill: {source}")
    except (OSError, RuntimeError) as error:
        raise LauncherError(f"cannot copy skill path {source}: {error}") from error


def mount_config(settings: dict[str, Any]) -> dict[str, Any]:
    """Build Podman mount configuration for the sandbox."""
    mounts: list[dict[str, Any]] = []
    if settings["host_share"] is not None:
        mounts.append(
            {
                "type": "bind",
                "source": str(settings["host_share"]),
                "target": CONTAINER_WORKSPACE,
                "read_only": False,
                "selinux_label": "shared",
            }
        )
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
    if settings.get("skills_snapshot") is not None:
        mounts.append({"type": "bind", "source": str(settings["skills_snapshot"]),
                       "target": CONTAINER_SKILLS_SNAPSHOT, "read_only": True,
                       "selinux_label": "shared"})
    # Provision storage even when GWS is attached after sandbox creation.
    mounts.append({"type": "tmpfs", "target": "/tmp/gws", "mode": 0o777})
    return {"podman": {"mounts": mounts}}


def git_identity(project: Path | None) -> tuple[str | None, str | None]:
    """Read required project identity, or optional global identity without a project."""
    command = ["git", "config", "--global"] if project is None else ["git", "-C", str(project), "config"]
    values: list[str] = []
    for key in ("user.name", "user.email"):
        try:
            result = subprocess.run(
                [*command, "--get", key],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            if project is None:
                if isinstance(error, FileNotFoundError) or error.returncode == 1:
                    return None, None
                raise LauncherError(f"cannot read global Git {key}") from error
            raise LauncherError(
                f"Git {key} is not configured for {project}; configure it locally or globally"
            ) from error
        value = result.stdout.rstrip("\n")
        if not value:
            if project is None:
                return None, None
            raise LauncherError(f"Git {key} is empty for {project}")
        values.append(value)
    return values[0], values[1]


def environment_args(settings: dict[str, Any], name: str | None, email: str | None) -> list[str]:
    environment = ["UV_CACHE_DIR=/tmp/uv-cache"]
    if settings.get("opencode_defaults") is not None:
        environment.append("EXOSHELL_OPENCODE_DEFAULTS=" + json.dumps(settings["opencode_defaults"]))
    git_config: list[tuple[str, str]] = []
    if name is not None and email is not None:
        environment.extend(
            [
                f"GIT_AUTHOR_NAME={name}",
                f"GIT_AUTHOR_EMAIL={email}",
                f"GIT_COMMITTER_NAME={name}",
                f"GIT_COMMITTER_EMAIL={email}",
            ]
        )
        git_config.extend([("user.name", name), ("user.email", email)])
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


def native_option(arguments: Sequence[str], *names: str) -> str | None:
    """Read native overrides before a literal --, including --name=value."""
    for index, argument in enumerate(arguments):
        if argument == "--":
            break
        for name in names:
            if argument == name:
                return arguments[index + 1] if index + 1 < len(arguments) else ""
            if argument.startswith(name + "="):
                return argument[len(name) + 1:]
            if len(name) == 2 and argument.startswith(name) and len(argument) > 2:
                return argument[2:]
    return None


def opencode_run_index(arguments: Sequence[str]) -> int | None:
    """Locate run after native global options, without treating option values as commands."""
    value_options = {
        "--model", "-m", "--agent", "--log-level", "--port", "--hostname",
        "--mdns-domain", "--cors", "--session", "-s", "--prompt", "--replay-limit",
    }
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            return None
        if argument in value_options:
            index += 2
            continue
        if not argument.startswith("-"):
            return index if argument == "run" else None
        index += 1
    return None


def agent_command(settings: dict[str, Any], arguments: Sequence[str]) -> tuple[list[str], dict[str, Any]]:
    """Translate launcher defaults without modifying forwarded arguments."""
    agent = settings["agent"]
    model, effort = settings.get("model"), settings.get("effort")
    defaults: list[str] = []
    environment_settings = dict(settings)
    model_options = ("--model",) if agent == "claude" else ("--model", "-m")
    native_model = native_option(arguments, *model_options)
    if agent == "codex":
        # Config overrides are repeatable and lower precedence than --model.
        if model is not None and native_model is None:
            defaults.extend(["--config", "model=" + json.dumps(model, ensure_ascii=False)])
        if effort is not None:
            defaults.extend(["--config", "model_reasoning_effort=" + json.dumps(effort, ensure_ascii=False)])
    elif agent == "claude":
        for key, value in (("model", model), ("effort", effort)):
            if value is not None and native_option(arguments, f"--{key}") is None:
                defaults.extend([f"--{key}", value])
    else:
        if model is not None and native_model is None:
            defaults.extend(["--model", model])
        # The run command supports --variant; the TUI uses agent configuration.
        run_index = opencode_run_index(arguments)
        if effort is not None:
            effective_model = native_model if native_model is not None else model
            if not effective_model:
                raise LauncherError(
                    "OpenCode effort requires an explicit model; set agents.opencode.model or use --model"
                )
            if run_index is not None:
                if native_option(arguments, "--variant") is None:
                    # Run-only options must follow the subcommand.
                    return [
                        "opencode", *defaults, *arguments[:run_index + 1],
                        "--variant", effort, *arguments[run_index + 1:],
                    ], environment_settings
            else:
                environment_settings["opencode_defaults"] = {"model": effective_model, "variant": effort}
    return [AGENTS[agent]["executable"], *defaults, *arguments], environment_settings


def create_command(
    settings: dict[str, Any], agent_args: Sequence[str], name: str | None, email: str | None,
) -> list[str]:
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
    selected_command, environment_settings = agent_command(settings, agent_args)
    command.extend(environment_args(environment_settings, name, email))
    if settings.get("skills_snapshot") is not None:
        command.extend(["--env", f"EXOSHELL_SKILLS_SNAPSHOT={CONTAINER_SKILLS_SNAPSHOT}"])
    command.append("--driver-config-json=" + json.dumps(mount_config(settings), separators=(",", ":")))
    command.append("--")
    if settings.get("skills_snapshot") is not None:
        # Older images must fail rather than silently starting without imports.
        command.extend(["/bin/sh", "-c",
                        'if [ ! -f /etc/exoshell/skills-import-v1 ]; then '
                        'echo "exoshell: image lacks skill import support; rebuild the sandbox image" >&2; '
                        'exit 2; fi; exec "$@"', "exoshell-skills"])
    command.extend(
        [
            "/usr/local/bin/exoshell-agent", settings["container_project"], "--",
            *selected_command,
        ]
    )
    return command


def is_local_image(image: str) -> bool:
    return image.startswith("localhost/")


def _verbose_value(key: str, value: Any) -> None:
    if isinstance(value, Path):
        value = str(value)
    elif isinstance(value, list):
        value = [str(item) if isinstance(item, Path) else item for item in value]
    print(f"exoshell: {key} = {json.dumps(value)}", file=sys.stderr, flush=True)


def run(argv: Sequence[str], *, cwd: Path) -> int:
    launcher_args, agent_args = split_agent_args(argv)
    args = parser().parse_args(launcher_args)
    config_path = discover_config(args.config, cwd=cwd)
    config = {}
    if config_path is not None:
        try:
            config_path = config_path.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise LauncherError(f"cannot resolve configuration {config_path}: {error}") from error
        if args.verbose:
            _verbose_value("config", config_path)
        config = load_config(config_path, required=True)
    elif args.verbose:
        _verbose_value("config", "built-in defaults")
    settings = resolve_settings(args, config, cwd=cwd)
    agent_command(settings, agent_args)  # Validate before image checks or provisioning.
    if args.verbose:
        for key in (
            "agent", "model", "effort", "image", "providers", "policy", "kubeconfig", "github_host",
            "gitlab_host", "keep", "no_share", "host_share", "project", "container_project", "skills",
        ):
            _verbose_value(key, settings[key])
    selected_skills = select_skills(settings["skills"])
    if not selected_skills:
        return launch(settings, agent_args)
    with tempfile.TemporaryDirectory(prefix="exoshell-skills-") as temporary:
        settings["skills_snapshot"] = Path(temporary)
        for skill_name, source in selected_skills.items():
            copy_skill_snapshot(source, Path(temporary) / skill_name)
        return launch(settings, agent_args)


def launch(settings: dict[str, Any], agent_args: Sequence[str]) -> int:
    """Check the image and launch while any skill snapshot remains alive."""
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
        return run(sys.argv[1:], cwd=Path.cwd())
    except LauncherError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

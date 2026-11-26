#!/usr/bin/env python3
"""Interactively replace stored OpenShell provider credentials."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import yaml

PROFILE_DIR = Path(__file__).resolve().parents[1] / "provider-profiles"


def list_providers() -> list[dict]:
    providers = []
    command = ["openshell", "provider", "list", "-o", "json"]
    next_page = command
    seen_tokens = set()
    while True:
        # The page token is an argument to the OpenShell provider list command.
        result = subprocess.run(  # noqa: S603
            next_page, check=True, stdout=subprocess.PIPE, text=True
        )
        page = json.loads(result.stdout)
        if (
            not isinstance(page, dict)
            or not isinstance(page.get("providers"), list)
            or not isinstance(page.get("next_page_token"), str)
        ):
            raise TypeError("unexpected response from OpenShell provider list")
        for provider in page["providers"]:
            if (
                not isinstance(provider, dict)
                or not all(
                    isinstance(provider.get(key), str) for key in ("name", "type")
                )
                or not isinstance(provider.get("credential_keys"), list)
                or not all(isinstance(key, str) for key in provider["credential_keys"])
            ):
                raise TypeError("unexpected provider entry from OpenShell")
            providers.append(provider)
        token = page["next_page_token"]
        if not token:
            return providers
        if token in seen_tokens:
            raise ValueError("repeated page token from OpenShell provider list")
        seen_tokens.add(token)
        next_page = [*command, "--page-token", token]


def stored_credentials(provider: dict, profile: dict) -> list[tuple[str, list[str]]]:
    stored_keys = set(provider["credential_keys"])
    credentials = []
    for credential in profile.get("credentials", []):
        name = credential["name"]
        aliases = credential.get("env_vars") or [name]
        keys = [key for key in aliases if key in stored_keys]
        if keys:
            credentials.append((credential.get("description") or name, keys))
    return credentials


def rotate(name: str, credentials: list[tuple[str, list[str]]]) -> bool:
    replacements = {}
    for description, keys in credentials:
        with warnings.catch_warnings():
            # getpass can otherwise fall back to reading with terminal echo on.
            warnings.simplefilter("error", getpass.GetPassWarning)
            value = getpass.getpass(f"{description} (Enter to skip): ")
        if value.strip():
            replacements.update(dict.fromkeys(keys, value))

    if not replacements:
        print("No replacements entered.")
        return True

    keys = ", ".join(replacements)
    if input(f"Save replacements for {name} ({keys})? [y/N] ").lower() not in {
        "y",
        "yes",
    }:
        print(f"Skipped {name}.")
        return True

    command = ["openshell", "provider", "update", name]
    for key in replacements:
        command.extend(("--credential", key))
    # Pass the provider and credential names as arguments to OpenShell.
    result = subprocess.run(  # noqa: S603
        command,
        env={**os.environ, **replacements},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        print(
            f"OpenShell update failed for {name} (exit {result.returncode}).",
            file=sys.stderr,
        )
        return False

    print(f"Saved credential replacements for {name}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="include providers outside the bundled ExOShell profiles",
    )
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print(
            "Run this helper from an interactive terminal on the gateway host.",
            file=sys.stderr,
        )
        return 1

    profiles = {}
    for path in sorted(PROFILE_DIR.glob("*.yaml")):
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        profiles[profile["id"]] = profile

    # OpenShell resolves the gateway and workspace from its active configuration.
    entries = []
    for provider in list_providers():
        profile_id = provider["type"]
        if profile_id in profiles:
            credentials = stored_credentials(provider, profiles[profile_id])
        elif args.all:
            credentials = [(key, [key]) for key in provider["credential_keys"]]
        else:
            continue
        entries.append((provider["name"], profile_id, credentials))
    if not entries:
        if args.all:
            print("No providers found in the active OpenShell workspace.")
        else:
            print("No provider instances match the bundled ExOShell profiles.")
        return 0

    heading = "Providers" if args.all else "ExOShell providers"
    status = 0
    while True:
        print(f"\n{heading} in the active OpenShell workspace")
        for index, (name, profile_id, credentials) in enumerate(entries, 1):
            label = str(index) if credentials else "-"
            suffix = ""
            if not credentials:
                suffix = (
                    " [no matching stored credentials]"
                    if profile_id in profiles
                    else " [no stored credentials]"
                )
            print(f"  {label:>2}  {name} ({profile_id}){suffix}")
        if not any(credentials for _, _, credentials in entries):
            return status

        choice = input("Select a provider (Enter to finish): ").strip()
        if not choice:
            return status
        for index, (name, _, credentials) in enumerate(entries, 1):
            if choice == str(index) and credentials:
                if not rotate(name, credentials):
                    status = 1
                break
        else:
            print("Choose a numbered provider.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nRotation interrupted.")
    except getpass.GetPassWarning:
        sys.exit(
            "Unable to disable terminal echo. Run this helper from an interactive terminal."
        )
    except subprocess.CalledProcessError as error:
        sys.exit(f"OpenShell provider list failed (exit {error.returncode}).")
    except FileNotFoundError as error:
        if error.filename == "openshell":
            sys.exit("OpenShell CLI not found. Run this helper on the gateway host.")
        raise
    except (TypeError, ValueError) as error:
        sys.exit(f"Rotation failed: {error}")

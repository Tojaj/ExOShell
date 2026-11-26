from __future__ import annotations

import json
import os
import pty
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rotate-provider-secrets.py"

FAKE_OPENSHELL = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open("commands.jsonl", "a", encoding="utf-8") as log:
    print(json.dumps(args), file=log)

github = dict(name="work-forge", type="exoshell-github-cli",
              credential_keys=["GH_TOKEN", "GITHUB_TOKEN"])
registry = dict(name="public-packages", type="exoshell-pypi-packages-ro",
                credential_keys=[])
workspace = dict(name="mail", type="exoshell-gws-cli",
                 credential_keys=["GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"])
other = dict(name="unbundled", type="custom",
             credential_keys=["CUSTOM_CLIENT_ID", "CUSTOM_TOKEN"],
             config_keys=["CUSTOM_ENDPOINT"])
public = dict(name="unbundled-public", type="custom", credential_keys=[])
if args == ["provider", "list", "-o", "json"]:
    print(json.dumps(dict(providers=[registry, other, public], next_page_token="more")))
elif args == ["provider", "list", "-o", "json", "--page-token", "more"]:
    print(json.dumps(dict(providers=[github, workspace], next_page_token="")))
elif args[:3] == ["provider", "update", "work-forge"]:
    assert os.environ["GH_TOKEN"] == os.environ["GITHUB_TOKEN"] == "fake=github token"
    print(os.environ["GH_TOKEN"])
    print(os.environ["GITHUB_TOKEN"], file=sys.stderr)
    sys.exit(int(os.environ.get("TEST_UPDATE_EXIT", "0")))
elif args[:3] == ["provider", "update", "mail"]:
    assert os.environ["GWS_REFRESH_TOKEN"] == "fake-refresh-token"
    assert not {"GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GH_TOKEN", "GITHUB_TOKEN"} & os.environ.keys()
elif args[:3] == ["provider", "update", "unbundled"]:
    assert os.environ["CUSTOM_TOKEN"] == "fake-custom-token"
    assert "CUSTOM_CLIENT_ID" not in os.environ
    print(os.environ["CUSTOM_TOKEN"])
else:
    sys.exit(99)
"""

MENU = "Select a provider (Enter to finish): "
GITHUB_PROMPT = "GitHub token (Enter to skip): "
GITHUB_CONFIRM = "Save replacements for work-forge (GITHUB_TOKEN, GH_TOKEN)? [y/N] "


class RotationTests(unittest.TestCase):
    def start(self, *args: str, update_exit: int = 0) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        cli = self.directory / "openshell"
        cli.write_text(FAKE_OPENSHELL, encoding="utf-8")
        cli.chmod(0o755)
        env = dict(os.environ, PATH=f"{self.directory}:{os.environ['PATH']}")
        env["TEST_UPDATE_EXIT"] = str(update_exit)
        for key in (
            "GWS_CLIENT_ID",
            "GWS_CLIENT_SECRET",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "CUSTOM_CLIENT_ID",
        ):
            env.pop(key, None)

        try:
            terminal, slave = pty.openpty()
        except OSError:
            # Restricted sandboxes can still exercise the workflow with a
            # simulated terminal. CI uses the real getpass prompt when available.
            command = [
                sys.executable,
                "-c",
                (
                    "import getpass\n"
                    "import runpy\n"
                    "import sys\n"
                    "sys.stdin.isatty = lambda: True\n"
                    "getpass.getpass = input\n"
                    "runpy.run_path(sys.argv.pop(1), run_name='__main__')"
                ),
                str(SCRIPT),
                *args,
            ]
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.directory,
                env=env,
            )
            self.addCleanup(self.process.stdin.close)
            self.addCleanup(self.process.stdout.close)
            self.read_fd = self.process.stdout.fileno()
            self.write_fd = self.process.stdin.fileno()
        else:
            self.addCleanup(os.close, terminal)
            try:
                self.process = subprocess.Popen(
                    [sys.executable, str(SCRIPT), *args],
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    cwd=self.directory,
                    env=env,
                    start_new_session=True,
                )
            finally:
                os.close(slave)
            self.read_fd = self.write_fd = terminal
        self.addCleanup(self.stop)
        self.transcript = bytearray()
        self.position = 0
        self.expect(MENU)

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)

    def expect(self, prompt: str) -> None:
        expected = prompt.encode()
        while (found := self.transcript.find(expected, self.position)) == -1:
            if not select.select([self.read_fd], [], [], 5)[0]:
                self.fail(f"Timed out waiting for {prompt!r} in {self.transcript!r}")
            output = os.read(self.read_fd, 4096)
            if not output:
                self.fail(f"Process exited before {prompt!r} in {self.transcript!r}")
            self.transcript.extend(output)
        self.position = found + len(expected)

    def send(self, value: str = "") -> None:
        os.write(self.write_fd, (value + "\n").encode())

    def commands(self) -> list[list[str]]:
        return [
            json.loads(line)
            for line in (self.directory / "commands.jsonl").read_text().splitlines()
        ]

    def enter_github_token(self) -> None:
        self.send("2")
        self.expect(GITHUB_PROMPT)
        self.send("fake=github token")
        self.expect(GITHUB_CONFIRM)

    def test_rotates_existing_aliases_and_a_single_workspace_credential(self) -> None:
        self.start()
        self.assertIn(
            b"public-packages (exoshell-pypi-packages-ro) [no matching stored credentials]",
            self.transcript,
        )
        self.assertNotIn(b"unbundled", self.transcript)
        self.send("1")
        self.expect("Choose a numbered provider.")
        self.expect(MENU)
        self.enter_github_token()
        self.send("y")
        self.expect("Saved credential replacements for work-forge.")
        self.expect(MENU)

        self.send("3")
        self.expect("Google OAuth client ID (Enter to skip): ")
        self.send()
        self.expect("Google OAuth client secret (Enter to skip): ")
        self.send()
        self.expect("Google OAuth refresh token (Enter to skip): ")
        self.send("fake-refresh-token")
        self.expect("Save replacements for mail (GWS_REFRESH_TOKEN)? [y/N] ")
        self.send("y")
        self.expect("Saved credential replacements for mail.")
        self.expect(MENU)
        self.send()

        self.assertEqual(self.process.wait(timeout=5), 0)
        self.assertNotIn(b"fake=github token", self.transcript)
        self.assertNotIn(b"fake-refresh-token", self.transcript)
        self.assertEqual(
            self.commands(),
            [
                ["provider", "list", "-o", "json"],
                ["provider", "list", "-o", "json", "--page-token", "more"],
                [
                    "provider",
                    "update",
                    "work-forge",
                    "--credential",
                    "GITHUB_TOKEN",
                    "--credential",
                    "GH_TOKEN",
                ],
                ["provider", "update", "mail", "--credential", "GWS_REFRESH_TOKEN"],
            ],
        )

    def test_all_rotates_a_stored_key_for_an_unbundled_provider(self) -> None:
        self.start("--all")
        self.assertIn(b"Providers in the active OpenShell workspace", self.transcript)
        self.assertIn(b"2  unbundled (custom)", self.transcript)
        self.assertIn(
            b"-  unbundled-public (custom) [no stored credentials]", self.transcript
        )
        self.send("3")
        self.expect("Choose a numbered provider.")
        self.expect(MENU)

        self.send("2")
        self.expect("CUSTOM_CLIENT_ID (Enter to skip): ")
        self.send()
        self.expect("CUSTOM_TOKEN (Enter to skip): ")
        self.send("fake-custom-token")
        self.expect("Save replacements for unbundled (CUSTOM_TOKEN)? [y/N] ")
        self.send("y")
        self.expect("Saved credential replacements for unbundled.")
        self.expect(MENU)

        self.send("4")
        self.expect(GITHUB_PROMPT)
        self.send()
        self.expect(MENU)
        self.send()

        self.assertEqual(self.process.wait(timeout=5), 0)
        self.assertNotIn(b"CUSTOM_ENDPOINT", self.transcript)
        self.assertNotIn(b"fake-custom-token", self.transcript)
        self.assertEqual(
            self.commands(),
            [
                ["provider", "list", "-o", "json"],
                ["provider", "list", "-o", "json", "--page-token", "more"],
                ["provider", "update", "unbundled", "--credential", "CUSTOM_TOKEN"],
            ],
        )

    def test_declining_and_interrupting_do_not_write(self) -> None:
        self.start()
        self.enter_github_token()
        self.send()
        self.expect("Skipped work-forge.")
        self.expect(MENU)
        self.enter_github_token()
        self.process.send_signal(signal.SIGINT)
        self.expect("Rotation interrupted.")
        self.assertEqual(self.process.wait(timeout=5), 1)
        self.assertEqual(len(self.commands()), 2)

    def test_failed_update_returns_to_menu_without_printing_secret(self) -> None:
        self.start(update_exit=7)
        self.enter_github_token()
        self.send("yes")
        self.expect("OpenShell update failed for work-forge (exit 7).")
        self.expect(MENU)
        self.send()
        self.assertEqual(self.process.wait(timeout=5), 1)
        self.assertNotIn(b"fake=github token", self.transcript)

    def test_requires_an_interactive_terminal(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("interactive terminal", result.stderr)


if __name__ == "__main__":
    unittest.main()

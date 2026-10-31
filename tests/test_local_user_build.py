from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "sandboxes/local-user/build.sh"


class LocalUserBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.capture = self.directory / "podman.json"
        self.id_calls = self.directory / "id.jsonl"
        self.environment = {
            **os.environ,
            "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
            "TEST_BUILD_CAPTURE": str(self.capture),
            "TEST_ID_CALLS": str(self.id_calls),
            "TEST_HOST_UID": "1234",
            "TEST_HOST_GID": "2345",
            # These are not supported build interfaces.
            "USER_UID": "3456",
            "USER_GID": "4567",
        }
        for name, body in (
            ("id", 'with open(os.environ["TEST_ID_CALLS"], "a") as f:\n'
                   '    f.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                   'print(os.environ[{"-u": "TEST_HOST_UID", "-g": "TEST_HOST_GID"}[sys.argv[1]]])\n'),
            ("podman", 'with open(os.environ["TEST_BUILD_CAPTURE"], "w") as f:\n'
                       '    json.dump(sys.argv[1:], f)\n'),
        ):
            executable = self.directory / name
            executable.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n" + body
            )
            executable.chmod(0o755)

    def run_build(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        self.capture.unlink(missing_ok=True)
        return subprocess.run(
            ["bash", str(BUILD), *arguments], cwd=self.directory,
            env=self.environment, capture_output=True, text=True,
        )

    def assert_build(self, arguments: list[str], uid: str, gid: str,
                     base: str = "localhost/exoshell-base:latest",
                     tag: str = "exoshell-local") -> None:
        result = self.run_build(arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.capture.read_text()), [
            "build", "--build-arg", f"BASE_IMAGE={base}",
            "--build-arg", f"USER_UID={uid}",
            "--build-arg", f"USER_GID={gid}",
            "--tag", tag, str(BUILD.parent),
        ])

    def test_defaults_use_host_identity_and_ignore_environment_ids(self) -> None:
        self.assert_build([], "1234", "2345")
        self.assertEqual(self.id_calls.read_text().splitlines(), ['["-u"]', '["-g"]'])

    def test_explicit_ids_and_existing_options_are_forwarded_as_arguments(self) -> None:
        base = "localhost/example:latest with spaces;$(literal)"
        tag = "example tag;$(literal)"
        self.assert_build(
            ["--gid", "1000", "--base-image", base, "--uid", "1000", "--tag", tag],
            "1000", "1000", base, tag,
        )
        self.assertFalse(self.id_calls.exists())

    def test_each_omitted_id_defaults_independently(self) -> None:
        for arguments, uid, gid, call in (
            (["--uid", "1000"], "1000", "2345", '["-g"]'),
            (["--gid", "1000"], "1234", "1000", '["-u"]'),
        ):
            with self.subTest(arguments=arguments):
                self.id_calls.unlink(missing_ok=True)
                self.assert_build(arguments, uid, gid)
                self.assertEqual(self.id_calls.read_text().splitlines(), [call])

    def test_valid_bounds_and_leading_zeros(self) -> None:
        for value, expected in (("1", "1"), ("4294967294", "4294967294"),
                                ("00001008", "1008"), ("0" * 100 + "1", "1")):
            with self.subTest(value=value):
                self.assert_build(["--uid", value, "--gid", value], expected, expected)

    def test_invalid_ids_fail_before_build(self) -> None:
        for option in ("--uid", "--gid"):
            for value in ("", "0", "000", "-1", "+1", "1.0", " 1", "1 ",
                          "1\n", "abc", "1000;true", "$(id)", "1+1", "１２", "١",
                          "4294967295", "4294967296", "18446744073709551616", "9" * 100):
                with self.subTest(option=option, value=value):
                    result = self.run_build([option, value])
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn(option, result.stderr)
                    self.assertIn("1 through 4294967294", result.stderr)
                    self.assertFalse(self.capture.exists())

    def test_missing_values_and_unknown_options_fail_before_build(self) -> None:
        for arguments in (["--uid"], ["--gid"], ["--uid", "--gid", "1000"],
                          ["--gid", "--tag", "example"], ["--base-image"],
                          ["--tag"], ["--unknown"], ["--uid=1000"]):
            with self.subTest(arguments=arguments):
                result = self.run_build(arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("error:", result.stderr)
                self.assertFalse(self.capture.exists())

    def test_invalid_default_ids_also_fail_before_build(self) -> None:
        for variable in ("TEST_HOST_UID", "TEST_HOST_GID"):
            for value in ("0", "4294967295", "-1", "invalid", ""):
                with self.subTest(variable=variable, value=value):
                    environment = self.environment.copy()
                    self.environment[variable] = value
                    result = self.run_build([])
                    self.environment = environment
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(self.capture.exists())

    def test_help_describes_identity_without_invoking_external_commands(self) -> None:
        for option in ("-h", "--help"):
            with self.subTest(option=option):
                result = self.run_build([option])
                self.assertEqual(result.returncode, 0, result.stderr)
                for text in ("--base-image IMAGE", "--tag TAG", "--uid UID", "--gid GID",
                             "id -u", "id -g", "4294967294"):
                    self.assertIn(text, result.stdout)
                self.assertFalse(self.capture.exists())
                self.assertFalse(self.id_calls.exists())

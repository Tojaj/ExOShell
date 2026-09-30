#!/usr/bin/env python3
"""Read-only release check for the version ARGs in exoshell-base/Dockerfile."""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = ROOT / "sandboxes/exoshell-base/Dockerfile"
CLAUDE_BASE = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"
NPM = {
    "GWS_VERSION": "@googleworkspace/cli",
    "CODEX_VERSION": "@openai/codex",
    "OPENCODE_VERSION": "opencode-ai",
    "AST_GREP_VERSION": "@ast-grep/cli",
}
GITHUB = {
    "UV_VERSION": ("astral-sh/uv", ("uv-x86_64-unknown-linux-gnu.tar.gz", "uv-aarch64-unknown-linux-gnu.tar.gz")),
    "ORAS_VERSION": ("oras-project/oras", ("oras_{v}_linux_amd64.tar.gz", "oras_{v}_linux_arm64.tar.gz")),
    "YQ_VERSION": ("mikefarah/yq", ("yq_linux_amd64", "yq_linux_arm64")),
    "TKN_VERSION": ("tektoncd/cli", ("tkn_{v}_Linux_x86_64.tar.gz", "tkn_{v}_Linux_aarch64.tar.gz")),
}
PINS = tuple(dict.fromkeys(("UV_VERSION", "GWS_VERSION", "CODEX_VERSION", "CLAUDE_VERSION", "OPENCODE_VERSION", "GLAB_VERSION", "OC_VERSION", "ORAS_VERSION", "YQ_VERSION", "TKN_VERSION", "PRE_COMMIT_VERSION", "AST_GREP_VERSION")))


class AssetError(LookupError):
    def __init__(self, message, candidate, date, source):
        super().__init__(message)
        self.candidate, self.date, self.source = candidate, date, source


def fetch(url, *, method="GET", json_data=True, headers=None):
    request_headers = {
        "User-Agent": "ExOShell-version-checker/1",
        "Accept": "application/json" if json_data else "text/plain",
    }
    request_headers.update(headers or {})
    request = urllib.request.Request(url, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if method == "HEAD":
                return True
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LookupError(f"{url}: {exc}") from exc
    if not json_data:
        return data.decode("utf-8").strip()
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise LookupError(f"{url}: invalid JSON: {exc}") from exc


def parse_pins(path=DOCKERFILE):
    found = dict(re.findall(r"^ARG ([A-Z_]+_VERSION)=([^\s#]+)", path.read_text(), re.M))
    missing = set(PINS) - found.keys()
    extra = {key for key in found if key.endswith("_VERSION")} - set(PINS)
    if missing or extra:
        raise ValueError(f"Dockerfile pin set changed; missing={sorted(missing)}, extra={sorted(extra)}")
    return {key: found[key] for key in PINS}


def version_key(value):
    value = re.sub(r"^(?:rust-)?v", "", value)
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        return None
    return tuple(map(int, value.split(".")))


def stable_versions(versions):
    return sorted({v for v in versions if version_key(v) is not None}, key=version_key, reverse=True)


def selected(versions, lag):
    ordered = stable_versions(versions)
    if len(ordered) <= lag:
        raise LookupError(f"only {len(ordered)} stable release(s) available; --lag {lag} requires {lag + 1}")
    return ordered[lag]


def require_names(actual, expected):
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise LookupError("missing Linux amd64/arm64 assets: " + ", ".join(missing))


def validate_assets(actual, expected, candidate, date, source):
    try:
        require_names(actual, expected)
    except LookupError as exc:
        raise AssetError(str(exc), candidate, date, source) from exc


def npm_release(pin, lag, get=fetch):
    package = NPM[pin]
    url = "https://registry.npmjs.org/" + urllib.parse.quote(package, safe="")
    data = get(url)
    versions = data["versions"]
    latest = data.get("dist-tags", {}).get("latest")
    if version_key(latest or "") is None:
        raise LookupError("npm latest dist-tag is unavailable or not a stable version")
    candidate = selected((v for v in versions if version_key(v) and version_key(v) <= version_key(latest)
                          and not versions[v].get("deprecated")), lag)
    entry = versions[candidate]
    date = data.get("time", {}).get(candidate)
    if not entry.get("dist", {}).get("tarball") or not entry.get("bin"):
        raise AssetError("npm package is missing tarball or executable metadata", candidate, date, url)
    optional = entry.get("optionalDependencies", {})
    required = {
        "CODEX_VERSION": ("@openai/codex-linux-x64", "@openai/codex-linux-arm64"),
        "OPENCODE_VERSION": ("opencode-linux-x64", "opencode-linux-arm64"),
        "AST_GREP_VERSION": ("@ast-grep/cli-linux-x64-gnu", "@ast-grep/cli-linux-arm64-gnu"),
    }.get(pin, ())
    validate_assets(optional, required, candidate, date, url)
    if pin == "OPENCODE_VERSION" and entry["bin"].get("opencode") != "bin/opencode.exe":
        raise AssetError("OpenCode executable layout changed; inspect the policy and image paths", candidate, date, url)
    return candidate, date, url


def github_release(pin, lag, get=fetch):
    repo, patterns = GITHUB[pin]
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    releases = get(url)
    stable = {re.sub(r"^(?:rust-)?v", "", item["tag_name"]): item for item in releases
              if not item.get("draft") and not item.get("prerelease") and version_key(item["tag_name"]) is not None}
    candidate = selected(stable, lag)
    release = stable[candidate]
    date, source = release.get("published_at"), release.get("html_url", url)
    validate_assets((a["name"] for a in release.get("assets", [])), (p.format(v=candidate) for p in patterns), candidate, date, source)
    if pin == "UV_VERSION":
        try:
            token_url = "https://ghcr.io/token?service=ghcr.io&scope=repository%3Aastral-sh%2Fuv%3Apull"
            token = get(token_url)["token"]
            image_url = f"https://ghcr.io/v2/astral-sh/uv/manifests/{candidate}"
            manifest = get(image_url, headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json",
            })
            platforms = {(item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
                         for item in manifest.get("manifests", [])}
            missing = {("linux", "amd64"), ("linux", "arm64")} - platforms
            if missing:
                raise LookupError(f"uv source image missing platforms: {sorted(missing)}")
        except (LookupError, KeyError, TypeError, urllib.error.URLError) as exc:
            raise AssetError(f"uv source image validation failed: {exc}", candidate, date, source) from exc
    return candidate, date, source


def claude_release(lag, get=fetch):
    if lag:
        raise LookupError("lagged native stable-channel releases are unavailable; use --lag 0")
    url = CLAUDE_BASE + "/stable"
    candidate = get(url, json_data=False).strip()
    if version_key(candidate) is None:
        raise LookupError(f"invalid Claude stable-channel version: {candidate!r}")
    manifest = get(f"{CLAUDE_BASE}/{candidate}/manifest.json")
    if manifest.get("version") != candidate:
        raise LookupError("Claude manifest version does not match stable channel")
    date = manifest.get("buildDate")
    validate_assets(manifest.get("platforms", {}), ("linux-x64", "linux-arm64"), candidate, date, url)
    return candidate, date, url


def glab_release(lag, get=fetch):
    url = "https://gitlab.com/api/v4/projects/34675721/releases?per_page=100"
    releases = get(url)
    stable = {item["tag_name"].removeprefix("v"): item for item in releases if version_key(item["tag_name"]) is not None}
    candidate = selected(stable, lag)
    release = stable[candidate]
    names = [a.get("name") for a in release.get("assets", {}).get("links", [])]
    date, source = release.get("released_at"), release.get("_links", {}).get("self", url)
    validate_assets(names, (f"glab_{candidate}_linux_amd64.tar.gz", f"glab_{candidate}_linux_arm64.tar.gz"), candidate, date, source)
    return candidate, date, source


def pypi_release(lag, get=fetch):
    url = "https://pypi.org/pypi/pre-commit/json"
    data = get(url)
    releases = {v: files for v, files in data["releases"].items() if files and any(not f.get("yanked") for f in files)}
    candidate = selected(releases, lag)
    files = [f for f in releases[candidate] if not f.get("yanked")]
    if not any(f.get("packagetype") in ("sdist", "bdist_wheel") for f in files):
        raise LookupError("PyPI release has no installable distribution")
    return candidate, min((f.get("upload_time_iso_8601") for f in files if f.get("upload_time_iso_8601")), default=None), url


def oc_release(pinned, lag, get=fetch):
    stream = ".".join(pinned.split(".")[:2])
    listing_url = "https://api.github.com/repos/openshift/cincinnati-graph-data/contents/channels"
    channels = get(listing_url)
    streams = sorted({int(m.group(1)) for item in channels if (m := re.fullmatch(r"stable-4\.(\d+)\.yaml", item.get("name", "")))}, reverse=True)
    if not streams:
        raise LookupError("no stable OpenShift channels found")
    url = f"https://raw.githubusercontent.com/openshift/cincinnati-graph-data/master/channels/stable-{stream}.yaml"
    text = get(url, json_data=False)
    versions = re.findall(r"^\s*-\s*(\d+\.\d+\.\d+)\s*$", text, re.M)
    candidate = selected((v for v in versions if v.startswith(stream + ".")), lag)
    # The channel is a release signal; the Dockerfile needs both mirror architectures.
    try:
        for arch in ("x86_64", "aarch64"):
            get(f"https://mirror.openshift.com/pub/openshift-v4/{arch}/clients/ocp/{candidate}/openshift-client-linux.tar.gz", method="HEAD", json_data=False)
    except (LookupError, urllib.error.URLError) as exc:
        raise AssetError(f"OpenShift client mirror validation failed: {exc}", candidate, None, url) from exc
    newer = [f"4.{minor}" for minor in streams if (4, minor) > tuple(map(int, stream.split(".")))]
    return candidate, None, url, newer


def check(pin, pinned, lag, get=fetch):
    if pin in NPM:
        source = "https://registry.npmjs.org/" + urllib.parse.quote(NPM[pin], safe="")
    elif pin in GITHUB:
        source = f"https://api.github.com/repos/{GITHUB[pin][0]}/releases?per_page=100"
    else:
        source = {"CLAUDE_VERSION": CLAUDE_BASE + "/stable", "GLAB_VERSION": "https://gitlab.com/api/v4/projects/34675721/releases?per_page=100", "OC_VERSION": "https://api.github.com/repos/openshift/cincinnati-graph-data/contents/channels", "PRE_COMMIT_VERSION": "https://pypi.org/pypi/pre-commit/json"}[pin]
    row = {"pin": pin, "pinned": pinned, "candidate": None, "date": None, "source": source, "status": "error", "note": None}
    try:
        if pin in NPM:
            candidate, date, source = npm_release(pin, lag, get)
        elif pin in GITHUB:
            candidate, date, source = github_release(pin, lag, get)
        elif pin == "CLAUDE_VERSION":
            candidate, date, source = claude_release(lag, get)
        elif pin == "GLAB_VERSION":
            candidate, date, source = glab_release(lag, get)
        elif pin == "PRE_COMMIT_VERSION":
            candidate, date, source = pypi_release(lag, get)
        elif pin == "OC_VERSION":
            candidate, date, source, newer = oc_release(pinned, lag, get)
            if newer:
                row["note"] = "newer streams: " + ", ".join(newer)
        row.update(candidate=candidate, date=date, source=source)
        if version_key(pinned) is None:
            raise LookupError("pinned version is not numeric semver")
        row["status"] = "upgrade" if version_key(candidate) > version_key(pinned) else ("current" if candidate == pinned else "ahead; no downgrade")
    except AssetError as exc:
        row.update(candidate=exc.candidate, date=exc.date, source=exc.source)
        row["note"] = str(exc)
    except (LookupError, KeyError, TypeError, ValueError, urllib.error.URLError) as exc:
        row["note"] = (row["note"] + "; " if row["note"] else "") + str(exc)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lag", type=int, choices=(0, 1, 2), default=0, help="stable releases behind newest (default: 0)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    args = parser.parse_args(argv)
    try:
        pins = parse_pins()
    except (OSError, ValueError) as exc:
        parser.exit(2, f"pin discovery failed: {exc}\n")
    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks = {pool.submit(check, pin, value, args.lag): pin for pin, value in pins.items()}
        results = {tasks[future]: future.result() for future in as_completed(tasks)}
    rows = [results[pin] for pin in PINS]
    if args.json:
        print(json.dumps({"lag": args.lag, "results": rows}, indent=2))
    else:
        print(f"ExOShell base versions (stable lag {args.lag})")
        print("PIN                 PINNED       CANDIDATE    RELEASE DATE         STATUS")
        for row in rows:
            print(f"{row['pin']:<19} {row['pinned']:<12} {(row['candidate'] or '—'):<12} {(row['date'] or '—')[:20]:<20} {row['status']}")
            print(f"  source: {row['source'] or 'lookup failed'}")
            if row["note"]:
                print(f"  note: {row['note']}")
    return 0 if all(row["status"] != "error" for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())

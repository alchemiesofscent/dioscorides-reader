"""Create the missing v<version> release tags after a deployment.

Every version with a CHANGELOG.md entry is tagged on the commit that first set
that version in pyproject.toml, so the tag marks the release itself rather than
whatever later commit happened to be deployed. Existing tags are never moved.
Run with --dry-run to see what would be tagged.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib

# Versions released before pyproject.toml carried them.
RETROSPECTIVE = {"0.1.0-alpha": "206064dc05a5c8f17c3d10d5aaf479965026aaf4"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def changelog_sections() -> dict[str, str]:
    text = open("CHANGELOG.md", encoding="utf-8").read()
    parts = re.split(r"^## (\S+) — \S+\n", text, flags=re.M)
    return {version: body.strip() for version, body in zip(parts[1::2], parts[2::2])}


def release_commits() -> dict[str, str]:
    commits: dict[str, str] = {}
    for commit in git("log", "--reverse", "--format=%H", "-G^version = ", "--", "pyproject.toml").split():
        version = tomllib.loads(git("show", f"{commit}:pyproject.toml"))["project"]["version"]
        commits.setdefault(version, commit)
    return {**RETROSPECTIVE, **commits}


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    existing = set(git("tag", "--list", "v*").split())
    commits = release_commits()
    created = []
    for version, body in changelog_sections().items():
        tag = f"v{version}"
        commit = commits.get(version)
        if commit is None:
            print(f"::warning::{tag}: no commit sets version {version} in pyproject.toml")
            continue
        if tag in existing:
            tagged = git("rev-list", "-n", "1", tag)
            if tagged != commit:
                print(f"::warning::{tag} points at {tagged[:12]}, expected {commit[:12]}; left as is")
            continue
        print(f"{tag} -> {commit[:12]}")
        if not dry_run:
            git("tag", "-a", tag, commit, "-m", f"Dioscorides reader {version}\n\n{body}")
            created.append(tag)
    if created:
        git("push", "origin", *created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Small repository entry point; no dependencies, model calls or implicit success."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("AGENTS.md", "README.md", "docs/current.md", "docs/product.md",
             "docs/engineering.md", "docs/donor.md", "docs/start.md")
REPOSITORY = "seoji2005/media-server"


class HarnessError(Exception):
    """Only fixed, intentionally safe messages may use this exception."""


def config() -> dict:
    value = json.loads((ROOT / "harness.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise HarnessError("unsupported harness configuration")
    if value.get("repository") != REPOSITORY:
        raise HarnessError("repository identity mismatch")
    commands = value.get("commands")
    if not isinstance(commands, dict) or set(commands) != {"test", "start"}:
        raise HarnessError("commands must declare test and start")
    for name, command in commands.items():
        if command is not None and (not isinstance(command, list) or not command or
                not all(isinstance(arg, str) and arg.strip() and "\0" not in arg for arg in command)):
            raise HarnessError(f"{name} must be null or a nonempty argument array")
    return value


def check(value: dict) -> int:
    for relative in DOCUMENTS:
        path = ROOT / relative
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise HarnessError(f"empty required document: {relative}")
        for target in re.findall(r"\]\(([^\s)]+)\)", content):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            resolved = (path.parent / unquote(url.path)).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.is_file():
                raise HarnessError(f"broken or escaping local link in {relative}")
    print("PASS: harness configuration and local documentation links")
    print("Evidence: contract only. No product test or model execution was performed.")
    return 0


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                            capture_output=True, check=True)
    return result.stdout.strip()


def status(value: dict) -> int:
    try:
        revision = git("rev-parse", "--verify", "HEAD")
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        dirty = bool(git("status", "--porcelain"))
        print(f"Configured repository: {REPOSITORY}\nRemote identity: NOT_VERIFIED\nHEAD: {revision}\nBranch: {branch}\nDirty: {dirty}")
    except (OSError, subprocess.CalledProcessError):
        print("GIT_UNAVAILABLE: not a committed checkout or Git is missing", file=sys.stderr)
        return 2
    for name, command in value["commands"].items():
        print(f"{name}: {'CONFIGURED' if command else 'NOT_CONFIGURED'}")
    print("Handoff: docs/current.md")
    return 0


def run(value: dict, name: str) -> int:
    command = value["commands"][name]
    if command is None:
        print(f"NOT_CONFIGURED: {name}; register a real command after implementation", file=sys.stderr)
        return 2
    if command[0] == "python":
        # Keep venv/Windows interpreter identity even without shell activation.
        command = [sys.executable, *command[1:]]
    try:
        # Argument arrays and shell=False avoid shell parsing. This is not a sandbox:
        # configured repository commands can execute arbitrary trusted project code.
        result = subprocess.run(command, cwd=ROOT, shell=False)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except FileNotFoundError:
        print(f"COMMAND_UNAVAILABLE: {name}", file=sys.stderr)
        return 127
    except OSError:
        print(f"COMMAND_FAILED_TO_START: {name}", file=sys.stderr)
        return 126


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    execute = sub.add_parser("run")
    execute.add_argument("command", choices=("test", "start"))
    args = parser.parse_args()
    try:
        value = config()
        if args.action == "check":
            return check(value)
        if args.action == "status":
            return status(value)
        return run(value, args.command)
    except HarnessError as exc:
        print(f"HARNESS_ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        # Third-party parser messages can contain private input. Never forward them.
        print("HARNESS_ERROR: required file missing, unreadable or malformed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

"""Installed and source-mode entry point for the optional managed Ollama service."""

from __future__ import annotations

import argparse
import subprocess
import sys

from recurgo.app import data_directory, project_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the optional local Ollama service")
    parser.add_argument("action", choices=("start", "pull", "status", "stop"))
    parser.add_argument("--use-proxy", action="store_true")
    args = parser.parse_args()

    root = project_root()
    script = root / "scripts" / "ollama_local.ps1"
    if not script.is_file():
        print(f"Ollama manager script is missing: {script}", flush=True)
        return 2

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Action",
        args.action.title(),
    ]
    if getattr(sys, "frozen", False):
        command.extend(("-DataRoot", str(data_directory())))
    if args.use_proxy:
        command.append("-UseProxy")
    try:
        return subprocess.run(command, cwd=root, check=False).returncode
    except OSError as exc:
        print(f"Could not run the Ollama manager: {exc}", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

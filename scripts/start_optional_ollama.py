"""Start the existing project-local Ollama service without a second layout."""

from __future__ import annotations

import subprocess

from recurgo.app import project_root


def main() -> int:
    root = project_root()
    executable = root / "runtime" / "ollama" / "v0.34.3" / "ollama.exe"
    if not executable.is_file():
        print(
            f"未找到 Ollama：{executable}\n"
            "请从 Ollama 官方下载 Windows 独立 ZIP，按《本机 Ollama 便携服务》说明解压。"
        )
        return 2
    try:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(root / "scripts" / "ollama_local.ps1"),
                "-Action",
                "Start",
            ],
            cwd=root,
            check=False,
        ).returncode
    except OSError as exc:
        print(f"Ollama 启动失败：{exc}", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

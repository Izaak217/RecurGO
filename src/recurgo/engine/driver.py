"""NVIDIA driver check used only by the standalone environment tool."""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from recurgo.i18n import Language, tr


def check_nvidia_driver(*, language: Language = "en") -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, tr(
            language,
            "当前独立检测工具只支持 Windows NVIDIA 环境。",
            "This standalone checker supports only Windows with NVIDIA CUDA.",
        )
    driver_path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "nvcuda.dll"
    try:
        driver = ctypes.WinDLL(str(driver_path))
    except OSError as exc:
        return (
            False,
            tr(
                language,
                "未找到可加载的 NVIDIA CUDA 显卡驱动接口 nvcuda.dll。"
                f"请先从 NVIDIA 官网安装适合本机显卡的驱动，再重启电脑。（{exc}）",
                f"Could not load NVIDIA CUDA driver interface nvcuda.dll. Install a suitable driver from NVIDIA and restart Windows. ({exc})",
            ),
        )
    result = driver.cuInit(0)
    if result != 0:
        return (
            False,
            tr(
                language,
                f"NVIDIA 驱动接口已找到，但无法初始化 CUDA（错误码 {result}）。"
                "请检查驱动和显卡状态。",
                f"NVIDIA driver interface found, but CUDA initialization failed (code {result}). Check the driver and GPU.",
            ),
        )
    count = ctypes.c_int()
    result = driver.cuDeviceGetCount(ctypes.byref(count))
    if result != 0 or count.value < 1:
        return (
            False,
            tr(
                language,
                f"NVIDIA 驱动接口已找到，但未检测到可用 CUDA 显卡（错误码 {result}）。",
                f"NVIDIA driver interface found, but no usable CUDA GPU was detected (code {result}).",
            ),
        )
    return True, tr(
        language,
        f"NVIDIA 驱动可用：检测到 {count.value} 块 CUDA 显卡。",
        f"NVIDIA driver available: detected {count.value} CUDA GPU(s).",
    )


def check_visual_cpp_runtime(*, language: Language = "en") -> tuple[bool, str]:
    """Check KataGo's direct MSVC imports in the system runtime location.

    This is an early diagnostic; a real KataGo analysis remains the final check.
    """

    if sys.platform != "win32":
        return False, tr(
            language,
            "Visual C++ 运行库检测只支持 Windows。",
            "The Visual C++ runtime check supports only Windows.",
        )
    system32 = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
    missing: list[str] = []
    for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        path = system32 / name
        if not path.is_file():
            missing.append(name)
            continue
        try:
            ctypes.WinDLL(str(path))
        except OSError:
            missing.append(name)
    if missing:
        names = ", ".join(missing)
        return False, tr(
            language,
            f"系统 Visual C++ 运行库不完整或无法加载（{names}）。请从微软官方安装 x64 版，然后重新检测。",
            f"The system Visual C++ runtime is incomplete or cannot be loaded ({names}). Install the official Microsoft x64 package, then check again.",
        )
    return True, tr(
        language,
        "已找到并可加载 KataGo 直接依赖的系统 Visual C++ 运行库；仍须通过实际分析确认兼容性。",
        "KataGo's directly required system Visual C++ libraries were found and loaded. A real analysis must still confirm compatibility.",
    )

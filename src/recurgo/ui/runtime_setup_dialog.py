"""Machine-specific CUDA and cuDNN location guidance."""

from __future__ import annotations

import os
from collections.abc import Mapping
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextOption
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from recurgo.engine import EngineRuntime
from recurgo.engine.driver import check_nvidia_driver, check_visual_cpp_runtime
from recurgo.i18n import Language, tr

from .i18n import localize_dialog_buttons

NVIDIA_DRIVER_URL = "https://www.nvidia.com/en-us/drivers/"
MSVC_URL = "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
CUDA_TOOLKIT_URL = "https://developer.nvidia.com/cuda-12-8-0-download-archive"
CUDA_RUNTIME_ZIP_URL = (
    "https://developer.download.nvidia.com/compute/cuda/redist/"
    "cuda_cudart/windows-x86_64/"
)
CUBLAS_ZIP_URL = (
    "https://developer.download.nvidia.com/compute/cuda/redist/"
    "libcublas/windows-x86_64/"
)
CUDNN_URL = "https://developer.nvidia.com/cudnn-9-8-0-download-archive"
CUDNN_ZIP_URL = (
    "https://developer.download.nvidia.com/compute/cudnn/redist/"
    "cudnn/windows-x86_64/"
)


def _link(url: str, label: str) -> str:
    return f'<a href="{url}">{escape(label)}</a>'


class RuntimeSetupDialog(QDialog):
    def __init__(
        self,
        paths: Mapping[str, object] | None,
        *,
        project_root: Path,
        dependencies_root: Path | None = None,
        check_system_msvc: bool = False,
        language: Language = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self._project_root = project_root
        self._dependencies_root = (
            dependencies_root
            if dependencies_root is not None
            else project_root / "runtime" / "cuda_deps"
        )
        self.setWindowTitle(self._tr("独立分析环境检测", "Analysis environment check"))
        self.resize(780, 560)
        layout = QVBoxLayout(self)
        introduction = QLabel(
            self._tr(
                "程序已提供 KataGo 引擎和模型。下面先查找 CUDA/cuDNN 文件；"
                "本版 KataGo 需要 cudnn64_9.dll（cuDNN 9.x）。"
                "自动搜索 NVIDIA 的 9.x 安装目录及配置路径；自定义位置可选择已有 DLL。"
                "未找到不代表尚未安装。点击“保存并检测”才会实际运行 KataGo。",
                "KataGo and its models are included. The search below checks for CUDA/cuDNN "
                "files. This KataGo build needs cudnn64_9.dll (cuDNN 9.x). Auto-search "
                "covers NVIDIA's 9.x installation folders and configured paths; choose an "
                "existing DLL for a custom location. A search miss does not prove the "
                "software is uninstalled. Save and check runs a real KataGo analysis.",
            )
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        driver_ready, driver_message = check_nvidia_driver(language=language)
        driver_detail = escape(driver_message)
        if not driver_ready:
            driver_detail += "<br>" + _link(
                NVIDIA_DRIVER_URL,
                self._tr("NVIDIA 官方驱动下载", "Official NVIDIA driver download"),
            )
        driver_label = QLabel(driver_detail)
        driver_label.setTextFormat(Qt.TextFormat.RichText)
        driver_label.setOpenExternalLinks(True)
        driver_label.setWordWrap(True)
        layout.addWidget(driver_label)

        if check_system_msvc:
            msvc_ready, msvc_message = check_visual_cpp_runtime(language=language)
            msvc_detail = escape(msvc_message)
            if not msvc_ready:
                msvc_detail += "<br>" + _link(
                    MSVC_URL,
                    self._tr(
                        "Microsoft Visual C++ x64 官方下载",
                        "Official Microsoft Visual C++ x64 download",
                    ),
                )
            msvc_label = QLabel(msvc_detail)
            msvc_label.setTextFormat(Qt.TextFormat.RichText)
            msvc_label.setOpenExternalLinks(True)
            msvc_label.setWordWrap(True)
            layout.addWidget(msvc_label)

        choices = QHBoxLayout()
        self.auto_radio = QRadioButton(
            self._tr("自动识别（推荐）", "Auto-detect (recommended)")
        )
        self.manual_radio = QRadioButton(self._tr("手动指定", "Choose manually"))
        choices.addWidget(self.auto_radio)
        choices.addWidget(self.manual_radio)
        choices.addStretch()
        layout.addLayout(choices)

        layout.addWidget(QLabel(self._tr("当前路径检查结果", "Current path check results")))
        self.auto_status_browser = QTextBrowser()
        self.auto_status_browser.setOpenExternalLinks(True)
        self.auto_status_browser.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        )
        self.auto_status_browser.setMinimumHeight(190)
        layout.addWidget(self.auto_status_browser, 1)
        values = paths or {}
        self.cuda_edit = QLineEdit(str(values.get("cudaBin") or ""))
        self.cudnn_edit = QLineEdit(str(values.get("cudnnBin") or ""))
        actions = QHBoxLayout()
        self.refresh_button = QPushButton(self._tr("重新识别", "Detect again"))
        self.refresh_button.clicked.connect(self._refresh_detection)
        actions.addWidget(self.refresh_button)
        open_folder = QPushButton(self._tr("打开 ZIP 放置目录", "Open ZIP destination"))
        open_folder.clicked.connect(self._open_dependencies_folder)
        actions.addWidget(open_folder)
        layout.addLayout(actions)

        self.locate_actions = QWidget()
        locate_layout = QHBoxLayout(self.locate_actions)
        locate_layout.setContentsMargins(0, 0, 0, 0)
        self.choose_cuda_button = QPushButton(
            self._tr("已安装 CUDA？选择 DLL…", "CUDA installed? Select its DLL…")
        )
        self.choose_cuda_button.clicked.connect(
            lambda: self._choose_existing_dll(self.cuda_edit, "cublas64_12.dll")
        )
        locate_layout.addWidget(self.choose_cuda_button)
        self.choose_cudnn_button = QPushButton(
            self._tr("已安装 cuDNN？选择 DLL…", "cuDNN installed? Select its DLL…")
        )
        self.choose_cudnn_button.clicked.connect(
            lambda: self._choose_existing_dll(self.cudnn_edit, "cudnn64_9.dll")
        )
        locate_layout.addWidget(self.choose_cudnn_button)
        layout.addWidget(self.locate_actions)

        form = QFormLayout()
        self.browse_buttons: list[QPushButton] = []
        for label, edit in (
            (self._tr("CUDA DLL 所在文件夹", "Folder containing CUDA DLLs"), self.cuda_edit),
            (self._tr("cuDNN DLL 所在文件夹", "Folder containing cuDNN DLL"), self.cudnn_edit),
        ):
            row = QHBoxLayout()
            row.addWidget(edit)
            browse = QPushButton(self._tr("浏览…", "Browse…"))
            browse.clicked.connect(lambda _checked=False, target=edit: self._browse(target))
            self.browse_buttons.append(browse)
            row.addWidget(browse)
            form.addRow(label, row)
            edit.editingFinished.connect(self._refresh_detection)
        layout.addLayout(form)

        self.status_label = QLabel(
            self._tr(
                "选择自动识别，或手动指定实际含 DLL 的文件夹。"
                "当前路径检查会随选择更新；点击“保存并检测”后会实际运行 KataGo。"
                "重启主程序后新路径才会生效。",
                "Use auto-detection or choose the folder containing the DLLs. The current "
                "path check updates with your selection. Save and check runs KataGo. "
                "New paths take effect after restarting the main application.",
            )
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, language)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._tr("保存并检测", "Save and check")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.auto_radio.toggled.connect(self._mode_changed)
        self.auto_radio.setChecked(not any(self._field_paths().values()))
        self.manual_radio.setChecked(not self.auto_radio.isChecked())
        self._mode_changed()

    def _tr(self, chinese: str, english: str) -> str:
        return tr(self.language, chinese, english)

    def _field_paths(self) -> dict[str, str]:
        return {
            "cudaBin": self.cuda_edit.text().strip(),
            "cudnnBin": self.cudnn_edit.text().strip(),
        }

    def _mode_changed(self) -> None:
        manual = self.manual_radio.isChecked()
        for widget in (self.cuda_edit, self.cudnn_edit, *self.browse_buttons):
            widget.setEnabled(manual)
        self.refresh_button.setText(
            self._tr("检查所选路径", "Check selected paths")
            if manual
            else self._tr("重新识别", "Detect again")
        )
        self._show_detection()
        if hasattr(self, "status_label"):
            self.status_label.setText(
                self._tr(
                    "当前结果已按所选模式更新。找到 DLL 后请点击“保存并检测”。",
                    "Results updated for the selected mode. Select Save and check "
                    "after locating the DLLs.",
                )
            )

    def _refresh_detection(self) -> None:
        self._show_detection()
        if self.choose_cuda_button.isVisible() or self.choose_cudnn_button.isVisible():
            self.status_label.setText(
                self._tr(
                    "当前路径检查已更新。点击上方对应按钮选择本机已有的 DLL；"
                    "随后点击“保存并检测”。",
                    "Current path check updated. Use the matching button above to select "
                    "an installed DLL, then select Save and check.",
                )
            )
        else:
            self.status_label.setText(
                self._tr(
                    "当前所选路径已找到所需 DLL。"
                    "点击“保存并检测”确认能否实际分析。",
                    "The current paths contain the required DLLs. "
                    "Select Save and check "
                    "to verify an actual analysis.",
                )
            )

    def _show_detection(self) -> None:
        manual_paths = self._field_paths() if self.manual_radio.isChecked() else {}
        try:
            runtime = EngineRuntime.load(
                self._project_root,
                path_overrides=manual_paths,
                local_dependencies_root=self._dependencies_root,
                validate=False,
            )
        except (OSError, KeyError, ValueError) as exc:
            self.choose_cuda_button.setVisible(True)
            self.choose_cudnn_button.setVisible(True)
            self.locate_actions.setVisible(True)
            self.auto_status_browser.setHtml(
                escape(
                    self._tr(f"当前路径检查暂不可用：{exc}", f"Path check unavailable: {exc}")
                )
            )
            return
        if not self.manual_radio.isChecked():
            self.cuda_edit.setText(
                str(runtime.cuda_bin)
                if all(
                    (runtime.cuda_bin / name).is_file()
                    for name in ("cublas64_12.dll", "cudart64_12.dll")
                )
                else ""
            )
            self.cudnn_edit.setText(
                str(runtime.cudnn_bin)
                if (runtime.cudnn_bin / "cudnn64_9.dll").is_file()
                else ""
            )
        reports: list[str] = []
        missing_components: set[str] = set()
        for label, key, directory, libraries in (
            ("CUDA", "cudaBin", runtime.cuda_bin, ("cublas64_12.dll", "cudart64_12.dll")),
            ("cuDNN", "cudnnBin", runtime.cudnn_bin, ("cudnn64_9.dll",)),
        ):
            missing = [name for name in libraries if not (directory / name).is_file()]
            manually_selected = bool(manual_paths.get(key))
            if missing:
                missing_components.add(label)
                if manually_selected:
                    reports.append(
                        "<p><b>"
                        + escape(label)
                        + self._tr(
                            "：所选文件夹未找到所需文件",
                            ": required files not found in selected folder",
                        )
                        + "</b><br>"
                        + self._tr("所选位置：", "Selected folder: ")
                        + escape(str(directory))
                        + "<br>"
                        + self._tr("未找到：", "Not found: ")
                        + escape(", ".join(missing))
                        + "<br>"
                        + self._tr(
                            "请选择实际包含这些 DLL 的文件夹；"
                            "当前结果只检查文件，不代表安装状态。",
                            "Choose the folder that actually contains these DLLs. This file "
                            "check does not determine installation status.",
                        )
                        + "</p>"
                    )
                    continue
                if label == "CUDA":
                    installer_download = _link(
                        CUDA_TOOLKIT_URL,
                        self._tr(
                            "NVIDIA CUDA Toolkit 12.8 下载页（EXE）",
                            "NVIDIA CUDA Toolkit 12.8 download page (EXE)",
                        ),
                    )
                    zip_downloads: list[str] = []
                    if "cudart64_12.dll" in missing:
                        zip_downloads.append(
                            _link(
                                CUDA_RUNTIME_ZIP_URL,
                                self._tr(
                                    "CUDA Runtime ZIP 列表（选 12.8）",
                                    "CUDA Runtime ZIP list (choose 12.8)",
                                ),
                            )
                        )
                    if "cublas64_12.dll" in missing:
                        zip_downloads.append(
                            _link(
                                CUBLAS_ZIP_URL,
                                self._tr(
                                    "cuBLAS ZIP 列表（选 12.8）",
                                    "cuBLAS ZIP list (choose 12.8)",
                                ),
                            )
                        )
                    destination = self._dependencies_root / "nvidia" / "cuda" / "bin"
                    installer_note = self._tr(
                        "运行下载的 EXE；安装时包含 CUDA Runtime 和 cuBLAS。"
                        "EXE 不放到下方目录。",
                        "Run the downloaded EXE with CUDA Runtime and cuBLAS selected. "
                        "Do not place the EXE in the directory below.",
                    )
                else:
                    installer_download = _link(
                        CUDNN_URL,
                        self._tr(
                            "NVIDIA cuDNN 9.8 下载页（选 EXE）",
                            "NVIDIA cuDNN 9.8 download page (choose EXE)",
                        ),
                    )
                    zip_downloads = [
                        _link(
                            CUDNN_ZIP_URL,
                            self._tr(
                                "cuDNN ZIP 列表（选 9.8、CUDA 12）",
                                "cuDNN ZIP list (choose 9.8, CUDA 12)",
                            ),
                        )
                    ]
                    destination = self._dependencies_root / "nvidia" / "cudnn" / "bin"
                    installer_note = self._tr(
                        "运行下载的 EXE，并选择 CUDA 12 组件。EXE 不放到下方目录。",
                        "Run the downloaded EXE and select the CUDA 12 component. "
                        "Do not place the EXE in the directory below.",
                    )
                reports.append(
                    "<p><b>"
                    + escape(label)
                    + self._tr(
                        "：自动搜索未找到所需文件",
                        ": required files not found by auto-search",
                    )
                    + "</b><br>"
                    + "<b>"
                    + self._tr("未找到：", "Not found: ")
                    + "</b>"
                    + escape(", ".join(missing))
                    + "<br>"
                    + self._tr(
                        "如果已经安装，请先选“手动指定”，指向实际含有上述 DLL 的文件夹；"
                        "无需重复下载或复制。cuDNN 的 DLL 也可能位于 bin 下"
                        "更深的版本与 x64 子目录。",
                        "If already installed, choose manually and select the folder "
                        "containing the DLLs. Do not download or copy them again. A cuDNN "
                        "installer may put DLLs below version and x64 folders under bin.",
                    )
                    + "<br>"
                    + "<b>"
                    + self._tr("仅在尚未安装时下载：", "Download only if not installed: ")
                    + "</b><br>"
                    + "<b>"
                    + self._tr(
                        "方法一：系统安装（EXE）：",
                        "Option 1: system installer (EXE): ",
                    )
                    + "</b>"
                    + installer_download
                    + self._tr("；", ". ")
                    + installer_note
                    + "<br>"
                    + "<b>"
                    + self._tr("方法二：独立 ZIP：", "Option 2: standalone ZIP: ")
                    + "</b>"
                    + " · ".join(zip_downloads)
                    + "<br>"
                    + "<b>"
                    + self._tr(
                        "ZIP 解压后，bin 内的 DLL 应放到：",
                        "For ZIP files, place the extracted bin DLLs in: ",
                    )
                    + "</b>"
                    + escape(str(destination))
                    + "<br>"
                    + self._tr(
                        "此目录只供 ZIP 解压文件使用；"
                        "系统 EXE 安装位置由 NVIDIA 安装程序决定。",
                        "This destination is only for extracted ZIP files. NVIDIA's EXE "
                        "installer chooses its own system location.",
                    )
                    + "</p>"
                )
            else:
                reports.append(
                    "<p><b>"
                    + escape(label)
                    + self._tr("：找到所需文件", ": required files found")
                    + "</b><br>"
                    + (
                        self._tr("手动选择位置：", "Selected folder: ")
                        if manually_selected
                        else self._tr("自动识别位置：", "Auto-detected folder: ")
                    )
                    + escape(str(directory))
                    + "<br>"
                    + self._tr(
                        "已找到文件，但尚未验证能否分析；请点击“保存并检测”。",
                        "Files found; analysis compatibility is not yet verified. "
                        "Select Save and check.",
                    )
                    + "</p>"
                )
        self.auto_status_browser.setHtml("".join(reports))
        self.choose_cuda_button.setVisible("CUDA" in missing_components)
        self.choose_cudnn_button.setVisible("cuDNN" in missing_components)
        self.locate_actions.setVisible(bool(missing_components))

    def _choose_existing_dll(self, edit: QLineEdit, filename: str) -> None:
        initial = edit.text().strip() or str(
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "NVIDIA"
        )
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self._tr(f"选择已有的 {filename}", f"Select installed {filename}"),
            initial,
            f"{filename} ({filename})",
        )
        if not selected:
            return
        if Path(selected).name.casefold() != filename.casefold():
            self.status_label.setText(
                self._tr(
                    f"请选择 {filename} 文件。",
                    f"Select the {filename} file.",
                )
            )
            return
        self.manual_radio.setChecked(True)
        edit.setText(str(Path(selected).parent))
        self._show_detection()
        if self.choose_cuda_button.isVisible() or self.choose_cudnn_button.isVisible():
            self.status_label.setText(
                self._tr(
                    "已更新所选路径；请先查看结果区仍未找到的文件。",
                    "Selected path updated. Check the result for files still not found.",
                )
            )
        else:
            self.status_label.setText(
                self._tr(
                    f"已选择 {selected}。点击“保存并检测”以实际运行 KataGo。",
                    f"Selected {selected}. Choose Save and check to run KataGo.",
                )
            )

    def _open_dependencies_folder(self) -> None:
        for directory in (
            self._dependencies_root / "nvidia" / "cuda" / "bin",
            self._dependencies_root / "nvidia" / "cudnn" / "bin",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dependencies_root)))

    def _browse(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("选择含 DLL 的文件夹", "Choose folder containing DLLs"), edit.text()
        )
        if folder:
            edit.setText(folder)
            self._refresh_detection()

    def paths(self) -> dict[str, str]:
        return (
            self._field_paths()
            if self.manual_radio.isChecked()
            else {
                "cudaBin": "",
                "cudnnBin": "",
            }
        )

    def accept(self) -> None:
        if self.auto_radio.isChecked():
            super().accept()
            return
        for label, value, libraries in (
            ("CUDA", self.cuda_edit.text().strip(), ("cublas64_12.dll", "cudart64_12.dll")),
            ("cuDNN", self.cudnn_edit.text().strip(), ("cudnn64_9.dll",)),
        ):
            resolved = Path(value)
            target = resolved if resolved.is_absolute() else self._project_root / resolved
            if value and not target.is_dir():
                self.status_label.setText(
                    self._tr(
                        f"{label} 文件夹不存在，请重新选择或留空自动查找。",
                        f"{label} folder does not exist. Choose another or leave it "
                        "blank for automatic detection.",
                    )
                )
                return
            missing = [name for name in libraries if value and not (target / name).is_file()]
            if missing:
                missing_text = ", ".join(missing)
                self.status_label.setText(
                    self._tr(
                        f"{label} 所选文件夹中未找到 {missing_text}；"
                        "请选择实际包含这些文件的目录，或留空自动查找。",
                        f"{label} selected folder does not contain {missing_text}. "
                        "Choose the folder containing these files or leave it blank "
                        "for auto-search.",
                    )
                )
                return
        super().accept()

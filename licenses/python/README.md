# Python 许可资料（v0.1.2）

本目录依据当前 `pyproject.toml` 和本地已安装包的 `METADATA` / `RECORD`，追踪 Windows / Python 3.13.3 环境下、未启用 extras 的运行时依赖闭包。本目录只归档许可资料，不包含依赖代码、二进制或本机运行数据；v1.0.0 Windows 安装包包含实际打包的解释器及依赖二进制。解释器与打包工具的许可单独列出，不将它们混入应用运行时 pip 依赖。

原始 LICENSE、NOTICE、COPYING、版权和色图 legal code 文件保持原始字节，原文中的作者、年份、版权、联系方式和第三方条款均未删改。每份副本均与本地来源或官方源包成员进行 SHA-256 核对；完整来源相对路径、上游链接、依赖关系和哈希见 [inventory.json](inventory.json)。运行时包的上游代码链接来自已安装元数据；sgfmill 原文来自官方版本匹配源包。

| 包 | 安装版本 | 已安装元数据声明 / 原文提示 | 归档状态 |
|---|---|---|---|
| annotated-types | 0.8.0 | MIT | 已复制 1 份原文 |
| colorama | 0.4.6 | License :: OSI Approved :: BSD License | 已复制 1 份原文 |
| numpy | 2.5.1 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0；wheel 内含 OpenBLAS、LAPACK、GCC runtime 等声明和例外 | 已复制 20 份原文 |
| opencv-python-headless | 5.0.0.93 | Apache 2.0 | 已复制 4 份原文 |
| platformdirs | 4.10.1 | MIT | 已复制 1 份原文 |
| pydantic | 2.13.4 | MIT | 已复制 1 份原文 |
| pydantic_core | 2.46.4 | MIT | 已复制 1 份原文 |
| pyqtgraph | 0.14.0 | MIT；色图附 CC-BY 4.0 和 CC0 原文 | 已复制 3 份原文 |
| sgfmill | 1.1.1 | MIT | 已复制 1 份原文（来自官方 1.1.1 源包） |
| typing_extensions | 4.16.0 | PSF-2.0 | 已复制 1 份原文 |
| typing-inspection | 0.4.4 | MIT | 已复制 1 份原文 |

- `colorama` 是 `pyqtgraph` 的运行时依赖，因此已纳入；一般 dev extra 与构建工具未纳入运行时清单。
- Qt、PySide6、PySide6 Essentials/Addons 和 Shiboken6 由单独的 Qt 许可资料目录处理，不在本目录重复归档。
- NumPy 顶层 LICENSE 包含该 Windows wheel 的 OpenBLAS、LAPACK、GCC runtime 等随附软件条款；子目录同时保留随机数、FFT、SIMD 等组件原文。不能仅用顶层元数据的简短许可表达式代替这些内容。
- OpenCV 同时保留 dist-info 与 `cv2` 内的 LICENSE 和 LICENSE-3RD-PARTY 原文，重复文件也按原始位置保留。
- pyqtgraph 的色图另含 Creative Commons Attribution 4.0 和 CC0 原文；保留这些文件不代表已对将来的二进制发行完成全部署名与源码提供义务核查。
- `sgfmill 1.1.1` 本地 wheel 未附许可文件，已从[官方 1.1.1 源包](https://mjw.woodcraft.me.uk/sgfmill/download/sgfmill-1.1.1.tar.gz)补齐 [doc/licence.rst](sgfmill-1.1.1/doc/licence.rst)，完整保留 Matthew Woodcraft 的原始版权、MIT 条款及 Contributors。源包位于 `licenses/sources/sgfmill-1.1.1.tar.gz`，源包与成员的哈希均已记录。

## 解释器与打包工具

| 组件 | 角色 | 归档原文 | 对应源码 |
|---|---|---|---|
| CPython 3.13.3 | 当前解释器；不是 pip 运行时依赖 | [LICENSE.txt](cpython-3.13.3/LICENSE.txt)，含历史与第三方条款 | [官方 v3.13.3 源码](https://github.com/python/cpython/tree/v3.13.3) |
| PyInstaller 6.21.0 | v1.0.0 构建使用的 build-only 工具及随 EXE 分发的 bootloader | [COPYING.txt](pyinstaller-6.21.0/COPYING.txt)，含原始版权、GPL、bootloader exception、run-time hooks 等完整条款 | [官方源码](https://github.com/pyinstaller/pyinstaller) |

v1.0.0 Windows 安装包收录 CPython 运行组件、PyInstaller bootloader 和可执行程序；其许可原文与第三方材料按实际文件清单保留在本目录。

## 使用边界

本目录已为清单内 11 个非 Qt 运行时依赖保存许可原文。它记录的是当前 wheel 已随附的材料及明确记录的 sgfmill 源包补充，不证明上游 wheel 已完整列出所有内部组件的义务。更换依赖版本、操作系统、wheel 构建或打包方式时，应重新检查依赖闭包和原文。

后续如更换 Python/Qt/原生库版本或打包方式，应依据新包的实际文件重新核对第三方声明、署名、源码提供及其他发行义务。

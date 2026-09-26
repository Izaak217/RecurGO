# Qt / PySide6 许可与对应源码说明

文档版本：v0.1.7；更新日期：2026-09-25。

v1.0.0 Windows 安装包按实际打包文件审查。构建脚本排除未使用的 Qt Virtual
Keyboard、Qt PDF、Qt FFmpeg 媒体插件和 OpenCV 视频插件。当前程序使用 Qt 的
`QAudioSink` 输出合成音效，并用 OpenCV 处理静态图片；这些插件不是上述功能的输入。
保留的 Qt、PySide6 共享库及 Python 依赖自带的 MSVC 运行库仍需按实际文件提供许可
说明和对应源码入口。实际文件以本轮安装包清单为准。
以下 v0.1.2 段落是此前源码环境审计记录，不能代替本次安装包的文件清单。

本目录补齐当前开发环境的 Qt / PySide6 许可资料。[具体插件声明](third_party/README.md)保存已对照文件的原文；[上游归属资料](upstream/README.md)与 [索引](upstream/index.json)保存 Qt 6.11.1 五个相关源码模块的原始声明及许可文本。上游源码元数据可能包含未编入 Windows wheel 或已被打包规则排除的组件，不等于实际随包二进制清单；实际清单以安装包的 `file-manifest.json` 为准。

## 当前核实范围

- 当前依赖为 PySide6、PySide6_Essentials、PySide6_Addons 和 Shiboken6 **6.11.1**。其安装元数据列有 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` 许可选项。本项目对适用组件采用 **LGPLv3 路径**，不是宣称取得了 Qt 商业许可。
- 本项目生产源码直接导入 `QtCore`、`QtGui`、`QtWidgets`、`QtMultimedia` 和 `QtNetwork`；测试另用 `QtTest`。这只是直接导入清单，不是最终依赖或发行清单。Qt6Core.dll、Qt6Multimedia.dll 与 Qt6Network.dll 的本机文件版本均为 **6.11.1.0**。
- Qt / PySide6 的版权属于 The Qt Company 及相关原作者。具体版权年份、作者与第三方声明应保留相应源码和发行文件中的原文；本项目自身许可不取代这些声明。

v0.1.2 的本机 Ollama 客户端新增直接使用 `QtNetwork`，通过 `QNetworkAccessManager`、`QNetworkRequest`、`QNetworkReply` 和 `QNetworkProxy` 完成异步本机 HTTP 请求。它复用现有 PySide6 安装，没有新增 Python HTTP SDK；v1.0.0 安装包收录 QtNetwork、网络信息插件及 TLS 插件。当前功能使用本机明文 HTTP，不代表打包工具没有带入 TLS 插件或其他网络组件。

Qt 6.11.1 的 [QNetworkAccessManager 源文件](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/network/access/qnetworkaccessmanager.cpp)声明商业许可、LGPLv3、GPLv2 或 GPLv3 路径。此处继续采用适用组件的 LGPLv3 路径；第三方代码和实际插件另按其原始条款核对，不能只凭模块名称认定全部依赖同许可。

## 本目录文件及来源

| 文件 | 内容与来源 |
| --- | --- |
| [LGPL-3.0-only.txt](LGPL-3.0-only.txt) | LGPLv3 完整原文，从 Qt 官方 `qtbase` 仓库 `v6.11.1` 标签的 [原文件](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/LICENSES/LGPL-3.0-only.txt) 原样保存。 |
| [GPL-3.0-only.txt](GPL-3.0-only.txt) | LGPLv3 所引用的 GPLv3 完整原文，从同一版本的 [原文件](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/LICENSES/GPL-3.0-only.txt) 原样保存。附带此文本不表示本项目全部代码都改为 GPL。 |
| [LicenseRef-Qt-Commercial.txt](LicenseRef-Qt-Commercial.txt) | 从本地 `pyside6-6.11.1.dist-info/licenses/` 原样复制；Essentials、Addons 和 Shiboken6 安装包附带的同名文本具有相同 SHA-256。保留它用于说明上游另有商业许可选项；该文件不是商业许可证或购买凭证。 |

原文 SHA-256（用于检查本目录文件是否被意外改写）：

```text
da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768  LGPL-3.0-only.txt
8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903  GPL-3.0-only.txt
4f54763ac0fe2abd8f7f8d8fe370a94a08ebf84786aa0b91045bd6628deb08a3  LicenseRef-Qt-Commercial.txt
```

## 固定版本的上游源码入口

以下链接已在官方目录中核实，固定为 **6.11.1**，不是 `latest`。本地审查目录已下载并核对 PySide6 与当前随包 Qt 模块的七份固定版本源码归档；这些归档不进入安装包或 Git 仓库。源码版本匹配不能证明已经重建或复核全部 wheel 的构建输入。

| 范围 | 官方对应版本源码 |
| --- | --- |
| PySide6 与 Shiboken6 | [pyside-setup-everywhere-src-6.11.1.tar.xz](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/pyside-setup-everywhere-src-6.11.1.tar.xz)，[官方目录](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/)。 |
| Qt 6.11.1 的模块源码 | [qt-everywhere-src-6.11.1.tar.xz](https://download.qt.io/archive/qt/6.11/6.11.1/single/qt-everywhere-src-6.11.1.tar.xz)，[官方目录](https://download.qt.io/archive/qt/6.11/6.11.1/single/)。 |
| 单独取得 Qt 模块 | [Qt 6.11.1 官方子模块源码目录](https://download.qt.io/archive/qt/6.11/6.11.1/submodules/)，包含 Qt Base、Qt Multimedia 等固定版本归档。 |

最终二进制发行时，必须以实际随包的 Qt、PySide6、Shiboken6、插件及第三方库版本和构建方式核对对应源码。版本一致是核对依据之一，不能取代补丁、构建脚本、配置和第三方代码的核对。若修改库，应同时保留修改记录并提供相应修改源码及必要构建资料。

## LGPL 路径下的二进制分发要求

v1.0.0 安装包采用以下 LGPL 分发安排；每次更换 Qt 或 PySide6 版本时须重新核对：

1. 随包保留 LGPLv3、其引用的 GPLv3、所分发组件的版权与第三方许可声明，并显著说明程序使用 Qt / PySide6 及其 LGPL 许可。安装前提示已给出此说明；如果程序运行时展示版权信息，也须在该界面加入库的版权说明。
2. 安装包保留独立的 Qt / PySide6 共享库。安装后关闭程序，在安装目录的 `_internal/PySide6/` 下找到 `Qt6*.dll` 及相应的 `plugins/`；备份原文件后，可将需要修改的库替换为架构和接口兼容的版本，再启动程序。替换文件及兼容性由操作者自行管理，重新安装或升级会覆盖安装目录；不得通过许可条款或技术措施禁止修改 LGPL 库及为调试这类修改而进行的逆向工程。
3. 分发库的二进制时，为用户提供完整、机器可读的对应源码获取途径。网络发布可采用 GPLv3 第 6(d) 条方式：在二进制下载位置旁提供清楚的、无需额外费用的等效源码访问说明。源码可以位于第三方服务器，但分发者仍负责其持续可获取性；不能只写上游首页或不确定版本的下载地址。
4. 构建生成的 `file-manifest.json` 记录本版实际文件、大小和 SHA-256；本目录与上游索引记录固定版本、原始许可及官方源码入口。若官方对应源码失效，应提供仍可取得的等效来源；不能以不确定版本的上游首页代替。

以上是本项目分发安排的说明，详细权利义务以随附的许可原文为准。LGPL 第 4 条同时有其他允许的组合和重新链接方式；本项目当前计划使用其共享库路径。

## 不直接发布整个开发环境

当前 `.venv` 安装了完整 PySide6 Addons，还包含本项目未直接使用的 `Qt6Quick3D.dll`、`Qt6VirtualKeyboard.dll` 等文件。Qt 官方将这些模块列在 GPLv3 开源许可范围；不能因 PySide6 总包元数据存在 LGPL 选项，就把全部模块一概按 LGPL 分发。

发行包应根据实际依赖收集必要模块，不直接复制整个 `.venv`。如果最终确需分发额外模块，逐项遵守其实际许可。仅把独立组件放在同一分发介质中，不等于自动给全部自有代码改换许可证。

dev16 候选曾收录 `avcodec-61.dll`、`avformat-61.dll` 等 PySide6 FFmpeg 文件、
OpenCV 的 FFmpeg 视频插件，以及 Qt PDF 插件。dev17 构建规则已排除这些未使用的
组件；v1.0.0 文件清单已确认这些二进制未进入安装包。FFmpeg 7.1.3 的
[官方源码归档](https://ffmpeg.org/releases/ffmpeg-7.1.3.tar.xz)已下载到本地
`build/` 审查目录，未放进源码仓库；如果未来重新分发 FFmpeg，需按实际二进制
提供对应源码、许可原文和构建信息。[FFmpeg 官方分发清单](https://ffmpeg.org/legal.html)
说明了其推荐做法。

## 官方依据

- [Qt Licensing](https://doc.qt.io/qt-6/licensing.html)：Qt 的许可选项、部分 GPLv3 模块与第三方代码说明。
- [Qt Multimedia：Licenses and attributions](https://doc.qt.io/qt-6/qtmultimedia-index.html#licenses-and-attributions)：Multimedia 的许可选项与第三方代码说明。此滚动文档当前显示 6.11.2；用于理解许可结构，不作为本机 6.11.1 全部第三方版本清单。
- [Qt Network：Licenses and attributions](https://doc.qt.io/qt-6/qtnetwork-index.html#licenses-and-attributions)：Network 的许可选项与第三方代码说明；当前滚动文档显示 6.11.2，固定版本依据仍以本文列出的 6.11.1 源码为准。
- [Licenses Used in Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html)：PySide 的第三方许可说明。
- [LGPLv3 原文](LGPL-3.0-only.txt)第 4 条与 [GPLv3 原文](GPL-3.0-only.txt)第 6 条：共享库、组合程序和对应源码分发要求。

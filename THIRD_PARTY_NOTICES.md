# 第三方组件与许可

[English](THIRD_PARTY_NOTICES.en.md) | 简体中文

本项目自有代码采用根目录 [MIT License](LICENSE)。第三方组件保持各自原始许可，
不能将整个运行目录视为 MIT。以下是源码仓库及 v1.0.0 Windows 安装包的许可索引；
实际随包文件由构建时的 `file-manifest.json` 记录。更换依赖或重新打包时须重新核对。

| 组件 | 当前范围 | 资料 |
| --- | --- | --- |
| KataGo 1.16.5 | 安装包含 CUDA 引擎；MIT 及上游另列第三方条款 | [引擎与附属组件](licenses/katago/README.md)、[来源与校验](licenses/katago/sources.json) |
| KataGo 官方主模型、Human SL | 安装包含两个模型；官方网络许可，保留版权与许可 | [当前模型与适用范围](licenses/models/README.md)、[网络许可原文](licenses/models/KataGo-Neural-Network-License.txt) |
| Python 依赖、解释器和打包运行组件 | 各自原始条款；含 wheel 内部第三方材料 | [Python 许可清单](licenses/python/README.md) |
| PySide6、Shiboken6、Qt 6.11.1 | 对适用模块采用 LGPLv3 路径；随包第三方材料集中收录 | [Qt 许可及对应源码说明](licenses/qt/README.md)、[已识别插件声明](licenses/qt/third_party/README.md)、[上游原始归属资料](licenses/qt/upstream/README.md) |
| NVIDIA cuDNN / CUDA | 专有协议，根目录 MIT 不替代它们 | [版本、原始协议与差异说明](licenses/nvidia/README.md) |
| Ollama 0.34.3 | 本机外部推理服务，未作为 Python 依赖打包 | [MIT License](https://github.com/ollama/ollama/blob/v0.34.3/LICENSE)、[本机运行说明](docs/OLLAMA_LOCAL.md) |
| Qwen3 4B Instruct 2507 | 本机选择的语言模型；模型许可独立于 Ollama | [官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)、[所选 tag 许可](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) |

OpenSSL、zlib、libzip 等随 KataGo 引擎分发的组件仍按各自许可处理；引擎目录不打包
本机的 Microsoft Visual C++ DLL，安装版要求系统提供运行库。Python/Qt/NumPy 的
上游二进制包另含 Visual C++ 运行库文件；其来源和
[微软再分发条款](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
见发布审查说明。Qt/PySide6 的许可、固定版本源码和共享库替换方式见上述资料。
v1.0.0 安装包排除程序未使用的 Qt PDF、Qt FFmpeg 和 OpenCV 视频插件。下载后的 Ollama、模型、缓存、密钥和个人棋谱不属于项目自有源码，
也不进入安装包。

Ollama 程序的 MIT 许可不代表所有可选模型采用 MIT。用户改选模型后，应查阅该模型
自身的许可；今后若将外部组件并入发行包，须按实际版本同时附带相应材料。

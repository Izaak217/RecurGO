# 本机 Ollama 便携服务（RecurGO v1.0.0）

[English](OLLAMA_LOCAL.en.md) | 简体中文

安装包用户请优先看[Windows 安装说明](INSTALL_WINDOWS.md)的可选 Ollama 部分：程序入口位于
开始菜单，Ollama 程序和模型放在 `%LOCALAPPDATA%\RecurGO\ollama`。以下项目相对路径和
`run_recurgo_with_ollama.cmd` 步骤主要适用于源码运行。

本脚本管理项目内的独立 Ollama CLI 服务。客户端与界面已接入，已通过模拟服务的自动化
回归。官方程序已校验并启动，本机 API 版本为 0.34.3；所选模型已经核对 SHA256 并成功导入。
本机 API 单句生成已验证，但完整棋局讲解的耗时、输出质量和与 KataGo 共用显存的情况
由用户自行测试，尚未验收。

## 界面使用

准备好程序和模型后，双击 `run_recurgo_with_ollama.cmd`。在工具栏的“本机 AI 解释设置”
中启用本机解释，检测并选择模型，保存设置；窗口较窄时，也可从
“菜单 → 分析 → 本机 AI 解释设置”进入。设置默认关闭，保存在本机数据库中。
程序默认英语；如需简体中文，可在“Preferences → Language / 语言”中选择并点击确定，立即生效。
新请求会使用所选语言的系统提示词及规则证据。模型能否稳定遵循语言要求，仍需以实际
生成结果确认。
如果主程序已经打开，只需启动 Ollama 服务，可单独双击 `start_optional_ollama.cmd`；
它调用同一套 `scripts/ollama_local.ps1`，仍使用下方列出的固定目录和隔离设置。

KataGo 数据到达后，规则解释立即更新；完整搜索结果稳定后自动请求语言模型，逐段显示补充
解释，无需每手点击生成。切换候选、局面或棋局会取消旧请求，防止回答串到其它手。
“取消”会停止本次补充；需要时可“重新生成”。公平对战不显示分析解释。

新的 KataGo 搜索和全盘复盘优先，语言模型请求会取消或等待。每次生成结束请求卸载模型，
以减少常驻显存；因此不能预先承诺下一次请求没有加载耗时。即时规则解释始终不等待 Ollama。

连接仅接受本机 HTTP 地址，并根据模型名称和本机服务返回的元数据拒绝可识别的云模型。
这不能证明不受信任的本机服务或第三方模型不会自行转发请求；只连接自己信任的 Ollama
服务，并使用来源已核对的本地模型。提示词只包含棋盘、候选、参考变化和规则证据，
不加入棋手名字、棋谱注释或本机路径。语言模型补充可能表述不准确，不能据此改变 KataGo
的排序或认定死活、征子、必然结果。

## 文件与数据位置

- 可执行文件：`runtime/ollama/v0.34.3/ollama.exe`，由核验后的官方 Windows AMD64 CLI ZIP 解压获得。
- 模型：`runtime/ollama/models/`。
- 密钥和用户配置：`runtime/ollama/profile/.ollama/`；应用数据位于该隔离 profile 的 `AppData/`。
- 临时文件、日志和 CUDA 缓存：`runtime/ollama/tmp/`、`logs/`、`cuda-cache/`。
- 服务记录：`runtime/ollama/service.json`，保存 PID、进程启动时间、程序路径和网络模式。

这些目录包含本机数据和第三方运行资源，不应加入源码提交或开源发布包。脚本拒绝通过项目内的目录联接或符号链接写到其它位置。

每次启动子进程均临时设置 `USERPROFILE`、`LOCALAPPDATA`、`APPDATA`、`TEMP`、`TMP`、`TMPDIR`、`CUDA_CACHE_PATH` 和 `OLLAMA_MODELS`，操作结束后恢复调用进程原环境。不修改 `HOME`、`CODEX_HOME` 或系统/用户持久环境，不安装系统服务或开机启动项。

## 使用

在项目目录用 Windows PowerShell 5.1 或 PowerShell 7 执行：

```powershell
.\scripts\ollama_local.ps1 -Action Status
.\scripts\ollama_local.ps1 -Action Start
.\scripts\ollama_local.ps1 -Action Pull
.\scripts\ollama_local.ps1 -Action Stop
```

`Start` 在后台启动 `ollama serve`，只监听 `127.0.0.1:11434`。stdout/stderr 各写入一个带时间戳和随机标识的新日志文件。服务不会因为启动脚本结束而主动停止，需要时执行 `Stop`。`Status` 只读状态，不创建运行目录。

`Stop` 在结束服务及其子进程前核对 PID、实际可执行文件路径和进程启动时间，避免误停用户另外安装的 Ollama。端口已被其它进程占用时，`Start` 报告冲突，不抢占端口、不结束该进程。PID 记录会更新，已有记录、模型和日志不删除。

默认模型为 `qwen3:4b-instruct-2507-q4_K_M`，可通过 `-Model` 指定其它已确定的完整 tag。`Pull` 使用已启动的本项目服务；进度来自 Ollama 自带 CLI，脚本不能从外部统一观测其全部下载字节流。

## 直连和显式代理

默认服务和 CLI 使用直连：清空该子进程的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`，并设置 `NO_PROXY=*`。本机 API 检测始终绕过代理。

只有直连失败、无法连接或速度异常慢时，才在当前 PowerShell 进程已有正确 `HTTP_PROXY` 或 `HTTPS_PROXY` 的前提下显式切换：

```powershell
.\scripts\ollama_local.ps1 -Action Stop
.\scripts\ollama_local.ps1 -Action Start -UseProxy
.\scripts\ollama_local.ps1 -Action Pull -UseProxy
```

模型下载由 `serve` 进程执行。因此只给 `Pull` 添加代理开关不能改变已启动服务的网络环境；脚本会检查两者模式一致，不自动重启服务。代理地址不写入状态文件。代理模式的 `NO_PROXY` 仍包括 `127.0.0.1`、`localhost` 和 `::1`。恢复直连时执行 `Stop`，再执行不带 `-UseProxy` 的 `Start`。

## 模型、接口与验证边界

推荐 tag 已在官方 registry 确认存在，模型及附属层约 2.326 GB，采用 Q4_K_M 量化，许可 Apache-2.0。`qwen3:4b-instruct-2507` 本身不是存在的 tag；裸 `qwen3:4b` 当前指向 Thinking 模型，不用于此默认配置。

- Manifest SHA256：`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
- Model blob SHA256：`85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`。
- [Ollama 模型 tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M)。
- [Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)：此变体仅支持非思考模式。

服务设置 `OLLAMA_NO_CLOUD=1`、`OLLAMA_NOHISTORY=1`、`OLLAMA_DEBUG_LOG_REQUESTS=false`，并限制同时加载模型数与并行请求数均为 1。模型下载仍需联网；禁用云功能不等于禁用模型下载。`OLLAMA_NOPRUNE=1` 禁止启动时自动修剪模型 blob。

下载完成后用 `scripts/probe_ollama.py` 检查真实 KataGo → 自动本机解释调用链，报告保存在
新的 `data/verification/ollama-*` 目录，不使用个人对局数据库。首字和完成耗时从客户端发起
请求开始计算，包括模型检查与生成，不包括 KataGo 搜索和界面等待；规则计算耗时也不是
完整界面延迟。只有 API 成功、界面收到完整内容且核对输入事实，才报告本机生成已验收。

下载大小不是运行显存占用；不得通过减少 KataGo 搜索预算、换弱分析模型或改变一选规则
来给语言模型腾资源。

该脚本重定向已核实的应用数据和 CUDA JIT 缓存路径，环境变量隔离不等同文件系统沙箱；不能据此声称 Windows/显卡驱动绝无额外系统记录。

## 上游依据

- [Ollama v0.34.3](https://github.com/ollama/ollama/releases/tag/v0.34.3)，[Windows CLI 说明](https://docs.ollama.com/windows)。
- 官方 ZIP SHA256：`306ce9e81e3491d147f558e60d7a389499f244d10f71859c6e4e899241d1b4ae`；[校验文件](https://github.com/ollama/ollama/releases/download/v0.34.3/sha256sum.txt)。
- [serve 密钥初始化](https://github.com/ollama/ollama/blob/v0.34.3/cmd/cmd.go#L2101)、[模型与环境配置](https://github.com/ollama/ollama/blob/v0.34.3/envconfig/config.go#L111)、[服务日志初始化](https://github.com/ollama/ollama/blob/v0.34.3/server/routes.go#L1969)。
- [聊天 API](https://docs.ollama.com/api/chat)、[CUDA 缓存环境变量](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html)。

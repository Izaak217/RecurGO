# 从源码启动（v1.0.1）

[English](SOURCE_SETUP.en.md) | 简体中文

配置完成后的日常操作见[用户使用说明](USER_GUIDE.md)。

目前可复现的开发路径是 **Windows x64 + Python 3.13 + KataGo CUDA 12.8 后端**。
这不是所有硬件的兼容性承诺。OpenCL、CPU 自动选择、首次安装向导和独立便携包仍待实现。

## Python 环境

在解压或克隆后的项目目录执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

此处使用 editable 安装，让程序按源码目录查找 `runtime/` 和 `data/`。
依赖版本记录在 `pyproject.toml`。`.venv/` 在本机重新生成，不随 Git 上传。

## 准备 KataGo

从 [KataGo v1.16.5 官方发行页](https://github.com/lightvector/KataGo/releases/tag/v1.16.5)
取得匹配的 Windows CUDA 12.8 引擎，保留该包要求的运行库与许可。
当前配置另需 CUDA 12.8 运行库和 cuDNN 9.x（本项目已验证 9.8；其他 9.x 以真实分析检测为准）。NVIDIA 显卡驱动需在 Windows 安装；
项目级运行库可按下方固定目录准备，不从其它电脑复制系统目录。
主程序不做独立环境预检。需要配置 CUDA/cuDNN 路径并实际验证 KataGo 时，
单独运行项目根目录的 `check_analysis_environment.cmd`。

从 [KataGo 官方网络目录](https://katagotraining.org/networks/) 取得主模型，
从 [额外网络目录](https://katagotraining.org/extra_networks/) 取得 Human SL：

- `kata1-b28c512nbt-s13255194368-d5935380940.bin.gz`
- `b18c384nbt-humanv0.bin.gz`

上述文件及核对过的 SHA256 见 [模型资料](../licenses/models/README.md)。
当前运行时加载器仍要求这两个文件，即使只使用“最强”难度也不能省略 Human SL。

建议目录：

```text
runtime/
  engine/katago.exe             # 同目录保留引擎依赖的 DLL
  models/                      # 上述两个模型
  configs/analysis.cfg
  runtime.local.json
  cuda_deps/nvidia/cuda/bin/    # CUDA 12.8 运行库 DLL
  cuda_deps/nvidia/cudnn/bin/   # cuDNN 9.8 运行库 DLL
  ollama/v0.34.3/ollama.exe     # 可选，从官方 CLI ZIP 解压
data/logs/katago/
```

新安装可复制 `docs/setup/runtime.example.json` 为 `runtime/runtime.local.json`，
复制 `docs/setup/analysis.example.cfg` 为 `runtime/configs/analysis.cfg`。
先创建目录；已有配置应自行比较，避免覆盖。

CUDA 固定目录需要放入匹配 12.8 的 `cublas64_12.dll`、`cudart64_12.dll` 等运行库；
可从 NVIDIA 官方 [CUDA Runtime ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/)
与 [cuBLAS ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/)
取得对应版本，解压后把 ZIP 内 `bin` 的 DLL 放入上面的 CUDA `bin` 目录。
cuDNN 可从 [NVIDIA 官方页面](https://developer.nvidia.com/cudnn-archive)取得适用于 CUDA 12 的
Windows 9.8 ZIP，解压后把 `bin` 内的 DLL 放入上面的 cuDNN `bin` 目录。
这里放的是**解压后的运行库**，不是下载好的安装器 EXE 或未解压的 ZIP。也可照官方说明
正常安装 CUDA Toolkit；独立工具同样会自动找系统安装位置。

双击 `check_analysis_environment.cmd`，选“自动识别”并点击“保存并检测”。工具先检查
Windows 中的 NVIDIA 驱动，再找固定目录、已有清单、系统安装位置和 `PATH`，最后实际
运行 KataGo。若自动识别不到，切换“手动指定”选择实际包含所需 DLL 的文件夹。手动路径保存在
本机 `data/` 的独立配置文件，主程序只读取；保存后重启主程序才会生效。

实时分析和全盘复盘的访问量在顶部“分析设置”中调整；窗口较窄时，也可从
“菜单 → 分析 → 分析设置”进入。默认 800 visits；
直接修改配置文件中的 `maxVisits` 不会覆盖界面发出的访问量。

示例分析参数来自已经使用的单 NVIDIA GPU 基线，只把日志位置改为相对路径，
不声称这些参数适合所有电脑或代表通用“最强”配置。应用按原有策略设置搜索预算。
若显存不足或后端不匹配，记录错误并调整安装方案，不以减少搜索质量作为兼容性修复。

启动前创建 `data/logs/katago/`，并从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\probe_qt_engine.py
.\.venv\Scripts\python.exe -m recurgo.app
```

可双击 `check_analysis_environment.cmd` 配置路径并做一次独立分析测试；
测试通过后无需每次打开主程序都运行。若更换显卡驱动、CUDA/cuDNN 或模型，可再次运行。

引擎未配置成功时，主程序会显示启动错误；棋盘和棋谱功能仍可打开，不能因此视为
AI 分析已经可用。独立诊断工具会列出缺失项，进行真实分析并产生本地日志。

## 可选本机语言模型

规则棋理解释不需要 Ollama。语言模型用于补充表达，不能改变 KataGo 的落点排序。
Ollama 和语言模型单独准备，见 [本机 AI 说明](OLLAMA_LOCAL.md)。

## 数据与发布边界

默认棋谱、分析缓存和设置在 `data/`。设置 `RECURGO_DATA_DIR` 可指定其它数据位置；
若改到项目内的其它目录，应同步加入忽略规则。导出的 SGF 也可能包含棋手名字和注释。

完整 `runtime/`、`data/`、`.venv/` 均由 `.gitignore` 排除。发布源码时保留本说明、示例配置、
`LICENSE`、`THIRD_PARTY_NOTICES.md` 和 `licenses/`。这些规则不控制手工复制或整目录压缩。

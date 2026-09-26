# RecurGO Windows 安装指南（v1.0.0）

[English](INSTALL_WINDOWS.en.md) | 简体中文

本文只说明安装、依赖配置和首次启动。下棋、分析、棋谱和偏好设置请看[用户说明书](USER_GUIDE.md)。从源码运行的开发者请看[源码启动说明](SOURCE_SETUP.md)。

## 安装流程速览

1. 安装 RecurGO，按需选择安装位置和桌面快捷方式。
2. 从开始菜单打开 **Analysis Environment Check / 检测分析环境**。
3. 按检测结果补齐 NVIDIA 驱动、CUDA、cuDNN 或 Visual C++ 运行库；已有组件先让工具识别，无需直接重装。
4. 点击 **保存并检测**，确认 KataGo 完成真实局面分析，再启动 RecurGO。程序操作见[用户说明书](USER_GUIDE.md)。

## 下载前先看

RecurGO v1.0.0 面向 Windows 10/11 x64 和 NVIDIA 显卡。没有 NVIDIA 显卡的电脑暂不支持；其他 NVIDIA 显卡也须通过下文的独立工具确认能否实际分析。

目前 KataGo 实际分析已在 NVIDIA GeForce RTX 5070 Ti Laptop GPU 和
NVIDIA GeForce RTX 2080 Ti 上通过；后者的主程序也已显示候选点和胜率。
这是两张显卡的测试结果，不代表所有 NVIDIA 显卡均可运行。

随包的 KataGo 要加载 `cudnn64_9.dll`，因此本版要求 **cuDNN 9.x**；其他主版本不能代替。自动识别会检查 NVIDIA 标准位置下的 `v9.*` 安装目录及其子文件夹，也检查 `CUDNN_PATH` 和 `PATH`。若安装在别处且没有设置这些路径，可在检测工具中选择实际 DLL 文件，不必重装。多个 9.x 共存时，以工具显示的选中路径和真实 KataGo 检测结果为准。

安装包包含 RecurGO、KataGo 引擎、分析模型以及程序运行所需组件。你不必自行安装 Python、寻找 KataGo 模型或修改引擎配置。以下组件需要单独准备：

| 组件 | 放在哪里 | 是否必须 |
| --- | --- | --- |
| NVIDIA 显卡驱动 | 安装在 Windows 中；多数 NVIDIA 电脑已有 | 必须 |
| CUDA 12.8 运行库、兼容的 cuDNN 9.x | 使用 NVIDIA 官方 Windows 安装程序安装到系统，或从官方 ZIP 解压到检测工具显示的用户数据目录 | 必须有可用版本；cuDNN 9.8 已验证，9.25.1 在 RTX 2080 Ti 上手动指定后实际分析通过，其他组合以本机检测结果为准 |
| Microsoft Visual C++ Redistributable x64 | 安装在 Windows 中；已有兼容版本则无须重复安装 | KataGo 启动需要 |
| Ollama 和语言模型 | 可选，建议放在下文的用户数据目录 | 仅使用本机 AI 补充讲解时需要 |

没有 Ollama，棋盘、KataGo 分析、胜率、候选点、复盘和程序自带的即时棋理说明仍可使用。

## 第一步：安装 RecurGO

在项目的 GitHub **Releases** 页面下载标有 **Windows x64** 的安装程序。安装时会显示程序安装目录选择页，可选择有写入权限的其他位置；默认目录为当前用户的 `%LOCALAPPDATA%\Programs\RecurGO`，不需要 Python。个人棋谱、配置和下载的运行资源仍保存在 `%LOCALAPPDATA%\RecurGO`，不会随程序安装目录移动。

从同一 Release 下载 `SHA256SUMS.txt` 后，可在安装程序所在目录打开 PowerShell，运行
`Get-FileHash -Algorithm SHA256 -LiteralPath "实际安装程序文件名.exe"`。将输出的哈希与
`SHA256SUMS.txt` 中对应文件的哈希逐字核对；不一致时不要运行该文件。只从项目的
GitHub Release 页面获取安装程序和校验文件，不使用他人转发的修改版。

安装向导的“附加任务”页可勾选 **创建桌面快捷方式**，默认不勾选。勾选后，桌面上的 RecurGO 快捷方式使用项目角色图标；不勾选仍可从开始菜单启动程序。

若系统没有兼容的 Visual C++ 运行库，请从[微软官方页面](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)安装 **x64** 版。安装包的 KataGo 引擎目录不单独复制开发机上的 Microsoft 运行库 DLL；检测工具会检查系统运行库。

页面上的 **Source code (zip)** 和 **Source code (tar.gz)** 是 GitHub 自动生成的源码压缩包，供查看代码或自行开发；它们不是可以双击安装的程序。普通用户应下载 Releases 中单独提供的 Windows 安装程序。

## 第二步：检查显卡驱动

从开始菜单打开 **Analysis Environment Check / 检测分析环境**，或运行安装目录中的 `check_analysis_environment.cmd`。该入口会打开检测配置窗口，显示能否找到并初始化 NVIDIA 显卡驱动。`RecurGO-Environment-Check.exe` 是供启动脚本调用的命令行程序，直接双击它不是日常检测入口。

- 显示驱动正常：继续下一步，不需要重装驱动。
- 显示驱动不可用：到 [NVIDIA 官方驱动页面](https://www.nvidia.com/en-us/drivers/)按自己的显卡型号安装；如果安装程序要求重启，重启后再打开检测工具。
- 没有 NVIDIA 显卡的电脑：暂不支持。

NVIDIA 显卡驱动安装在 Windows 系统中，无须放入 RecurGO 的安装目录。主程序里没有驱动或 CUDA 设置页；相关操作只在这个独立工具中进行。

## 第三步：准备 CUDA 和 cuDNN

有两种方式，选一种即可。**从 CUDA Toolkit 下载页得到 EXE 是正常的**：运行安装程序即可；下方的固定目录只用于独立 ZIP 方式，不能把 EXE 放进去。

1. **系统安装**：从 NVIDIA 官方 [CUDA Toolkit 12.8 下载页](https://developer.nvidia.com/cuda-12-8-0-download-archive)和 [cuDNN 9.8 下载页](https://developer.nvidia.com/cudnn-9-8-0-download-archive)选择 Windows x64 安装程序，安装与本项目匹配的 CUDA 12.8 和 cuDNN 9.8（cuDNN 选择 CUDA 12 对应组件）。cuDNN 安装程序不能代替 CUDA 运行库和 cuBLAS。安装完成后重新打开检测工具。工具会查找 NVIDIA 的版本目录、`bin` 下的 CUDA 版本与架构子目录、相关环境变量和 `PATH`。如果自动识别不到，并不能据此断定系统未安装；选择 **“手动指定”**，分别指向实际包含 `cublas64_12.dll` 与 `cudart64_12.dll` 的 CUDA 文件夹，以及实际包含 `cudnn64_9.dll` 的 cuDNN 文件夹。后者可能比 `bin` 更深，例如 `bin\12.9\x64`。
2. **独立 ZIP**：在“检测分析环境”工具中点击 **“打开 ZIP 放置目录”**。它会建立并打开放置运行库的文件夹。工具窗口也会显示两个目标文件夹的完整路径；请以窗口显示的路径为准。相对 `%LOCALAPPDATA%\RecurGO` 用户数据目录的结构如下：

    ```text
    cuda_deps\nvidia\cuda\bin\    放 CUDA 12.8 运行库的 DLL
    cuda_deps\nvidia\cudnn\bin\   放 cuDNN 9.8 的 DLL
    ```

ZIP 方式需要：

1. 从 NVIDIA 官方 [CUDA Runtime ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/)下载 **Windows x86_64、12.8** 的压缩包；再从 [cuBLAS ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/)下载对应的 **Windows x86_64、12.8** 压缩包。分别解压，把这两个压缩包中 bin 文件夹里的 DLL 放进上面的 cuda\bin。
2. 从 [NVIDIA cuDNN 9.8 官方页面](https://developer.nvidia.com/cudnn-9-8-0-download-archive)下载 **cuDNN 9.8、CUDA 12、Windows x86_64** 的 ZIP。解压，把其中 bin 文件夹里的 DLL 放进上面的 cudnn\bin。

使用 ZIP 方式时，要放的是解压后的 DLL，不是还没解压的 ZIP；使用官方安装程序时，不必再把 DLL 复制到固定目录。不用从其他电脑的系统目录复制 DLL。路径识别和 DLL 文件检查仍不是最终兼容性证明，请点击 **“保存并检测”**，以实际启动 KataGo 并取得分析结果为准。

项目已验证 cuDNN 9.8；在 NVIDIA GeForce RTX 2080 Ti 的测试机器上，手动指定 cuDNN 9.25.1 后，实际 KataGo 分析也已通过。NVIDIA 的 [cuDNN 9.25.1 支持矩阵](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.25.1/reference/support-matrix.html)列出其 **CUDA 12.x** 组件支持 CUDA 12.8。9.25.1 安装程序可能把 `cudnn64_9.dll` 放在 `C:\Program Files\NVIDIA\CUDNN\v9.25\bin\12.9\x64` 这样的深层目录；其中的 `12.9` 表示所装组件的 CUDA 版本目录，不能仅凭找到 DLL 就认定它与本机 CUDA 12.8 可配合。先让检测工具识别或手动指定**实际含有 DLL 的文件夹**，再以本机实际 KataGo 分析结果判断。上述 9.25.1 测试不等于其他安装方式或机器均已验收。

## 第四步：实际检测一次

回到“检测分析环境”工具，选择 **“自动识别（推荐）”**，点击 **“重新识别”**。自动找到的 CUDA 与 cuDNN 文件夹会显示在路径框中，结果区也会分别显示当前选用了哪一处目录。若装有多个版本，以结果区显示的实际目录为准；需要改用另一版本时切到手动模式。若自动搜索未找到，但已经安装了相应组件，分别点击 **“已安装 CUDA？选择 DLL…”** 或 **“已安装 cuDNN？选择 DLL…”**，选择本机实际存在的对应 DLL；工具会自动切到手动模式，并立即重新检查所选文件夹。也可以在“手动指定”下浏览或输入路径；上方结果会随之更新，不再保留过期的自动搜索结论。找到两个组件的 DLL 后，点击 **“保存并检测”**。装在自定义目录且没有配置 `CUDNN_PATH` 或 `PATH` 的组件，可能需要手动选择一次。

检测会真正启动 KataGo 并分析一个测试局面。只有看到分析通过，才表示这台电脑上的分析环境已就绪。如果没有通过，先看窗口指出缺少的是显卡驱动、哪个 DLL，还是引擎启动失败，再按提示修正。文件齐全但仍启动失败时，不要把“已找到 DLL”当成分析成功。

这项检测是首次安装或更换驱动、CUDA/cuDNN、显卡后主动运行的工具，不是每次打开主程序都要做。若主程序正在运行，检测中修改了路径设置，关闭并重新打开主程序后再试分析。

## 第五步：首次启动

KataGo 检测通过后，从开始菜单或所选桌面快捷方式打开 RecurGO。新建棋局并开启 **“实时分析”**，确认右侧出现候选点和胜率。分析、对战和棋谱操作详见[用户说明书](USER_GUIDE.md)；调整分析访问量也在说明书中介绍。

## 可选：使用 Ollama 补充棋理讲解

Ollama 不随安装包提供，没有安装也不影响前面的功能。如需使用，可以按项目约定目录准备：

1. 从 [Ollama v0.34.3 官方发行页](https://github.com/ollama/ollama/releases/tag/v0.34.3)下载 Windows AMD64 CLI ZIP。把压缩包里的文件完整解压到 `%LOCALAPPDATA%\RecurGO\ollama\v0.34.3\` 中，不要只复制 ollama.exe；解压后该目录中应能看到 ollama.exe。
2. 使用安装版附带的“启动本机 Ollama”入口启动服务；再使用随包的模型下载入口下载默认模型 qwen3:4b-instruct-2507-q4_K_M。模型会保存在 `%LOCALAPPDATA%\RecurGO\ollama\models\` 中。下载需要联网，请等到下载完成。
3. 回到 RecurGO，点击顶部 **“本机 AI 解释设置”**，勾选启用，点击 **“检测本机模型”**，选择下载好的模型并保存。

如果检测不到模型，先确认 Ollama 服务正在运行、模型已经下载完成。也可以按 [Ollama 官方 Windows 说明](https://docs.ollama.com/windows)正常安装 Ollama；这种方式的程序和模型由官方安装自行管理，不会自动放进上面的项目文件夹。语言模型的讲解可能出错，落点与胜率仍以 KataGo 为准。

## 遇到问题

| 看到的情况 | 先检查什么 |
| --- | --- |
| 打开棋盘后没有候选点 | 是否开启“实时分析”；再运行独立的“检测分析环境”，看 KataGo 能否完成实际测试 |
| 自动识别未找到 cudart64_12.dll、cublas64_12.dll 或 cudnn64_9.dll | 若已用 NVIDIA 安装程序安装，先重新打开检测工具，再手动选择实际含有这些 DLL 的目录，可能是 `bin` 下的 CUDA 版本与 `x64` 子目录；无需重复下载。若采用 ZIP 方式，检查是否已解压到工具显示的目录。自动搜索未找到不等于系统没有安装。 |
| 检测找到 DLL，但分析仍失败 | 看检测工具显示的原始错误；核对驱动、CUDA/cuDNN 版本和显卡可用性 |
| KataGo 提示缺少 `msvcp140.dll` 或 `vcruntime140.dll` | 从上面的微软官方页面安装 Visual C++ Redistributable x64，再运行检测工具 |
| 本机 AI 没有回答 | Ollama 是否启动、模型是否下载完成，以及“本机 AI 解释设置”是否选择了该模型；KataGo 分析可单独使用 |

反馈问题时，可以提供错误文字、Windows 版本和显卡型号。棋谱、个人数据库和缓存属于你的本机数据；请不要把整个数据文件夹或私人棋谱上传到公开问题页面。

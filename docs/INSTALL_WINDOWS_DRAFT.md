# RecurGO Windows 安装与使用说明（已由新版取代的草稿 v0.4）

[English](INSTALL_WINDOWS_DRAFT.en.md) | 简体中文

> **旧草稿，勿按以下步骤安装。** 当前说明请看[Windows 安装指南](INSTALL_WINDOWS.md)；源码用户请看[源码启动说明](SOURCE_SETUP.md)。

## 下载前先看

首个安装版计划支持 Windows x64 和 NVIDIA 显卡。没有 NVIDIA 显卡的电脑暂不适用；不同 NVIDIA 显卡也须通过下文的独立工具确认能否实际分析。

安装包将包含 RecurGO、KataGo 引擎、分析模型以及程序运行所需组件。你不必自行安装 Python、寻找 KataGo 模型或修改引擎配置。另需准备的组件分两类：

| 组件 | 放在哪里 | 是否必须 |
| --- | --- | --- |
| NVIDIA 显卡驱动 | 安装在 Windows 中；多数 NVIDIA 电脑已有 | 必须 |
| CUDA 12.8 运行库、cuDNN 9.8 | 从 NVIDIA 官方下载，把解压后的文件放进下文的项目文件夹；已有合适的系统安装也可自动识别 | 必须有可用版本 |
| Ollama 和语言模型 | 可选，建议放在下文的项目文件夹 | 仅使用本机 AI 补充讲解时需要 |

没有 Ollama，棋盘、KataGo 分析、胜率、候选点、复盘和程序自带的即时棋理说明仍可使用。

## 第一步：安装 RecurGO

发布后，在项目的 GitHub **Releases** 页面下载标有 **Windows x64** 的安装程序，运行并按提示完成安装。

页面上的 **Source code (zip)** 和 **Source code (tar.gz)** 是 GitHub 自动生成的源码压缩包，供查看代码或自行开发；它们不是可以双击安装的程序。普通用户应下载 Releases 中单独提供的 Windows 安装程序。

## 第二步：检查显卡驱动

打开安装包附带的 **“检测分析环境”** 独立工具。它会显示能否找到并初始化 NVIDIA 显卡驱动。

- 显示驱动正常：继续下一步，不需要重装驱动。
- 显示驱动不可用：到 [NVIDIA 官方驱动页面](https://www.nvidia.com/en-us/drivers/)按自己的显卡型号安装；如果安装程序要求重启，重启后再打开检测工具。
- 没有 NVIDIA 显卡：首个 Windows 安装版暂不适用。

NVIDIA 显卡驱动安装在 Windows 系统中，无须放入 RecurGO 的安装目录。主程序里没有驱动或 CUDA 设置页；相关操作只在这个独立工具中进行。

## 第三步：准备 CUDA 和 cuDNN 文件

在“检测分析环境”工具中点击 **“打开固定目录”**。它会建立并打开放置运行库的文件夹。工具窗口也会显示两个目标文件夹的完整路径；请以窗口显示的路径为准。相对安装目录的结构如下：

    runtime\cuda_deps\nvidia\cuda\bin\    放 CUDA 12.8 运行库的 DLL
    runtime\cuda_deps\nvidia\cudnn\bin\   放 cuDNN 9.8 的 DLL

1. 从 NVIDIA 官方 [CUDA Runtime ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/)下载 **Windows x86_64、12.8** 的压缩包；再从 [cuBLAS ZIP 目录](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/)下载对应的 **Windows x86_64、12.8** 压缩包。分别解压，把这两个压缩包中 bin 文件夹里的 DLL 放进上面的 cuda\bin。
2. 从 [NVIDIA cuDNN 9.8 官方页面](https://developer.nvidia.com/cudnn-9-8-0-download-archive)下载 **cuDNN 9.8、CUDA 12、Windows x86_64** 的 ZIP。解压，把其中 bin 文件夹里的 DLL 放进上面的 cudnn\bin。

要放的是解压后的 DLL，不是还没解压的 ZIP，也不是 CUDA 安装程序 EXE。不用从其他电脑的系统目录复制 DLL。若你的电脑已经安装了合适的 CUDA/cuDNN，检测工具也会尝试自动寻找，无须重复下载。若文件保存在其他位置，可在工具中改选 **“手动指定”**，分别选中实际的 bin 文件夹。

## 第四步：实际检测一次

回到“检测分析环境”工具，选择 **“自动识别（推荐）”**，点击 **“重新识别”**。窗口会分别显示 CUDA 和 cuDNN 找到了什么；如果你刚复制文件，这一步可以刷新结果。然后点击 **“保存并检测”**。

检测会真正启动 KataGo 并分析一个测试局面。只有看到分析通过，才表示这台电脑上的分析环境已就绪。如果没有通过，先看窗口指出缺少的是显卡驱动、哪个 DLL，还是引擎启动失败，再按提示修正。文件齐全但仍启动失败时，不要把“已找到 DLL”当成分析成功。

这项检测是首次安装或更换驱动、CUDA/cuDNN、显卡后主动运行的工具，不是每次打开主程序都要做。若主程序正在运行，检测中修改了路径设置，关闭并重新打开主程序后再试分析。

## 第五步：打开程序，按需调整分析量

启动 RecurGO，打开或新建棋局，开启 **“实时分析”**，即可查看 KataGo 候选落点、胜率和思路说明；需要时可使用全盘复盘。

分析访问量可以自己改：点击窗口顶部的 **“分析设置”** → 修改 **“每个局面的访问量”** → 保存。默认值是 **800 visits**。访问量较高通常会分析更久；较低通常更快，但搜索可能不够充分。此设置用于之后的实时分析和全盘复盘，不改变对战中“最强”AI 的搜索设置；旧分析结果也不会因为修改数值而自动变成新访问量的结果，需要重新分析。

## 可选：使用 Ollama 补充棋理讲解

Ollama 不随安装包提供，没有安装也不影响前面的功能。如需使用，可以按项目约定目录准备：

1. 从 [Ollama v0.34.3 官方发行页](https://github.com/ollama/ollama/releases/tag/v0.34.3)下载 Windows AMD64 CLI ZIP。把压缩包里的文件完整解压到安装目录的 runtime\ollama\v0.34.3\ 中，不要只复制 ollama.exe；解压后该目录中应能看到 ollama.exe。
2. 使用安装版附带的“启动本机 Ollama”入口启动服务；再使用随包的模型下载入口下载默认模型 qwen3:4b-instruct-2507-q4_K_M。模型会保存在项目的 runtime\ollama\models\ 中。下载需要联网，请等到下载完成。
3. 回到 RecurGO，点击顶部 **“本机 AI 解释设置”**，勾选启用，点击 **“检测本机模型”**，选择下载好的模型并保存。

如果检测不到模型，先确认 Ollama 服务正在运行、模型已经下载完成。也可以按 [Ollama 官方 Windows 说明](https://docs.ollama.com/windows)正常安装 Ollama；这种方式的程序和模型由官方安装自行管理，不会自动放进上面的项目文件夹。语言模型的讲解可能出错，落点与胜率仍以 KataGo 为准。

## 遇到问题

| 看到的情况 | 先检查什么 |
| --- | --- |
| 打开棋盘后没有候选点 | 是否开启“实时分析”；再运行独立的“检测分析环境”，看 KataGo 能否完成实际测试 |
| 检测说缺少 cudart64_12.dll、cublas64_12.dll 或 cudnn64_9.dll | 是否下载了对应的 Windows ZIP、已经解压，并把 bin 里的 DLL 放进工具显示的正确目录 |
| 检测找到 DLL，但分析仍失败 | 看检测工具显示的原始错误；核对驱动、CUDA/cuDNN 版本和显卡可用性 |
| 本机 AI 没有回答 | Ollama 是否启动、模型是否下载完成，以及“本机 AI 解释设置”是否选择了该模型；KataGo 分析可单独使用 |

反馈问题时，可以提供错误文字、Windows 版本和显卡型号。棋谱、个人数据库和缓存属于你的本机数据；请不要把整个数据文件夹或私人棋谱上传到公开问题页面。

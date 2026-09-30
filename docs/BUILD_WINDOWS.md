# Windows 安装包构建说明（v1.0.1）

[English](BUILD_WINDOWS.en.md) | 简体中文

此文档供维护者构建本地安装包候选。一个正式版本对应同一份公开源码和一个 Windows x64 安装程序；GitHub 的源码 ZIP/TAR 是版本标签的自动快照，不是另一套需要维护的程序。构建、生成校验值均在本机进行，不会上传 GitHub。

## 构建输入

- Windows 10/11 x64、Python 3.13、项目 `.venv`，按[源码启动说明](SOURCE_SETUP.md)安装包含 `dev` 组的固定依赖。
- 从 [Inno Setup 官方页面](https://jrsoftware.org/isdl.php)获取 `ISCC.exe`；构建脚本只调用编译器，不把 Inno Setup 安装程序放进源码仓库或用户安装包。
- 按[源码启动说明](SOURCE_SETUP.md)准备 KataGo 1.16.5 CUDA 引擎、主模型、Human SL 模型与 `runtime/runtime.local.json`。模型和二进制不提交 Git。
- `packaging/asset_lock.json` 列出安装包允许收录的九个固定资源及 SHA-256。任何来源文件不符时构建立即停止。变更上游版本须重新核对许可、来源、哈希及功能，然后明确更新锁定文件。
- 本地 Git 必须可用；`licenses/` 仅从已跟踪文件清单复制，出现额外文件时构建停止。
- 桌面快捷方式图标使用 `assets/recurgo-icon-artwork.png` 原图制作；仅将四角规则裁为透明的版本保存在 `assets/recurgo-icon-artwork-rounded.png`，再生成 `src/recurgo/assets/recurgo.ico`。构建脚本只把 ICO 复制到安装目录，供可选桌面快捷方式引用；PNG 不进入安装目录，程序和安装器自身的图标不变。
- 本机 Inno Setup 7 编译器会显示“Non-commercial use only”；[官方商业许可问答](https://jrsoftware.org/isorder.php)按商业用途及收入判断是否请求购买，并说明购买并非严格要求。此提示本身不证明当前个人开源发布受阻。

## 构建

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_windows_release.py --iscc "C:\path\to\ISCC.exe"
```

脚本每次创建新的 `build/release-.../` 目录，不覆盖已有产物。`stage/RecurGO/` 是待安装的文件树；`file-manifest.json` 记录每个文件的大小和 SHA-256；`output/` 包含安装程序及 `SHA256SUMS.txt`。`build/` 被 Git 忽略。

安装包候选包含 RecurGO 程序和 Python/Qt 运行组件、KataGo 引擎、两个模型、分析配置、独立环境检测工具、可选 Ollama 的启动和模型下载入口、双语说明及许可材料。它不包含开发机的棋谱、数据库、CUDA/cuDNN、Ollama 程序或语言模型。用户自行从 NVIDIA 官方准备驱动与 CUDA/cuDNN；可选 Ollama 自行从官方取得。

用户运行库和个人数据位于当前用户的 `%LOCALAPPDATA%\RecurGO`；默认程序目录是 `%LOCALAPPDATA%\Programs\RecurGO`，安装器每次都显示程序目录选择页。安装包中的 KataGo 引擎目录不复制开发机的 Microsoft Visual C++ DLL；独立工具检查系统运行库并给出微软官方链接。Python/Qt/NumPy 上游包自带的二进制组件仍需按实际文件清单复核再分发条件。

## 版本与发布

当前正式版本为 **v1.0.1**。`pyproject.toml`、`src/recurgo/__init__.py`、安装程序文件名、Git 标签和 GitHub Release 标题应一致。每次发布均从最终源码重新构建，不能把开发版安装包改名充当正式版。发布说明全文须经用户确认后才能上传或修改公开内容。v1.0.1 的功能、验证边界和发布步骤见[发布核验记录](RELEASE_1.0.1.md)。

本地编译成功只证明生成了安装文件。每个后续版本仍应检查安装、独立检测、真实 KataGo 分析、对战、棋谱、复盘、中英文切换与可选 Ollama，并重新核对源码及安装包隐私、第三方许可和 LGPL 对应源码/共享库替换方式。[首版设计记录](RELEASE_TARGET.md)说明验收范围。不要把 `build/` 整目录上传；只在同一版本的 GitHub Release 中附上安装程序和校验文件。

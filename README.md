# RecurGO

[English](README.en.md) | 简体中文

用户文档：[Windows 安装指南](docs/INSTALL_WINDOWS.md) · [用户说明书](docs/USER_GUIDE.md) · [源码启动](docs/SOURCE_SETUP.md) · [构建安装包](docs/BUILD_WINDOWS.md)。

本地 KataGo 围棋练习、对战和复盘程序。

首次公开版本为 **v1.0.0**；Windows x64 安装程序与源码使用同一版本号。
KataGo 实际分析已在 Windows x64 的 NVIDIA GeForce RTX 5070 Ti Laptop GPU 和
NVIDIA GeForce RTX 2080 Ti 上通过；后者在主程序中也显示了候选点和胜率。
这不代表所有 NVIDIA 显卡或全部功能均已验收。
多显卡后端选择尚未完成。仓库不包含模型、运行库、个人棋谱或缓存。

面向普通用户的[Windows 安装指南](docs/INSTALL_WINDOWS.md)介绍安装流程；[用户说明书](docs/USER_GUIDE.md)介绍日常操作。安装程序和校验文件见同版本 GitHub Release；程序已有访问量设置和 Ollama 安装提示。
CUDA/cuDNN 路径配置与 KataGo 实际检测都在独立的 `check_analysis_environment.cmd` 中；
源码模式优先识别 `runtime/cuda_deps/nvidia/`；安装版优先识别当前用户数据目录中的
`cuda_deps/nvidia/`，两者都保留手动选取。显卡驱动在
Windows 中安装，工具会检查其可用性。主程序没有环境配置或测试入口。

当前状态：

- KataGo v1.16.5 CUDA 运行环境已验证。
- 实时分析和全盘复盘可在工具栏“分析设置”中修改 visits；默认 800，旧预算缓存保留但不混用。
- 主分析模型与 Human SL 模型已验证。
- 长期运行的 JSON 分析进程、增量结果和取消请求已接入 Qt 界面。
- 支持手动打谱、公平对战、辅助对战；对战可选择玩家执黑或执白，执白时 AI 自动先行。
- 六档难度中，入门至顶级按 Human SL 段位策略概率抽样，最强采用主模型最佳手。
- 候选点、胜率、目差、人类偏好、PV 和胜率折线可实时更新。
- 胜率折线严格跟随当前变化路径，悔棋后立即回退。
- 棋盘支持合法点位的半透明落子预览，以及落子、提子音效和静音。
- 支持四套棋盘主题、四套内置棋子样式，以及可分别选择的内置落子声和提子声；
  音量、静音和外观选择保存在本地数据库中。
- 支持从剪贴板或本地图片识别 9/13/19 路静态棋局；自动识别后可手选四角、
  旋转/镜像、逐点校正，并明确选择当前黑方或白方落子。
- 中国规则在界面显示“黑贴3¾子”，引擎仍使用等价的 `komi=7.5`。
- 支持手动结束、认输、双方停一手后数子、整块死子确认和结果保存。
- 数子完成后可停留当前棋局或直接开始新一盘，SGF 会保留 `RE` 结果。
- 胜率图支持横向、纵向缩放；仅在鼠标悬停时显示手数、黑胜率和指示线。
- SQLite 每手自动保存，棋谱库可恢复历史对局。
- 棋谱库支持单击后“进入棋谱”、双击直接进入，以及确认后永久删除棋谱和关联分析缓存。
- 支持带变化分支和注释的 SGF 导入、导出。
- 导入或打开历史棋谱后，可用首手、上一手、手数滑杆、下一手和末手逐手复盘。
- 支持可停止、可续做的全盘 AI 分析，每个局面的候选点、胜率和目差即时保存。
- 全盘复盘提供概览、胜率走势、着法质量、问题手、吻合度五个视图，并可按布局、
  中盘、官子筛选；全部质量统计均分别标明黑方和白方。
- 着法质量使用黑白双方分类柱状图，问题手与吻合度使用可点击的逐手时间轴；
  点击标记即可跳到相应局面。
- 默认显示英语；“Preferences → Language / 语言”可选择简体中文或 English，点击确定后即时生效。
  本地棋理说明、对话框和可选 Ollama 提示词会使用所选语言；模型输出语言仍需实际检查。
- 模式、难度、执色、实时分析和领地控件与其他功能位于同一行工具栏；窗口较窄时，
  可点右端白底溢出按钮打开未显示的控件，顶部“Menu / 菜单”也保留备用入口。

图片识谱由本地 OpenCV 完成，不上传图片。可选语言模型解释只向本机 Ollama 服务发送
当前棋盘与候选事实，不包含棋手名、棋谱注释或本机路径。图片导入建立的是静态根局面，
因此不会臆测图片中不存在的历史手顺、既往提子数或劫争历史。

开发启动：

先安装 Python 3.13，在项目目录创建环境并安装依赖：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m recurgo.app
```

首次克隆还需要自行准备 KataGo 引擎、模型和运行时配置；仅安装 Python 依赖不会启用
AI 分析。当前 CUDA 配置步骤和限制见 [源码启动说明](docs/SOURCE_SETUP.md)。
开发启动采用 editable 安装；普通 wheel 安装及独立 exe 尚未完成发行验证。

棋理说明先由本地规则根据 KataGo 数据即时显示。可选的 Ollama 补充解释支持自动请求、
流式显示和过期结果取消；KataGo 正在搜索时优先让它完成。Ollama 默认关闭，使用方法和
真实运行验证状态见 [本机 AI 说明](docs/OLLAMA_LOCAL.md)。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\probe_qt_engine.py
.\.venv\Scripts\python.exe scripts\probe_ui_battle.py
```

`.gitignore` 排除本机运行目录和数据；源码提交范围见 [分发说明](docs/DISTRIBUTION.md)。

## 许可与第三方组件

RecurGO 自有代码与文档以 [MIT License](LICENSE) 发布，版权署名为
[izaak (izaak217)](https://github.com/izaak217)。当前源码版本为 **v1.0.1**。

KataGo 引擎、模型、Qt/PySide6 及其他依赖分别遵循各自的许可证；本项目的 MIT
许可不替代第三方条款。组件清单与许可原文见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [licenses/](licenses/README.md)。
分发时应随包保留这些资料，具体源码获取与打包要求见
[分发说明](docs/DISTRIBUTION.md)。

本项目是基于 KataGo 的独立应用，并非 KataGo、Qt 或 NVIDIA 的官方产品；
提及这些名称仅用于说明所使用的组件，不表示官方背书。

随包组件的许可资料和固定版本源码入口见上述索引；安装包不包含 NVIDIA 驱动、CUDA/cuDNN 或 Ollama。
版本记录见 [CHANGELOG.md](CHANGELOG.md)。

安全问题请按 [安全报告说明](SECURITY.md) 私下报告；不要在公开问题中披露细节。

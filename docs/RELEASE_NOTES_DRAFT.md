# RecurGO v1.0.0 发布说明草稿

[English](RELEASE_NOTES_DRAFT.en.md) | 简体中文

> 历史发布说明草稿；正式内容以 v1.0.0 Release 为准，不要将本文直接当作发布公告。

RecurGO 是本地运行的围棋练习、对战和复盘程序。首次正式发布拟在**同一个版本**提供公开源码，以及单独的 **Windows x64 安装程序**。GitHub 自动生成的 `Source code (zip/tar.gz)` 供阅读和二次开发；普通用户下载 Release 附件中的安装程序。

## 安装包内容

- RecurGO 程序及其 Python/Qt 运行组件；KataGo 1.16.5 CUDA 引擎；主分析模型和 Human SL 模型；分析配置。
- 独立“检测分析环境”工具、可选 Ollama 启动及模型下载入口、中英文[安装说明](INSTALL_WINDOWS.md)和[用户指南](USER_GUIDE.md)，以及第三方许可材料。
- 不包含个人棋谱或数据库，也不包含 NVIDIA 驱动、CUDA/cuDNN、Ollama 程序或语言模型。

## 首发支持与使用

目标平台是 Windows 10/11 x64 和 NVIDIA CUDA 12.8 后端。NVIDIA GeForce RTX 5070 Ti Laptop GPU 和 NVIDIA GeForce RTX 2080 Ti 已通过实际 KataGo 分析；后者的主程序也显示了候选点和胜率。其他显卡与后端未列入已验证范围，RTX 2080 Ti 的全部功能也尚未验收。用户须有适配的 NVIDIA 驱动、CUDA/cuDNN 和系统 Visual C++ 运行库；独立检测工具给出状态、官方下载链接并实际运行一次 KataGo 分析。可选 Ollama 仅补充语言解释，KataGo 决定落点与分析数值。

程序支持手动研究、对战、实时分析、棋谱库、SGF 导入导出、全盘复盘和中英文即时切换。分析访问量可单独设置；“最强”对战模式、主模型、Human SL 和候选点排序不因打包调整。

安装程序的文件名、大小与 SHA-256 以正式 Release 附件及 `SHA256SUMS.txt` 为准。问题反馈可通过 GitHub Issues；安全问题按 [SECURITY.md](../SECURITY.md) 私密联系。请勿公开上传私人棋谱、数据库或日志。

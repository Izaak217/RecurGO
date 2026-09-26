# 源码与 Windows 安装包的分发（文档修订 v0.1.4）

[English](DISTRIBUTION.en.md) | 简体中文

本文说明 v1.0.0 源码与 Windows 安装包的收录范围，以及后续版本应重复的发布检查。
许可总表见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## 源码仓库收录范围

保留 `src/`、`tests/`、`scripts/`、公共 `docs/`、`licenses/`、启动脚本、项目元数据及
根目录的许可文件。`docs/setup/` 是可公开的配置示例，用户复制后再填写本机路径。

`.gitignore` 排除：

| 内容 | 路径或规则 |
| --- | --- |
| 棋谱、数据库、分析缓存、截图、诊断输出、日志 | 整个 `data/`；额外排除数据库、日志和 SGF 后缀 |
| 本机引擎、模型、CUDA/cuDNN、Ollama、下载包、密钥及运行配置 | 整个 `runtime/` |
| Python 环境及编译、测试和构建缓存 | `.venv/`、`__pycache__/`、工具缓存、`build/`、`dist/` 等 |
| 环境秘密、本机覆盖配置和编辑器状态 | `.env*`、`*.local.json` 等；保留 `.env.example` |
| 早期本机实施笔记 | `docs/PROJECT_PLAN.md` |

`tests/fixtures/` 下经审核的 SGF 可作为测试资料保留。第三方许可来源包
`licenses/sources/sgfmill-1.1.1.tar.gz` 需要保留，因此没有粗略地忽略所有压缩文件。

## 同名 `data` 目录的区别

| 位置 | 内容与处理 |
| --- | --- |
| 项目根目录 `data/` | 本机棋谱数据库、日志、环境检测结果及其它用户数据；整目录不进源码和安装包。 |
| `.venv/Lib/site-packages/**/data/` | 本机 Python 依赖的资源或测试资料；虚拟环境不进源码，也不整目录打包。 |
| 安装文件树 `_internal/cv2/data/` | PyInstaller 收集的 OpenCV 包资源；目前仅有 `__init__.py`，允许随程序进入安装包。 |
| 其它新出现的 `data/` | 未经审查时构建失败；需先确认来源及是否含私人内容。 |

安装包构建器只从 Git 已跟踪的 `licenses/` 文件复制许可材料；该目录出现额外文件时
停止构建。它还检查安装文件树中的数据库、棋谱、日志、链接文件、常见密钥标记与本机路径。
这些规则是防止误打包的门槛，不替代发布前对源码、二进制和安装后行为的人工审查。

忽略文件仍存在于本机，`.gitignore` 不删除它们。它也不约束手动上传、整目录压缩、
`git add -f` 或已经被 Git 跟踪的文件，不能把它当作秘密扫描器。
规则含义见 [Git 官方说明](https://git-scm.com/docs/gitignore)。

## 每次公开推送前复核

项目目录已在 2026-09-23 初始化本地 `main` 仓库；首版以一份根提交发布。
每次公开推送前，使用以下
命令查看内容：

```powershell
git status --short --untracked-files=all
git check-ignore -v data/recurgo.db runtime/runtime.local.json
git add --dry-run .
```

暂存后还要看 `git diff --cached --name-only` 与 `git diff --cached`，确认没有个人棋谱、
截图、账号信息或下载资源。不要用 `git add -f` 绕过规则，也不要直接压缩整个工作目录。
以后如果文件已经提交，新增忽略规则不会自动清除其历史内容，需要另行检查处理。

GitHub 网页也支持上传文件，不要求本机 Git；日常维护使用 Git 提交和推送更方便。
网页上传不会替你应用本地的 `.gitignore`，仍须人工选择文件。
参见 [GitHub 文件上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。

## 源码、Python 包与安装包的区别

本项目自有源码使用 MIT。第三方原始许可和中文说明位于 `licenses/`；Python 构建元数据
声明收入这些资料，但独立 wheel 的安装运行路径尚未验证，不能视为已发布成品。

仅发布本项目源码，不意味着把本机整个环境一起再分发。源码仓库不包含引擎二进制、
NVIDIA 运行库、Ollama 程序或模型；用户独立获取这些资源时仍需遵守各自条款。

每次 Windows 安装包必须依据**实际包含的文件**检查 Qt/FFmpeg、KataGo 附带组件、MSVC、
OpenCV、NumPy 以及模型等。需要保留版权与许可、提供适用的对应源码，并落实 LGPL
所需的库替换等权利。v1.0.0 的资料和构建清单是本版核对依据，不能自动套用于将来版本。

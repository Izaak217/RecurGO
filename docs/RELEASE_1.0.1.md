# v1.0.1 验证记录与发布流程

日期：2026-09-30。功能和规则说明见 [数子设计记录](SCORING_RULES_PLAN.md)、[用户说明书](USER_GUIDE.md)和[更新记录](../CHANGELOG.md)。

## 问题与修改

旧终局窗口只对移除死子后的连通空区做封闭边界计数；未围严的大片区域会一起判作中立，且完全不使用正常的 KataGo 领地数据。因此结束按钮产生的数值与局内预测可能严重不符。

现在以当前节点的预测预览，完成同预算的终局分析后核对点位。计分模型校验整块死活、共享点及未确认点；棋盘支持四种点位状态；主窗口隔离数子期间的实时分析和 AI 落子回包；数据库保存最终图和节点。原始棋盘不被修改，旧棋谱不重算。模型、客观分析预算、候选顺序及最强 AI 搜索配置均未更改。

涉及 `domain/scoring_estimate.py`、`domain/scoring.py`、`ui/scoring_dialog.py`、`ui/board_widget.py`、`ui/main_window.py`、`storage/database.py`、分析设置文字及相应回归测试。

## 已执行验证

- 全套 pytest：314 项通过；覆盖点位切换、实际鼠标点击、奇偶共有点、四分之一子胜差、整块死活矛盾、劫点待确认、异步过期和失败、取消与重新打开、保存后查看，以及原有对战、棋谱、SGF、识图、引擎与复盘测试。
- mypy：42 个源码文件通过。
- 真实 KataGo：用合成的 19 路已活棋块局面发起数子请求，预算 800，完成 815 visits，返回 361 点；19 个低确定性公共边界点保留为待确认。另以开局局面验证全部低确定性点不会被误认作共有。
- 中英文 19 路界面：逐点黑／白／共有／待确认、禁用未完成确认、结果冻结、关闭和新局按钮；截图由项目内 probe 生成。离屏测试显式加载本机字体，不打包这些字体。
- Ruff：与原提交逐项对照，本次改动未新增检查问题；涉及文件的既有问题由 23 项减少至 18 项，剩余为原有长行格式提示，不宣称全仓库 Ruff 零警告。
- 最终 Windows 安装程序：500.81 MB；安装树 691.38 MB、670 个文件，清单大小和 SHA-256 全部相符；39 个被打包的项目模块与最终源码编译结果一致，许可文件字节一致，未收录私密数据或凭证。
- 使用安装树中的引擎与模型完成数子请求：811 visits、361 点、19 个待确认边界点。冻结的独立环境检测程序返回成功并完成 21 visits；冻结主程序在项目内隔离数据目录启动成功。没有运行安装器去改动本机现有安装、注册表或用户棋谱；安装向导及所有硬件组合未重新验收。
- 安装程序 SHA-256：`79cc1cecdc51917d3c7275cec538ea09b62461fabfd0d835c645f9a73d4b33a1`。安装器未添加代码签名。
- 发布目标为 `v1.0.1`。公开状态及附件以 [GitHub Release](https://github.com/Izaak217/RecurGO/releases/tag/v1.0.1) 为准；只有附件为 uploaded 且 GitHub 摘要匹配上述本地摘要，才算远端核验通过。

## 升级与发布步骤

1. 退出正式版；备份个人数据目录 `%LOCALAPPDATA%\RecurGO`，自定义 `RECURGO_DATA_DIR` 的用户备份该路径。源码目录和已安装程序目录可以完全分开。
2. 对齐 `pyproject.toml`、`src/recurgo/__init__.py`、双语更新记录和用户文档的版本；运行测试、静态检查与真实引擎 probe。
3. 按 [Windows 构建说明](BUILD_WINDOWS.md)生成新的唯一构建目录。核验锁定资源哈希、许可字节、文件清单和敏感文件排除，再测试冻结产物。构建不会自动更改现有安装目录。
4. 只提交源码、测试和公开文档；不提交开发凭证、个人棋谱、数据库、日志、模型、运行库或 `build/`。推送经验证的提交，建立同名版本标签。
5. 在对应 GitHub Release 上传唯一安装程序和 `SHA256SUMS.txt`，附双语更新说明；核对远端标签提交、版本、附件大小、上传状态和 GitHub SHA-256。
6. 用户下载新版本后核对 SHA-256，可选择现有正式版目录升级，或单独的新目录；两者默认仍使用同一份个人数据。运行环境检测，再查看棋谱库及数子。旧版不能显示新增的归属图，升级前备份用于恢复。

## 限制

AI 预测不等于终局裁判；双方仍需确认死活和归属。低确定性阈值不是规则证明；特殊循环劫不自动裁决。SGF 保留项目既有结果单位，未导出本地归属修正图。新版本在本机验证，不代表对所有显卡重新认证；没有为此修改 CUDA、cuDNN 或用户已安装程序。

## English

The old scorer flood-filled closed regions without using KataGo ownership, making large open
boundaries appear neutral. v1.0.1 completes a final-position search, supports four-state point
corrections and whole-group status, and persists the reviewed map. Models, objective search
budgets and Strongest play remain unchanged.

Validation: 314 tests and type checking of 42 source files passed. A real 800-visit request
completed 815 visits and returned all 361 ownership values. Nineteen uncertain boundary points
remained unresolved. Chinese and English UI probes cover editing and confirmation. The final
500.81 MB installer contains a 670-file tree with verified hashes, exact license bytes and no
private files. All 39 packaged project modules match compilation of the final source. Staged
engine scoring completed 811 visits; the frozen environment checker completed 21 visits and
the frozen app started with isolated project-local data. No new lint findings were introduced;
18 existing long-line findings remain in changed files. This run did not execute the installer
wizard or modify the existing installation. The installer is unsigned. The SHA-256 above must
also match the digest of the uploaded GitHub release asset.

Release workflow: align versions/docs, run regression and engine/UI probes, build a fresh
installer, audit manifest/licenses/private-data exclusion, test staged binaries, commit only
public project files, push and tag the verified revision, upload the installer and SHA256SUMS,
then verify the remote tag and asset hashes. Close the old application and back up the user
data directory before upgrading. A new application folder can share the same user data.

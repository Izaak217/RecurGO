# v1.0.1 验证记录与发布流程

日期：2026-09-30。功能和规则说明见[数子设计记录](SCORING_RULES_PLAN.md)、
[用户说明](USER_GUIDE.md)和[更新记录](../CHANGELOG.md)。

## 问题与修改

v1.0.0 的终局窗口只按封闭空区计数，未使用 KataGo 的领地预测，导致未围严的大片领地可能被算成中立点。
v1.0.1 获取当前局面的 KataGo 分析，结合整块棋子的预测、搜索波动、能确定的活棋和眼位，
以及条件明确的双活形状，给出供用户核对的数子建议。
用户手动修改最后叠加，优先于自动判断。整块死活判断不一致时给出提示，不阻止用户确认
完整的点位结果；待确认点仍需补齐。

修改涉及 domain/scoring_shape.py、domain/scoring_estimate.py、domain/scoring.py、
engine/service.py、ui/scoring_dialog.py、ui/board_widget.py、ui/main_window.py、
storage/database.py 及相关测试。引擎新增归属波动统计的可选请求；
局内分析、推荐排序、模型、访问量基线和最强 AI 的配置没有调整。保存格式兼容旧棋谱。

## 源码验证

- 完整 pytest：338 项通过；mypy：43 个源码文件通过。新增代码和相关计分文件的 Ruff 检查通过，
  不据此宣称整个历史仓库没有 lint 问题。
- 真实 KataGo：6 个公开的 19 路合成局面，分别测试 800、3,200、12,800 visits，共 18 次请求。
  对比同一引擎回包经逐点阈值方法和当前算法处理后的结果。
- 5 个明确终局样例在这次运行的 800 visits 下，逐点阈值方法分别留下 6、36、1、0、19 个待确认点；
  当前算法均为 0，且没有错分点，胜差与人工标注一致。第 6 个尚未终局的公气样例，两种方法均保留
  19 个待确认点，没有自动平分。
- 更高访问量并未消除逐点阈值方法的所有待确认点；本次没有据此增加默认搜索预算。
- 单元测试覆盖小棋盘及 19 路的两眼活棋、无眼双活、带专有眼位双活、死子、已终局与未终局的公气，
  以及大空不可直接填满、外部逃跑路径、当前劫点、波动数据异常、人工修改覆盖棋形判断和刷新保留。
- 保存和重新打开人工结果、错误节点、过期回包、取消、原有对战、复盘、棋谱和识图等流程均包含在回归中。
- 中英文 19 路数子及结果窗口已渲染检查，控件和结果没有截断。
- 冻结后的 40 个项目模块与源码编译结果一致。安装树中的引擎和模型再次验证上述 6 个局面；
  5 个明确终局样例无错分及待确认点，未终局样例仍保留 19 个待确认点。
- 冻结的环境检测程序成功加载模型并完成 21 visits；冻结主程序在项目内隔离数据目录启动成功。

这些是限定样例的验证，不代表已穷尽双活、循环劫或所有实战局面。真实引擎对比只覆盖 19 路；
小棋盘的结构判断由单元测试覆盖，不据此扩大硬件或棋盘支持声明。

## 构建与发布验收

1. 对齐版本与文档，完成源码测试、真实引擎验证及中英文界面检查；完整发布文案须先由用户确认。
2. 在独立构建目录生成 Windows 安装包，核验锁定资源哈希、许可原文、文件清单和隐私排除，
   验证冻结程序及安装树中的真实引擎。构建不修改现有正式版安装目录。
3. 只提交源码、测试和公开文档，不提交开发凭证、个人棋谱、数据库、日志、模型、运行库或 build/。
4. 推送经验证的源码提交，将 v1.0.1 标签指向该提交，确保安装包、源码归档和标签提交一致。
5. 上传安装程序和 SHA256SUMS.txt，发布已确认的中英文说明。
6. 核对公开状态、标签提交、附件名称、大小、uploaded 状态和 GitHub 报告的 SHA-256。
   远端核验成功之前，不将发布视为完成。

最终安装包的校验值以随包生成的 SHA256SUMS.txt 为准。不在安装包内部文档写入该安装包
自身的哈希，避免无法满足的自引用校验。

## 安装与升级

Windows 用户下载安装程序和 SHA256SUMS.txt，并核对校验值。
安装前退出正在运行的 RecurGO；升级前备份个人数据目录 %LOCALAPPDATA%\RecurGO，
使用 RECURGO_DATA_DIR 的用户备份自定义目录。
可以安装到原正式版目录或单独的新目录，两者默认使用同一份个人数据。
运行环境检测，再检查棋谱库和数子。旧棋谱不重算，已有逐点结果仍可查看。

## 限制

自动建议仍可能出错，复杂双活和循环劫不作完整自动裁定，以用户最终确认的点位为准。
现有数据库和 SGF 延续原项目的结果单位；SGF 不携带本地逐点修改图。
安装器未增加代码签名。本次未运行安装向导去修改本机安装或注册表，未重新验收所有显卡组合，
未修改已有 CUDA、cuDNN 或正式版程序。

## English

Version 1.0.1 fixes end-of-game scoring and improves automatic territory assessment using
connected groups, eyes, search variation and a limited class of clear mutual-life shapes.
Manual decisions take priority; group-status notices do not block a completed manual map.
Unresolved points still need review. Models, search budgets, recommendations and Strongest
play settings are unchanged.

Validation: 338 tests and type checking of 43 source files passed. Six synthetic 19x19 positions
were tested at 800, 3,200 and 12,800 visits. Five settled examples had no wrong or unresolved
assignments with the current algorithm; the unfinished example retained its 19 unresolved points.
These limited fixtures do not establish general scoring accuracy or complete seki detection.
Both language interfaces were inspected. The 40 frozen project modules matched the source;
the staged engine repeated the six cases successfully. The frozen checker completed 21 visits,
and the frozen app started with isolated test data.

Release checks cover the approved text, installer contents, licenses, private-data exclusion,
matching source and tag, uploaded assets and SHA-256. Windows users should verify the installer
against SHA256SUMS.txt and back up games before upgrading. The installer wizard and all GPU
combinations were not re-tested, and the installer remains unsigned.

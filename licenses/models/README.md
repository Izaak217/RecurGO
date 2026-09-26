# KataGo 模型许可索引

文档版本：v0.1.4；核实日期：2026-09-25。

v0.2.0.dev25 本地安装包候选使用 `packaging/asset_lock.json` 固定下列两个模型的
SHA-256，并随包附带本目录的官方网络许可原文；源码仓库仍不提交模型文件。
这不等于安装包已完成全部第三方许可或运行验收。

本目录说明当前两个 KataGo 模型的许可及来源。模型权重与程序源码分别适用各自条款；不能因项目源码采用 MIT，就把全部模型也标成 MIT。

## 当前模型

| 本地文件名 | 用途 | 官方来源与适用许可 |
| --- | --- | --- |
| `kata1-b28c512nbt-s13255194368-d5935380940.bin.gz` | KataGo 主分析模型 | [官方 kata1 网络列表](https://katagotraining.org/networks/)中的同名模型，适用下述 KataGo Neural Network License。 |
| `b18c384nbt-humanv0.bin.gz` | Human SL 人类棋风模型 | [官方 Extra Networks](https://katagotraining.org/extra_networks/)中标为 KataGo Human SL Network 的模型，适用同一网络许可。 |

上述文件在本机 `runtime/models/`。本次重新计算的 SHA-256 与本机运行时清单一致；它们用于识别当前文件，不是独立取得的上游签名或版权证明：

```text
c5bca453d7b08ea8df6546439325d4dd681e77d975e1da3f7593d771147b73bc  kata1-b28c512nbt-s13255194368-d5935380940.bin.gz
637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5  b18c384nbt-humanv0.bin.gz
```

## 许可原文与适用范围

- [KataGo-Neural-Network-License.txt](KataGo-Neural-Network-License.txt)：从官方页面提取的网络许可正文，保留 David J Wu（lightvector）的原始版权及许可条款；提取方式与哈希见 [provenance.json](../provenance.json)。
- [network_license.html](network_license.html)：保存的完整官方页面，包含适用范围、例外与外部贡献模型说明。可与[当前官方页面](https://katagotraining.org/network_license/)核对。

官方许可允许使用、修改和分发其覆盖的权重，并要求随副本保留原始版权及许可。发布上述模型时应同时附带许可原文及来源记录，不用项目根目录的 MIT 文本替代。具体权利义务以原文为准。

官方页面另列 `g170`、`zhizi` 及外部贡献模型的区别；不能把当前两项的许可判断扩展到网站上的所有模型。更换或新增权重时，重新核对训练方、版本、来源和具体条款。

本目录不覆盖可选 Ollama 服务及其语言模型。通过同一客户端运行的不同语言模型仍须分别核对许可。本地安装包候选只收录上表两个 KataGo 模型，尚未批准公开分发。

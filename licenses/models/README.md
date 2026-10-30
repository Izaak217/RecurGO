# KataGo 模型许可索引

文档版本：v1.1.0.dev1；核实日期：2026-10-29。

当前 TF3 开发候选使用 `packaging/asset_lock.json` 固定两个模型的路径与 SHA-256，
随包保留官方网络许可。源码仓库不提交模型权重；权重许可与 RecurGO 自有源码的 MIT 分开。

| 文件 | 用途 | 官方来源与许可 |
| --- | --- | --- |
| `kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz` | TF3 客观分析、推荐、复盘与最强 AI | [官方 kata1 网络列表](https://katagotraining.org/networks/)，适用 KataGo Neural Network License |
| `b18c384nbt-humanv0.bin.gz` | 既有 Human SL 陪练档位 | [官方 Extra Networks](https://katagotraining.org/extra_networks/)中标为 KataGo Human SL Network 的模型，适用同一网络许可 |

```text
93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871  kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz
637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5  b18c384nbt-humanv0.bin.gz
```

TF3 散列在从官方 HTTPS 地址下载后本地计算，用于锁定当前文件，不是上游签名或独立版权证明。
下载来源、许可快照和散列记录见 [sources-tf3.json](sources-tf3.json)。Human SL 文件保持原有内容。

[官方许可页面](https://katagotraining.org/network_license/)将 kata1 官方网络和标为 KataGo 的 Human SL
网络纳入许可；另列 g170、zhizi 及外部贡献网络例外。这里仅判断上表两项，不扩展到任意下载的模型。
许可允许使用、修改、分发及商业销售，要求随副本保留版权与许可声明；具体条款以原文为准。

- [KataGo-Neural-Network-License.txt](KataGo-Neural-Network-License.txt)：原许可正文，保留 David J Wu 的版权。
  本次与 2026-10-29 官方快照去除排版空白后逐字一致，因此保留原文件，不改写许可。
- [network_license-2026-10-29.html](network_license-2026-10-29.html)：本次取得的完整官方网页，保留适用范围和例外。
- [network_license.html](network_license.html)及 [既有 provenance.json](../provenance.json)：历史来源记录，继续保留。

旧 `kata1-b28c512nbt-s13255194368-d5935380940.bin.gz` 不属于当前运行或打包模型清单。
更换模型仍需重新核对来源、许可、哈希和棋力；版本更新不能自行证明棋力提升。
当前候选的人工功能与棋力验收仍待完成，旧引擎测试不能转作 TF3 验收结果。

本目录不覆盖可选 Ollama 及其语言模型。不同模型仍须分别核对自身条款。

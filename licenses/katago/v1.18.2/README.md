# KataGo v1.18.2 CUDA 许可与来源

文档版本：v1.1.0.dev1；核对日期：2026-10-29。

本次目标是官方 `katago-v1.18.2-cuda12.8-cudnn9.8.0-windows-x64.zip` 标准构建，
引擎 revision 为 `fd0723fdbc0e9d82cf269c9630af8c27c57c07c4`。
安装包文件及 SHA-256 以项目 `packaging/asset_lock.json` 为准；本目录不是运行库目录。
许可原文从固定上游版本直接取得，文件散列、来源和版本核实方法见 [sources.json](sources.json)。
本地散列用于识别内容，不等于上游签名。

| 组件 | 原文及适用范围 |
| --- | --- |
| KataGo v1.18.2 | [LICENSE](LICENSE)、[CONTRIBUTORS](CONTRIBUTORS)；主体 MIT，第三方例外分别适用原许可 |
| cuDNN frontend，KataGo 固定副本 | [MIT 原文](cudnn-frontend-LICENSE.txt)；与 NVIDIA cuDNN 运行库的专有条款分开 |
| CUTLASS，KataGo 固定副本 | [BSD-3-Clause 原文](cutlass-LICENSE.txt)；该文件另明确 Python CuTeDSL 适用 NVIDIA EULA |
| OpenSSL 3.6.3 | [Apache-2.0 原文](openssl-3.6.3-LICENSE.txt)；`libcrypto-3-x64.dll` 和 `libssl-3-x64.dll` 的 PE 版本均为 3.6.3 |
| zlib 1.3.2 | [上游 README 与许可](zlib-1.3.2-README.txt)；`z.dll` 的 PE 版本为 1.3.2 |
| libzip 1.11.4 | [BSD-3-Clause 原文](libzip-1.11.4-LICENSE.txt)；`zip_libzip_version()` 返回 1.11.4 |
| bzip2 1.0.8 | [原始许可](bzip2-1.0.8-LICENSE)；`BZ2_bzlibVersion()` 返回 1.0.8，从官方源码包原样提取许可 |
| ghc filesystem、half、httplib、TCLAP | [filesystem](filesystem-LICENSE)、[half](half-LICENSE.txt)、[httplib](httplib-LICENSE)、[TCLAP](tclap-COPYING)；固定 KataGo tag 的原文 |
| SHA-2、nlohmann JSON | 保留 [sha2.cpp](sha2.cpp) 和 [完整 json.hpp](json.hpp) 中所有版权及嵌入许可 |
| Mozilla CA bundle | [上游说明](mozilla-cacerts-LICENSE)及既有 [完整 MPL-2.0](../mozilla-cacerts/MPL-2.0.txt)；随包证书仍标注 2020-07-22 数据 |

MIT、BSD 等许可材料必须随实际分发组件保留。不得将第三方作品标为 RecurGO 原创，
也不得使用第三方作者名称为产品背书。具体义务以原文为准。

CUDA 的构建文件接入 cuDNN frontend；CUTLASS fused FFN 带编译条件，MSVC 构建会排除该路径。
保存 CUTLASS 原文是保留上游资料，不表示当前 Windows 二进制必然启用了该优化。
本次不分发 CuTeDSL、其他后端的完整依赖或 KataGo 训练工具。
完整固定版本源码见 [KataGo v1.18.2](https://github.com/lightvector/KataGo/tree/v1.18.2)。

旧引擎附件 `libz.dll`、`libzip.dll` 不在本次白名单；本次为 `z.dll`、`zip.dll` 和新增 `bz2.dll`。
随官方 ZIP 附带的 Microsoft 运行库继续不从引擎目录打包，系统需提供兼容 x64 运行库。
NVIDIA CUDA、NVRTC、cuDNN 仍由用户单独准备，不随本候选分发；其专有许可不能被 frontend 的 MIT 许可替代。

上一级的 v1.16.5 资料仅保留为历史来源记录，不表示旧引擎继续随包安装。

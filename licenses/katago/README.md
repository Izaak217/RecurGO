# KataGo 与 Windows 引擎附属组件许可资料

资料版本：v0.1.4；核对日期：2026-09-25。

## v1.0.0 Windows 安装包

下文的“本次源码发布”记录的是此前源码仓库审计范围。当前源码仓库仍不提交
`runtime/` 二进制；Windows 安装包另按 `packaging/asset_lock.json` 中固定的 SHA-256
打包 KataGo 1.16.5 引擎、OpenSSL、zlib、libzip 和 CA 证书，随包复制本目录的原许可。
安装包不从本机引擎目录复制 `msvcp*` 或 `vcruntime*` DLL，独立检测工具要求系统
Visual C++ 运行库。Python/Qt/NumPy 上游依赖自带的同名文件见各自许可清单。

对应本机 KataGo **v1.16.5**，Git revision
`ba938676d7f42d70950b3a535af2466fb642008c`。
本目录保存第三方原始许可和承载许可声明的小型源码文件；这些材料保留原作者的授权，
不因本项目采用 MIT 而被重新授权。机器可读来源、SHA256 和核对依据见
[sources.json](sources.json)。

## 源码仓库与安装包的范围

源码仓库包含本目录的通知、原文、`json.hpp` 和 `sha2.cpp`，不包含
`runtime/engine/` 中的 EXE、DLL 或 CA 证书包。Windows 安装包另按
`packaging/asset_lock.json` 收录前述固定引擎文件；以下 DLL 版本来自本机 PE
版本资源，用于核对该版本。

更换安装包中的引擎或附属组件时，应按实际文件更新资料和清单。
不得仅凭本目录存在，就把任意版本的运行库加入发行包。

## 已保留的原文

| 组件与已确认版本 | 许可材料 | 核对依据 |
| --- | --- | --- |
| KataGo v1.16.5 | [LICENSE](LICENSE)、[CONTRIBUTORS](CONTRIBUTORS) | 固定 Git revision 的上游文件；主许可 MIT，并明确列出第三方例外 |
| OpenSSL 3.0.12 | [LICENSE.txt](openssl-3.0.12/LICENSE.txt)，Apache-2.0 | `libcrypto-3-x64.dll`、`libssl-3-x64.dll` 的 ProductVersion/FileVersion 均为 3.0.12 |
| zlib 1.2.13 | [README](zlib-1.2.13/README)，含完整 zlib 许可 | `libz.dll` 的 ProductVersion/FileVersion 为 1.2.13 |
| libzip 1.10.0 | [LICENSE](libzip-1.10.0/LICENSE)，BSD-3-Clause | `libzip.dll` 的 ProductVersion/FileVersion 为 1.10.0 |
| ghc filesystem 1.5.8 | [LICENSE](filesystem-1.5.8/LICENSE)，MIT | KataGo 固定 revision 的 `cpp/external/filesystem-1.5.8/` |
| half 2.2.0 | [LICENSE.txt](half-2.2.0/LICENSE.txt)，MIT | 同一 revision 实际保存的目录为 `cpp/external/half-2.2.0/` |
| cpp-httplib，KataGo 内置副本 | [LICENSE](httplib/LICENSE)，MIT | 以 KataGo revision 标识该副本，不推定未核实的独立版本号 |
| TCLAP 1.2.5 | [COPYING](tclap-1.2.5/COPYING)，MIT | KataGo 的 `cpp/external/tclap-1.2.5/` |
| SHA-2，KataGo 修改副本 | [sha2.cpp](sha2/sha2.cpp)，内嵌 BSD-3-Clause 原文 | 文件保留 Aaron D. Gifford 的版权与 David J Wu 的修改说明 |
| nlohmann JSON 3.8.0 | [完整 json.hpp](nlohmann_json-3.8.0/json.hpp) | 头文件版本宏及其中的全部许可、版权声明 |
| Mozilla CA bundle，2020-07-22 数据 | [原说明](mozilla-cacerts/LICENSE)、[完整 MPL 2.0](mozilla-cacerts/MPL-2.0.txt) | 本机 `cacert.pem` 文件头及 KataGo 固定 revision 的对应文本 |

上表中的内置头文件材料依据上游源码保存，不据此断言它们在每种后端或每项功能中均被使用。
KataGo 总 `LICENSE` 仍写 `half-2.1.0`，而固定 revision 的实际目录和已保留文件为
**half 2.2.0**；这里保留总 LICENSE 原文并说明差异。half 的独立原文采用 MIT，
没有附加许可证例外条款。

`json.hpp` 不只有文件顶部的 MIT 声明：它还保留 Hedley 的 CC0-1.0 声明、
Florian Loitsch 的 Grisu2 MIT 归属说明，以及 Bjoern Hoehrmann UTF-8 解码器的版权归属。
因此保留整个上游头文件，不用单行“MIT”替代这些通知。

## CA 证书与对应源码

本机 `runtime/engine/cacert.pem` 的完整文件 SHA256 为
`2782f0f8e89c786f40240fc1916677be660fb8d8e25dede50c9f6f7b0c2c2178`，
Git blob SHA1 为 `f9bd706b40dbad2ee2309b28279de3b24c81037a`，与
[KataGo 对应公开 PEM 文本](https://raw.githubusercontent.com/lightvector/KataGo/ba938676d7f42d70950b3a535af2466fb642008c/cpp/external/mozilla-cacerts/cacert.pem)
完全一致。文件头自带的另一条 `SHA256` 注释不是这里计算的整个文件散列，不能混用。
原说明指向 curl 的 CA 提取流程和 Mozilla MPL 2.0；v1.0.0 安装包收录该证书文件及本目录的许可资料。

`MPL-2.0.txt` 从本项目已有的 pathspec 1.1.1 许可副本逐字节复制，含第 1–10 节及
Exhibit A、B。此处仅复用完整标准许可正文，不把 pathspec 认定为 KataGo 依赖。
[Mozilla 官方许可正文](https://www.mozilla.org/en-US/MPL/2.0/)可用于对照。

完整 KataGo 源码对应
[固定 revision](https://github.com/lightvector/KataGo/tree/ba938676d7f42d70950b3a535af2466fb642008c)。
OpenSSL、zlib、libzip 的对应版本源码与原文链接列在 `sources.json`；本目录没有完整镜像
这些库。若后续实际分发 CA 数据或修改过的组件，应将实际对应的源码与获取说明纳入该次
发行资料，不能把本次源码发布的记录当作另一版本二进制包的清单。

## Microsoft Visual C++ 运行库

本机以下七个文件的 ProductVersion/FileVersion 均为 **14.34.31938.0**：
`msvcp140.dll`、`msvcp140_1.dll`、`msvcp140_2.dll`、`msvcp140_atomic_wait.dll`、
`msvcp140_codecvt_ids.dll`、`vcruntime140.dll`、`vcruntime140_1.dll`。
**v1.0.0 安装包不从 KataGo 引擎目录复制或打包这七个 DLL**；它们不是本项目 MIT 许可覆盖的组件。Python、Qt 和 NumPy 上游包另带有同名或同类运行库，其原始条款和来源见随包资料。

官方资料分别说明运行时使用条款和开发工具/可再分发代码的授权依据：

- [Visual C++ Runtime 2015–2022 条款](https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/)。
- [Visual Studio 2022 Diagnostic Build Tools 条款](https://visualstudio.microsoft.com/license-terms/vs2022-ga-diagnosticbuildtools/)，以及适用于实际取得方式的 [Visual Studio 许可目录](https://visualstudio.microsoft.com/license-terms/)。
- [Microsoft 再分发说明](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)与 [Visual Studio 2022 可再分发文件清单](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)。

运行时使用条款不替代二进制再分发依据。随包上游依赖运行库须遵守适用的 Microsoft 条款；
本项目记录了原文和官方许可目录，KataGo 引擎目录不复制这些文件。

## 其他后端的范围

CLBlast 属于需要在采用 OpenCL 后端时另行核对的上游组件；这里不宣称当前 CUDA
引擎使用了 CLBlast，也没有把它加入当前已确认 DLL 清单。此目录不包含 macOS/CoreML
组件材料。NVIDIA、Python、Qt 和模型的资料分别放在同级对应目录。

## 校验方式

既有 10 份第三方文件与 KataGo 主 LICENSE、CONTRIBUTORS 均保留原字节。
逐项计算本地 SHA256，并用 Git blob 的 `SHA1("blob " + 长度 + NUL + 文件内容)`
与对应官方仓库文件对象核对；这同时核对来源文件内容，区别于只检查 URL 能打开。
MPL 正文与本地原副本的 SHA256 一致。具体散列、固定来源路径和核对状态保存在
`sources.json`。

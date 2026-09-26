# Qt 6.11.1 随包第三方声明

本目录集中保存 v1.0.0 Windows 安装包中可识别的 Qt 第三方组件声明，不给每个 DLL 重复放一份许可证。RecurGO 的 MIT 许可不替代下列原始条款。

| 安装包中的文件 | 上游组件 | 随附声明 |
| --- | --- | --- |
| `PySide6/opengl32sw.dll` | Mesa llvmpipe | [MIT 原文](MIT.txt)、[Boost 1.0 原文](BSL-1.0.txt)；版权声明见下方及 [Qt 官方归属页](https://doc.qt.io/qt-6/qt-attribution-llvmpipe.html)。 |
| `PySide6/plugins/imageformats/qjpeg.dll` | libjpeg-turbo / IJG | [COPYRIGHT](libjpeg-COPYRIGHT.txt)、[LICENSE](libjpeg-LICENSE)、[IJG 条款](libjpeg-ijg-license.txt)。 |
| `PySide6/plugins/imageformats/qtiff.dll` | libtiff | [COPYRIGHT 与许可](libtiff-COPYRIGHT)。 |
| `PySide6/plugins/imageformats/qwebp.dll` | libwebp | [COPYING](libwebp-COPYING)。 |

Mesa llvmpipe 的随包版权声明：Copyright (C) 1999-2007 Brian Paul；Copyright (c) 2013-2016 The Khronos Group Inc.；C11 `<threads.h>` emulation library: (C) Copyright yohhoy 2012。适用的 MIT 与 Boost 1.0 许可原文见上表。

上述七份原文保持 Qt 6.11.1 官方源码归档中的原始字节。`qtbase-everywhere-src-6.11.1.tar.xz` 的官方 SHA-256 为 `d9594a31228aa23ad6b531719a29b45f0f3989fe6c136d45767ea179f233c1ac`；`qtimageformats-everywhere-src-6.11.1.tar.xz` 为 `b2bf6c6845ac175ed7f819145483ba4676f617aaa6a5012c8efee63c8bbac413`。[固定版本官方源码目录](https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/)

Qt Core、Gui 等模块还可能内含其他上游代码；对应归属资料保留在随包的 [Qt 6.11.1 上游索引](../upstream/README.md)，并可对照 [Qt 官方第三方许可目录](https://doc.qt.io/qt-6/licenses-used-in-qt.html)。本表只列出四个已逐文件对照的插件；其余模块不应仅凭本表判断许可范围。更换 Qt 版本或构建配置时须重新核对。

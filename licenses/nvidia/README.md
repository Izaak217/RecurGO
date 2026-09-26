# NVIDIA 许可资料与版本差异

文档版本：v0.1.2；核实日期：2026-09-23。

当前运行配置使用 CUDA 12.8 系列路径及本地 `nvidia-cudnn-cu12 9.8.0.87`。cuDNN 安装元数据将其声明为 NVIDIA 专有软件；项目源码的 MIT 许可不替代 NVIDIA 的协议。本目录保存协议资料，尚不是允许直接发布整个 CUDA/cuDNN 目录的结论。

## 原文与来源

| 文件 | 来源与版本依据 |
| --- | --- |
| [cudnn-9.8.0.87-package-License.txt](cudnn-9.8.0.87-package-License.txt) | 从本地 `runtime/cuda_deps/nvidia_cudnn_cu12-9.8.0.87.dist-info/License.txt` 原样复制；安装包版本为 9.8.0.87，但文内协议及补充条款标注 2020-01-28。 |
| [cudnn-9.8.0-eula.html](cudnn-9.8.0-eula.html) | [NVIDIA cuDNN 9.8.0 官方协议](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.8.0/reference/eula.html)快照；页面更新日期为 2025-03-06，cuDNN 补充条款标注 2022-02-22。 |
| [cuda-12.8.0-eula.html](cuda-12.8.0-eula.html) | [NVIDIA CUDA Toolkit 12.8.0 官方协议](https://docs.nvidia.com/cuda/archive/12.8.0/eula/index.html)快照，文内更新日期为 2025-01-07。该文件不能独自证明将来包内每个 DLL 的实际版本。 |

下载来源、复制来源和 SHA-256 已记录在 [provenance.json](../provenance.json)。本次重新核对了这三个原文文件的哈希，没有修改或替换条款。

## cuDNN 两份文本为何都保留

本地包附带的旧文本在分发清单中列出 `.so`、`.h`、`cudnn64_7.dll` 和 `cudnn.lib`；cuDNN 9.8.0 官方页面的补充条款则列出运行时 `.so` 和 `.dll`。旧文本出现版本 7 的 DLL 名称，与当前 9.8.0.87 包并不对应，差异是原始材料本身存在的事实。

因此保留两份原文及其来源，不擅自改旧文件的版本号，也不在本项目文档中自行裁定哪份协议全面替代另一份。9.8 官方页面为当前版本提供了更直接的材料，但实际再分发仍需核对所取得软件的适用协议、补充条款及单独组件声明；必要时向 NVIDIA 澄清差异。

## 二进制发行前仍需核对

- 逐项列出实际携带的 CUDA、cuDNN、cuBLAS 等 DLL、版本、来源及校验和，对照相应协议的可分发清单和条件。cuDNN 的安装元数据还声明依赖 `nvidia-cublas-cu12`，不能只看 cuDNN 自身的许可文本。
- 保留相关版权、协议及第三方声明；未确认可分发的开发工具、头文件或其他组件不自动纳入发行包。
- 如由用户自行安装 NVIDIA 运行库，应提供对应官方来源及所需版本说明；如果由项目随包提供，则另行完成该发行方式的材料与条件核对。

这些事项不影响公开项目自有源码，但本目录不宣称已完成 NVIDIA 二进制再分发核查。详细权利义务以所适用的原始协议为准。

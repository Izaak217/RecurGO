# Third-party components and licenses

English | [简体中文](THIRD_PARTY_NOTICES.md)

RecurGO-owned code uses the root [MIT License](LICENSE). Third-party components keep their original licenses; the entire runtime directory is not covered by RecurGO's MIT license. This indexes source-repository materials and the v1.0.0 Windows installer. The build writes a separate `file-manifest.json` of actual contents; review it again when dependencies or packaging change.

| Component | Current scope | Records |
| --- | --- | --- |
| KataGo 1.16.5 | CUDA engine in the installer; MIT plus upstream third-party terms | [Engine and bundled components](licenses/katago/README.md), [sources and checksums](licenses/katago/sources.json) |
| Official KataGo main model and Human SL | Both models in the installer; official network license, copyright and license retained | [Models and scope](licenses/models/README.md), [original network license](licenses/models/KataGo-Neural-Network-License.txt) |
| Python dependencies, interpreter, packaged runtime | Their own terms, including third-party material within wheels | [Python license inventory](licenses/python/README.md) |
| PySide6, Shiboken6, Qt 6.11.1 | LGPLv3 route for applicable modules; bundled third-party material is indexed together | [Qt licenses and corresponding source notes](licenses/qt/README.md), [identified plugin notices](licenses/qt/third_party/README.md), [original upstream attributions](licenses/qt/upstream/README.md) |
| NVIDIA cuDNN / CUDA | Proprietary agreements, not replaced by RecurGO's MIT license | [Versions, original agreements, and distinctions](licenses/nvidia/README.md) |
| Ollama 0.34.3 | External local inference service, not bundled as a Python dependency | [MIT License](https://github.com/ollama/ollama/blob/v0.34.3/LICENSE), [local service guide](docs/OLLAMA_LOCAL.en.md) |
| Qwen3 4B Instruct 2507 | Locally selected language model; its license is separate from Ollama's | [Official model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [selected tag license](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) |

Bundled engine components such as OpenSSL, zlib, and libzip remain subject to their own terms. The installer does not copy developer-machine Microsoft Visual C++ DLLs into KataGo's engine directory; it requires the system runtime. Upstream Python, Qt, and NumPy packages contain other Visual C++ runtime DLLs. Their origins and [Microsoft's redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170) are recorded in the release review. The Qt notes describe fixed-version source and shared-library replacement. The installer excludes unused Qt PDF, Qt FFmpeg, and OpenCV video plugins. Downloaded Ollama files, models, caches, secrets, and personal games are not RecurGO-owned source or part of the installer.

Ollama's MIT license does not mean every optional model uses MIT. Check the license of any model you choose. If external components are bundled in a future release, provide the materials required for the actual versions included.

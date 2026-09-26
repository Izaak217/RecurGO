"""Supported application languages and explicit bilingual message selection."""

from __future__ import annotations

from typing import Literal

Language = Literal["zh", "en"]


def normalize_language(value: object) -> Language:
    return "zh" if value == "zh" else "en"


def tr(language: Language, chinese: str, english: str) -> str:
    return english if language == "en" else chinese


_ERROR_TRANSLATIONS = (
    ("缺少 KataGo 运行清单", "Missing KataGo runtime manifest"),
    (
        "请按《安装指南》或《源码启动说明》补齐 KataGo 文件",
        "Add the KataGo files as described in the setup guide",
    ),
    ("分析环境缺少以下项目", "The analysis environment is missing these items"),
    (
        "请按《安装指南》或《源码启动说明》补齐；CUDA/cuDNN 路径可在独立检测工具中指定",
        "Add them using the setup guide; CUDA/cuDNN paths can be set in the standalone checker",
    ),
    ("KataGo返回了无法解析的数据", "KataGo returned unparseable data"),
    ("分析请求被拒绝", "Analysis request rejected"),
    ("KataGo意外退出，代码", "KataGo exited unexpectedly, code"),
    ("可以重试启动或关闭分析", "Retry startup or close analysis"),
    ("KataGo进程错误", "KataGo process error"),
    ("KataGo启动或模型加载超时", "KataGo startup or model loading timed out"),
    ("请检查显卡、模型和配置后重试", "Check the GPU, model, and configuration, then retry"),
    (
        "KataGo分析长时间没有返回数据，已停止本次请求",
        "KataGo returned no data for too long; this request was stopped",
    ),
    ("可以重试或关闭分析", "Retry or close analysis"),
    ("未知进程错误", "Unknown process error"),
    ("（字段：", " (field: "),
    ("KataGo 引擎文件：", "KataGo engine file: "),
    ("KataGo 分析模型文件：", "KataGo analysis model file: "),
    ("KataGo Human SL 模型文件：", "KataGo Human SL model file: "),
    ("KataGo 分析配置文件：", "KataGo analysis configuration file: "),
    ("CUDA bin 文件夹：", "CUDA bin folder: "),
    ("cuDNN bin 文件夹：", "cuDNN bin folder: "),
    ("CUDA 运行库 ", "CUDA runtime library "),
    ("cuDNN 运行库 ", "cuDNN runtime library "),
    ("无法读取图片", "Could not read image"),
    ("图片格式无效或文件已经损坏", "Invalid or damaged image"),
    ("识别输入必须是彩色图片", "The input must be a color image"),
    (
        "图片分辨率过低，棋盘短边至少需要 160 像素",
        "Image resolution is too low; the shorter board edge needs at least 160 pixels",
    ),
    ("仅支持 9 路、13 路和 19 路棋盘", "Only 9×9, 13×13, and 19×19 boards are supported"),
    (
        "OpenCV 尚未安装，图片识谱功能暂不可用",
        "OpenCV is not installed; image recognition is unavailable",
    ),
    ("没有可用的棋盘角点", "No usable board corners"),
    ("棋盘角点必须恰好为四个", "Exactly four board corners are required"),
    (
        "选择的棋盘区域过小或四个角点顺序无效",
        "Selected board area is too small or the corners are in an invalid order",
    ),
    (
        "未能自动定位棋盘，请手动点击棋盘的四个角",
        "Could not locate the board automatically; select its four corners",
    ),
    (
        "直线检测结果格式异常，请手动点击棋盘的四个角",
        "Line detection returned an invalid result; select the four board corners",
    ),
    (
        "未能自动定位完整网格，请手动点击棋盘的四个角",
        "Could not locate the full grid automatically; select the four board corners",
    ),
    (
        "检测到的棋盘区域过小，请手动选择四个角",
        "Detected board area is too small; select four corners manually",
    ),
    (
        "网格线不够清晰，请手动选择棋盘四角并指定路数",
        "Grid lines are unclear; select four board corners and set the board size",
    ),
    ("Ollama 地址必须是本机 HTTP 地址", "Ollama address must be a local HTTP address"),
    (
        "Ollama 地址不能为空或包含空白字符",
        "Ollama address cannot be empty or contain whitespace",
    ),
    ("Ollama 地址或端口格式不正确", "Invalid Ollama address or port"),
    ("仅允许本机 HTTP 根地址", "Only a local HTTP root address is allowed"),
    (
        "不允许外部地址、用户名、路径、查询参数或片段",
        "External addresses, usernames, paths, queries, and fragments are not allowed",
    ),
    ("请选择已安装的本地 Ollama 模型", "Select an installed local Ollama model"),
    (
        "Ollama 模型名称不能为空或包含空白字符",
        "Ollama model name cannot be empty or contain whitespace",
    ),
    (
        "不允许使用云端模型；请选择已安装的本地模型",
        "Cloud models are not allowed; select an installed local model",
    ),
    ("Ollama 启用状态必须是布尔值", "Ollama enabled state must be boolean"),
    (
        "Ollama 响应过大，已停止读取；请缩短解释内容",
        "Ollama response was too large and reading stopped; shorten the explanation",
    ),
    (
        "Ollama 流式响应单行过大，已停止读取",
        "An Ollama response line was too large; reading stopped",
    ),
    ("Ollama 在完成标记后仍返回了额外数据", "Ollama returned extra data after completion"),
    ("Ollama 返回了无效的流式 JSON 响应", "Ollama returned invalid streaming JSON"),
    ("Ollama 流式响应的数据格式不正确", "Ollama streaming response has an invalid format"),
    ("Ollama 返回错误", "Ollama returned an error"),
    (
        "Ollama 解释达到输出长度上限，文字已被截断",
        "Ollama explanation reached the output limit and was truncated",
    ),
    (
        "请参考即时规则说明，或缩短解释后重试",
        "Use the immediate rules explanation or retry with a shorter explanation",
    ),
    (
        "Ollama 流式响应缺少有效的文字或完成状态",
        "Ollama stream has no valid text or completion state",
    ),
    (
        "本机 Ollama 返回了重定向；为避免连接外部服务，已拒绝",
        "Local Ollama returned a redirect, which was rejected to avoid an external connection",
    ),
    ("Ollama 请求失败", "Ollama request failed"),
    (
        "未找到模型或接口，请确认模型已安装、地址正确",
        "Model or API not found; check the installed model and address",
    ),
    (
        "无法完成本机 Ollama 请求，请确认服务已启动、地址和端口正确",
        "Could not complete the local Ollama request; check that the service is running and the address and port are correct",
    ),
    ("也可能是连接中断或请求超时", "The connection may also have dropped or timed out"),
    ("Ollama 返回了无效或空的 JSON 响应", "Ollama returned invalid or empty JSON"),
    ("Ollama 返回的数据格式不正确", "Ollama returned an invalid data format"),
    ("Ollama 模型列表格式不正确", "Ollama model list has an invalid format"),
    ("Ollama 模型列表包含无效记录", "Ollama model list contains an invalid entry"),
    ("Ollama 模型列表包含无效模型名称", "Ollama model list contains an invalid model name"),
    (
        "Ollama 未返回模型信息，无法确认本地模型",
        "Ollama did not return model information; locality cannot be confirmed",
    ),
    (
        "该模型指向远程或云端服务，已拒绝；请选择本地模型",
        "This model points to a remote or cloud service and was rejected; select a local model",
    ),
    (
        "该模型无法确认支持关闭思考模式；请选择本地非思考模型",
        "This model cannot be confirmed to support disabling thinking; select a local non-thinking model",
    ),
    (
        "Ollama 未返回完整的文字解释，请重试或选择其他本地模型",
        "Ollama did not return a complete explanation; retry or select another local model",
    ),
    ("Ollama 生成解释超时", "Ollama explanation timed out"),
    ("Ollama 读取模型信息超时", "Ollama model information request timed out"),
    ("请确认服务和模型可用后重试", "Check the service and model, then retry"),
)


def localize_error(message: str, language: Language) -> str:
    """Translate known application errors while retaining raw external diagnostics."""
    if language != "en":
        return message
    for chinese, english in _ERROR_TRANSLATIONS:
        message = message.replace(chinese, english)
    return message

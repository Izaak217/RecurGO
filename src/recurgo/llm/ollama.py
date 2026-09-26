"""Asynchronous, loopback-only Ollama transport with cancellable requests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxy,
    QNetworkReply,
    QNetworkRequest,
)

from .settings import normalize_base_url, validate_model

Stage = Literal["tags", "show", "chat"]


@dataclass(slots=True)
class _Request:
    base_url: str
    stage: Stage
    timer: QTimer
    model: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    reply: QNetworkReply | None = None
    body: bytearray = field(default_factory=bytearray)
    disable_thinking: bool = False
    received_bytes: int = 0
    explanation: str = ""
    stream_done: bool = False


def _is_remote(payload: object) -> bool:
    pending = [payload]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in {"remote_host", "remote_model", "remote", "cloud"} and value:
                    return True
                if key in {"name", "model"} and isinstance(value, str):
                    if ":cloud" in value.lower() or "-cloud" in value.lower():
                        return True
                if isinstance(value, (dict, list)):
                    pending.append(value)
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _messages_copy(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("Ollama 解释请求必须包含非空消息列表。")
    result: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Ollama 消息格式不正确。")
        role = message.get("role")
        content = message.get("content")
        if (
            not isinstance(role, str)
            or role not in {"system", "user", "assistant"}
            or not isinstance(content, str)
        ):
            raise ValueError("Ollama 消息必须包含合法角色和文字内容。")
        if not content.strip():
            raise ValueError("Ollama 消息内容不能为空。")
        result.append({"role": role, "content": content})
    return result


class OllamaClient(QObject):
    models_ready = Signal(str, object)
    explanation_partial = Signal(str, str)
    explanation_ready = Signal(str, str)
    request_failed = Signal(str, str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        models_timeout_ms: int = 10_000,
        chat_timeout_ms: int = 180_000,
        max_response_bytes: int = 1_048_576,
        max_line_bytes: int = 262_144,
    ) -> None:
        super().__init__(parent)
        if min(models_timeout_ms, chat_timeout_ms, max_response_bytes, max_line_bytes) <= 0:
            raise ValueError("Ollama 超时时间和响应大小限制必须大于零。")
        self._models_timeout_ms = models_timeout_ms
        self._chat_timeout_ms = chat_timeout_ms
        self._max_response_bytes = max_response_bytes
        self._max_line_bytes = min(max_line_bytes, max_response_bytes)
        self._network = QNetworkAccessManager(self)
        self._network.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self._requests: dict[str, _Request] = {}
        self._closed = False

    def list_models(self, base_url: str) -> str:
        normalized = normalize_base_url(base_url)
        self._check_open()
        request_id = self._new_request(normalized, "tags")
        self._send(request_id)
        return request_id

    def generate(
        self, base_url: str, model: str, messages: list[dict[str, str]]
    ) -> str:
        normalized = normalize_base_url(base_url)
        local_model = validate_model(model)
        safe_messages = _messages_copy(messages)
        self._check_open()
        request_id = self._new_request(normalized, "show")
        context = self._requests[request_id]
        context.model = local_model
        context.messages = safe_messages
        self._send(request_id)
        return request_id

    def cancel(self, request_id: str | None = None) -> None:
        ids = list(self._requests) if request_id is None else [request_id]
        for current_id in ids:
            self._dispose(current_id, abort=True)

    def shutdown(self) -> None:
        self._closed = True
        self.cancel()

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("Ollama 客户端已关闭。")

    def _new_request(self, base_url: str, stage: Stage) -> str:
        request_id = f"ollama-{uuid4()}"
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._timed_out(request_id))
        self._requests[request_id] = _Request(base_url, stage, timer)
        return request_id

    def _send(self, request_id: str) -> None:
        context = self._requests[request_id]
        request = QNetworkRequest(QUrl(f"{context.base_url}/api/{context.stage}"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(QByteArray(b"Accept"), QByteArray(b"application/json"))
        timeout = (
            self._chat_timeout_ms if context.stage == "chat" else self._models_timeout_ms
        )
        request.setTransferTimeout(timeout)
        context.body.clear()
        context.received_bytes = 0
        if context.stage == "tags":
            reply = self._network.get(request)
        else:
            data: dict[str, object] = {"model": context.model}
            if context.stage == "chat":
                data.update(
                    {
                        "messages": context.messages,
                        "stream": True,
                        "keep_alive": 0,
                        "options": {
                            "num_ctx": 4096,
                            "num_predict": 768,
                            "temperature": 0.2,
                        },
                    }
                )
                if context.disable_thinking:
                    data["think"] = False
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            reply = self._network.post(request, QByteArray(body))
        context.reply = reply
        reply.setReadBufferSize(self._max_response_bytes + 1)
        reply.readyRead.connect(lambda: self._read_available(request_id, reply))
        reply.metaDataChanged.connect(lambda: self._check_size(request_id, reply))
        reply.finished.connect(lambda: self._finished(request_id, reply))
        context.timer.start(timeout)

    def _check_size(self, request_id: str, reply: QNetworkReply) -> None:
        context = self._requests.get(request_id)
        if context is None or context.reply is not reply:
            return
        length = reply.header(QNetworkRequest.KnownHeaders.ContentLengthHeader)
        if isinstance(length, int) and length > self._max_response_bytes:
            self._fail(request_id, "Ollama 响应过大，已停止读取；请缩短解释内容。")

    def _read_available(self, request_id: str, reply: QNetworkReply) -> bool:
        context = self._requests.get(request_id)
        if context is None or context.reply is not reply:
            return False
        chunk = reply.readAll().data()
        context.received_bytes += len(chunk)
        if context.received_bytes > self._max_response_bytes:
            self._fail(request_id, "Ollama 响应过大，已停止读取；请缩短解释内容。")
            return False
        context.body.extend(chunk)
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if context.stage == "chat" and isinstance(status, int) and 200 <= status < 300:
            return self._read_stream(request_id)
        return True

    def _read_stream(self, request_id: str, *, eof: bool = False) -> bool:
        context = self._requests.get(request_id)
        if context is None:
            return False
        while True:
            newline = context.body.find(b"\n")
            if newline < 0:
                if len(context.body) > self._max_line_bytes:
                    self._fail(request_id, "Ollama 流式响应单行过大，已停止读取。")
                    return False
                if not eof or not context.body:
                    return True
                newline = len(context.body)
            if newline > self._max_line_bytes:
                self._fail(request_id, "Ollama 流式响应单行过大，已停止读取。")
                return False
            line = bytes(context.body[:newline]).strip()
            del context.body[: newline + 1]
            if not line:
                continue
            if context.stream_done:
                self._fail(request_id, "Ollama 在完成标记后仍返回了额外数据。")
                return False
            try:
                payload: object = json.loads(line)
            except (ValueError, UnicodeDecodeError, RecursionError):
                self._fail(request_id, "Ollama 返回了无效的流式 JSON 响应。")
                return False
            if not isinstance(payload, dict):
                self._fail(request_id, "Ollama 流式响应的数据格式不正确。")
                return False
            if payload.get("error"):
                self._fail(request_id, f"Ollama 返回错误：{str(payload['error'])[:300]}")
                return False
            if payload.get("done") is True and payload.get("done_reason") == "length":
                self._fail(
                    request_id,
                    "Ollama 解释达到输出长度上限，文字已被截断；"
                    "请参考即时规则说明，或缩短解释后重试。",
                )
                return False
            message = payload.get("message")
            content = message.get("content", "") if isinstance(message, dict) else ""
            if not isinstance(content, str) or not isinstance(payload.get("done"), bool):
                self._fail(request_id, "Ollama 流式响应缺少有效的文字或完成状态。")
                return False
            context.stream_done = payload.get("done") is True
            if content:
                context.explanation += content
                self.explanation_partial.emit(request_id, context.explanation)
                if self._requests.get(request_id) is not context:
                    return False

    def _finished(self, request_id: str, reply: QNetworkReply) -> None:
        if not self._read_available(request_id, reply):
            return
        context = self._requests[request_id]
        context.timer.stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if isinstance(status, int) and 300 <= status < 400:
            self._fail(request_id, "本机 Ollama 返回了重定向；为避免连接外部服务，已拒绝。")
            return
        if isinstance(status, int) and status >= 400:
            detail = self._error_detail(context.body)
            message = f"Ollama 请求失败（HTTP {status}）"
            if status == 404:
                message += "：未找到模型或接口，请确认模型已安装、地址正确。"
            elif detail:
                message += f"：{detail}"
            self._fail(request_id, message)
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._fail(
                request_id,
                "无法完成本机 Ollama 请求，请确认服务已启动、地址和端口正确；"
                "也可能是连接中断或请求超时。",
            )
            return
        if context.stage == "chat":
            if self._read_stream(request_id, eof=True):
                self._complete_explanation(request_id)
            return
        try:
            payload: object = json.loads(context.body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            self._fail(request_id, "Ollama 返回了无效或空的 JSON 响应。")
            return
        if not isinstance(payload, dict):
            self._fail(request_id, "Ollama 返回的数据格式不正确。")
            return
        if payload.get("error"):
            self._fail(request_id, f"Ollama 返回错误：{str(payload['error'])[:300]}")
            return
        if context.stage == "tags":
            self._complete_models(request_id, payload)
        elif context.stage == "show":
            self._model_checked(request_id, payload)

    def _complete_models(self, request_id: str, payload: dict[str, object]) -> None:
        models = payload.get("models")
        if not isinstance(models, list):
            self._fail(request_id, "Ollama 模型列表格式不正确。")
            return
        names: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                self._fail(request_id, "Ollama 模型列表包含无效记录。")
                return
            name = model.get("name", model.get("model"))
            if not isinstance(name, str) or not name.strip():
                self._fail(request_id, "Ollama 模型列表包含无效模型名称。")
                return
            if _is_remote(model):
                continue
            try:
                name = validate_model(name)
            except ValueError:
                continue
            if name not in names:
                names.append(name)
        self._dispose(request_id)
        self.models_ready.emit(request_id, names)

    def _model_checked(self, request_id: str, payload: dict[str, object]) -> None:
        if not payload:
            self._fail(request_id, "Ollama 未返回模型信息，无法确认本地模型。")
            return
        if _is_remote(payload):
            self._fail(request_id, "该模型指向远程或云端服务，已拒绝；请选择本地模型。")
            return
        context = self._requests[request_id]
        thinking = payload.get("thinking")
        values = thinking.get("values") if isinstance(thinking, dict) else None
        supports_false = isinstance(values, list) and any(value is False for value in values)
        capabilities = payload.get("capabilities")
        has_thinking = (
            isinstance(capabilities, list) and "thinking" in capabilities
        ) or thinking is not None
        # Ollama 0.34.3 reports this local Instruct model as thinking-capable,
        # but /api/show omits thinking.values. Its /api/chat accepts think=false.
        # Reject only an explicit advertised list that excludes false; otherwise
        # ask the local API to disable thinking and let it report any unsupported flag.
        if has_thinking and isinstance(values, list) and not supports_false:
            self._fail(
                request_id,
                "该模型无法确认支持关闭思考模式；请选择本地非思考模型，"
                "例如 qwen3:4b-instruct-2507-q4_K_M。",
            )
            return
        context.disable_thinking = has_thinking
        if context.reply is not None:
            context.reply.deleteLater()
        context.reply = None
        context.stage = "chat"
        self._send(request_id)

    def _complete_explanation(self, request_id: str) -> None:
        context = self._requests[request_id]
        content = context.explanation.strip()
        if not context.stream_done or not content:
            self._fail(request_id, "Ollama 未返回完整的文字解释，请重试或选择其他本地模型。")
            return
        self._dispose(request_id)
        self.explanation_ready.emit(request_id, content)

    @staticmethod
    def _error_detail(body: bytearray) -> str:
        try:
            payload: object = json.loads(body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            return ""
        if isinstance(payload, dict) and isinstance(payload.get("error"), str):
            return str(payload["error"])[:300]
        return ""

    def _timed_out(self, request_id: str) -> None:
        context = self._requests.get(request_id)
        if context is None:
            return
        action = "生成解释" if context.stage == "chat" else "读取模型信息"
        self._fail(request_id, f"Ollama {action}超时，请确认服务和模型可用后重试。")

    def _fail(self, request_id: str, message: str) -> None:
        if self._dispose(request_id, abort=True):
            self.request_failed.emit(request_id, message)

    def _dispose(self, request_id: str, *, abort: bool = False) -> bool:
        context = self._requests.pop(request_id, None)
        if context is None:
            return False
        context.timer.stop()
        context.timer.deleteLater()
        if context.reply is not None:
            if abort and not context.reply.isFinished():
                reply = context.reply
                # Qt can still be delivering response metadata/body in this call stack.
                # Retire the request now, then abort after the network callback returns.
                QTimer.singleShot(0, self, lambda: self._abort_reply(reply))
            else:
                context.reply.deleteLater()
        return True

    @staticmethod
    def _abort_reply(reply: QNetworkReply) -> None:
        if not reply.isFinished():
            reply.abort()
        reply.deleteLater()

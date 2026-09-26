from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QNetworkProxy
from pytestqt.qtbot import QtBot

from recurgo.llm import OllamaClient, OllamaSettings


@dataclass
class Response:
    payload: object = field(default_factory=dict)
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    raw: bytes | None = None
    delay: float = 0
    send_length: bool = True
    chunks: list[bytes] | None = None
    chunk_delay: float = 0.01


class LocalOllama:
    def __init__(self) -> None:
        self.routes: dict[str, Response] = {
            "/api/tags": Response({"models": [{"name": "local:4b"}]}),
            "/api/show": Response({"details": {"family": "qwen3"}}),
            "/api/chat": Response({"message": {"content": "连接两块棋。"}, "done": True}),
        }
        self.calls: list[tuple[str, object]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.respond()

            def do_POST(self) -> None:
                self.respond()

            def respond(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body: object = json.loads(self.rfile.read(length)) if length else None
                owner.calls.append((self.path, body))
                response = owner.routes.get(self.path, Response(status=404))
                if response.delay:
                    time.sleep(response.delay)
                data = (
                    response.raw
                    if response.raw is not None
                    else json.dumps(response.payload, ensure_ascii=False).encode("utf-8")
                )
                if response.chunks is not None:
                    data = b"".join(response.chunks)
                try:
                    self.send_response(response.status)
                    self.send_header("Content-Type", "application/json")
                    if response.send_length:
                        self.send_header("Content-Length", str(len(data)))
                    for key, value in response.headers.items():
                        self.send_header(key, value)
                    self.end_headers()
                    if response.chunks is None:
                        self.wfile.write(data)
                    else:
                        for chunk in response.chunks:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                            time.sleep(response.chunk_delay)
                except OSError:
                    pass

            def log_message(self, _format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


@pytest.fixture
def server() -> Iterator[LocalOllama]:
    instance = LocalOllama()
    yield instance
    instance.close()


@pytest.fixture
def client(qtbot: QtBot) -> Iterator[OllamaClient]:
    instance = OllamaClient(QCoreApplication.instance())
    yield instance
    instance.shutdown()
    instance.deleteLater()


def messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "解释已核实棋形。"},
        {"role": "user", "content": "D4"},
    ]


def test_settings_round_trip_and_normalize_localhost() -> None:
    value = OllamaSettings(
        enabled=True, base_url=" http://localhost:11434/ ", model=" local:4b "
    )
    assert value.base_url == "http://127.0.0.1:11434"
    assert value.model == "local:4b"
    assert OllamaSettings.from_mapping(value.to_mapping()) == value
    assert OllamaSettings(base_url="http://[::1]:11434/").base_url == "http://[::1]:11434"


@pytest.mark.parametrize(
    "raw",
    [None, {"enabled": "false"}, {"base_url": "https://example.com"}, {"model": "x:cloud"}],
)
def test_corrupt_saved_settings_disable_service(raw: dict[str, object] | None) -> None:
    assert OllamaSettings.from_mapping(raw) == OllamaSettings()


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://192.168.1.5:11434",
        "http://127.0.0.1.example.com",
        "http://127.1",
        "http://user@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1:11434/?x=1",
        "http://127.0.0.1:11434/?",
        "http://127.0.0.1:11434/#",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
        "http://localhost:",
        "http://127.0.\n0.1:11434",
    ],
)
def test_invalid_endpoint_is_rejected_before_network(client: OllamaClient, url: str) -> None:
    with pytest.raises(ValueError):
        client.list_models(url)
    with pytest.raises(ValueError):
        client.generate(url, "local:4b", messages())


@pytest.mark.parametrize("model", ["", "x:cloud", "x-cloud:latest", "local model"])
def test_cloud_or_invalid_model_is_rejected_before_network(
    client: OllamaClient, server: LocalOllama, model: str
) -> None:
    with pytest.raises(ValueError):
        client.generate(server.url, model, messages())
    assert server.calls == []


@pytest.mark.parametrize(
    "value",
    [[], [{"role": "tool", "content": "x"}], [{"role": "user", "content": " "}]],
)
def test_invalid_messages_are_rejected_before_network(
    client: OllamaClient, server: LocalOllama, value: list[dict[str, str]]
) -> None:
    with pytest.raises(ValueError):
        client.generate(server.url, "local:4b", value)
    assert server.calls == []


def test_lists_only_local_models_and_preserves_request_identity(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/tags"].payload = {
        "models": [
            {"name": "local:4b"},
            {"name": "remote:cloud"},
            {"name": "remote-cloud:latest"},
            {"name": "hidden:4b", "remote_host": "https://example.com"},
            {"name": "local:4b"},
        ]
    }
    with qtbot.waitSignal(client.models_ready, timeout=2000) as result:
        request_id = client.list_models(server.url + "/")
    assert result.args == [request_id, ["local:4b"]]
    assert [path for path, _body in server.calls] == ["/api/tags"]


def test_show_then_chat_uses_checked_local_model_and_a_snapshot_of_messages(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    source = messages()
    with qtbot.waitSignal(client.explanation_ready, timeout=2000) as result:
        request_id = client.generate(server.url, "local:4b", source)
        source[1]["content"] = "changed after sending"
    assert result.args == [request_id, "连接两块棋。"]
    assert [path for path, _body in server.calls] == ["/api/show", "/api/chat"]
    assert server.calls[0][1] == {"model": "local:4b"}
    chat = server.calls[1][1]
    assert isinstance(chat, dict)
    assert chat["messages"] == messages()
    assert chat["stream"] is True
    assert "think" not in chat
    assert chat["keep_alive"] == 0
    assert chat["options"] == {"num_ctx": 4096, "num_predict": 768, "temperature": 0.2}


@pytest.mark.parametrize("values", [[False], [False, True]])
def test_thinking_is_disabled_when_model_explicitly_supports_false(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama, values: list[bool]
) -> None:
    server.routes["/api/show"].payload = {
        "capabilities": ["completion", "thinking"],
        "thinking": {"values": values, "default": True},
    }
    with qtbot.waitSignal(client.explanation_ready, timeout=2000):
        client.generate(server.url, "local:4b", messages())
    chat = server.calls[1][1]
    assert isinstance(chat, dict)
    assert chat["think"] is False


def test_thinking_capability_without_values_attempts_local_non_thinking_chat(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/show"].payload = {"capabilities": ["completion", "thinking"]}
    with qtbot.waitSignal(client.explanation_ready, timeout=2000):
        client.generate(server.url, "local:4b", messages())
    chat = server.calls[1][1]
    assert isinstance(chat, dict)
    assert chat["think"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"thinking": {"values": [True], "default": True}},
        {"thinking": {"values": ["low", "high"]}},
    ],
)
def test_models_explicitly_without_non_thinking_mode_are_rejected_before_chat(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama, payload: dict[str, object]
) -> None:
    server.routes["/api/show"].payload = payload
    with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
        client.generate(server.url, "local:4b", messages())
    assert "非思考模型" in failure.args[1]
    assert [path for path, _body in server.calls] == ["/api/show"]


@pytest.mark.parametrize(
    "details",
    [
        {"remote_host": "https://example.com"},
        {"remote_model": "remote:70b"},
        {"details": {"remote_model": "remote:70b"}},
        {"model": "remote:cloud"},
        {},
    ],
)
def test_show_rejects_remote_or_missing_model_information_without_chat(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama, details: dict[str, object]
) -> None:
    server.routes["/api/show"].payload = details
    with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
        request_id = client.generate(server.url, "local:4b", messages())
    assert failure.args[0] == request_id
    assert [path for path, _body in server.calls] == ["/api/show"]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (Response(status=404, payload={"error": "model missing"}), "未找到模型"),
        (Response(status=500, payload={"error": "out of memory"}), "out of memory"),
        (Response(raw=b"not json"), "JSON"),
        (Response(raw=b""), "完整"),
        (Response(payload=[]), "格式"),
        (Response(payload={"message": {"content": " "}, "done": True}), "完整"),
        (Response(payload={"message": {"content": "partial"}, "done": False}), "完整"),
        (Response(payload={"error": "model load failed"}), "model load failed"),
    ],
)
def test_chat_failures_are_reported_once_without_success(
    qtbot: QtBot,
    client: OllamaClient,
    server: LocalOllama,
    response: Response,
    expected: str,
) -> None:
    server.routes["/api/chat"] = response
    failures: list[tuple[str, str]] = []
    successes: list[tuple[str, str]] = []
    client.request_failed.connect(lambda rid, text: failures.append((rid, text)))
    client.explanation_ready.connect(lambda rid, text: successes.append((rid, text)))
    with qtbot.waitSignal(client.request_failed, timeout=2000) as result:
        request_id = client.generate(server.url, "local:4b", messages())
    assert result.args[0] == request_id
    assert expected in result.args[1]
    qtbot.wait(20)
    assert len(failures) == 1
    assert successes == []


@pytest.mark.parametrize("send_length", [True, False])
def test_response_size_is_bounded_with_or_without_content_length(
    qtbot: QtBot, server: LocalOllama, send_length: bool
) -> None:
    service = OllamaClient(QCoreApplication.instance(), max_response_bytes=128)
    server.routes["/api/tags"] = Response(raw=b"x" * 1024, send_length=send_length)
    try:
        with qtbot.waitSignal(service.request_failed, timeout=2000) as failure:
            service.list_models(server.url)
        assert "响应过大" in failure.args[1]
    finally:
        service.shutdown()
        service.deleteLater()


def test_redirect_is_not_followed_even_to_another_local_server(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    destination = LocalOllama()
    server.routes["/api/tags"] = Response(
        status=302, headers={"Location": destination.url + "/api/tags"}
    )
    try:
        with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
            client.list_models(server.url)
        assert "重定向" in failure.args[1]
        assert destination.calls == []
    finally:
        destination.close()


def test_local_requests_bypass_application_and_environment_proxy(
    qtbot: QtBot,
    client: OllamaClient,
    server: LocalOllama,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy = LocalOllama()
    original = QNetworkProxy.applicationProxy()
    monkeypatch.setenv("HTTP_PROXY", proxy.url)
    monkeypatch.setenv("http_proxy", proxy.url)
    monkeypatch.setenv("NO_PROXY", "")
    QNetworkProxy.setApplicationProxy(
        QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, "127.0.0.1", proxy.server.server_port)
    )
    try:
        with qtbot.waitSignal(client.models_ready, timeout=2000):
            client.list_models(server.url)
        assert proxy.calls == []
        assert len(server.calls) == 1
    finally:
        QNetworkProxy.setApplicationProxy(original)
        proxy.close()


@pytest.mark.parametrize("stage", ["tags", "show", "chat"])
def test_real_watchdog_times_out_without_blocking_the_qt_event_loop(
    qtbot: QtBot, server: LocalOllama, stage: str
) -> None:
    service = OllamaClient(
        QCoreApplication.instance(), models_timeout_ms=25, chat_timeout_ms=25
    )
    server.routes[f"/api/{stage}"].delay = 0.15
    try:
        with qtbot.waitSignal(service.request_failed, timeout=2000) as failure:
            if stage == "tags":
                service.list_models(server.url)
            else:
                service.generate(server.url, "local:4b", messages())
        assert "超时" in failure.args[1]
    finally:
        service.shutdown()
        service.deleteLater()


@pytest.mark.parametrize("stage", ["show", "chat"])
def test_cancel_discards_late_reply_and_does_not_emit_failure(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama, stage: str
) -> None:
    server.routes[f"/api/{stage}"].delay = 0.12
    seen: list[str] = []
    client.explanation_ready.connect(lambda _rid, text: seen.append(text))
    client.request_failed.connect(lambda _rid, text: seen.append(text))
    request_id = client.generate(server.url, "local:4b", messages())
    qtbot.waitUntil(lambda: any(path == f"/api/{stage}" for path, _body in server.calls))
    client.cancel(request_id)
    qtbot.wait(180)
    assert seen == []
    if stage == "show":
        assert [path for path, _body in server.calls] == ["/api/show"]


def test_shutdown_cancels_all_requests_and_rejects_new_work(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/tags"].delay = 0.12
    server.routes["/api/show"].delay = 0.12
    seen: list[str] = []
    client.models_ready.connect(lambda rid, _names: seen.append(rid))
    client.explanation_ready.connect(lambda rid, _text: seen.append(rid))
    client.request_failed.connect(lambda rid, _text: seen.append(rid))
    client.list_models(server.url)
    client.generate(server.url, "local:4b", messages())
    client.shutdown()
    qtbot.wait(180)
    assert seen == []
    with pytest.raises(ValueError, match="关闭"):
        client.list_models(server.url)


def test_connection_refused_has_actionable_chinese_error(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.server.shutdown()
    server.server.server_close()
    with qtbot.waitSignal(client.request_failed, timeout=5000) as failure:
        client.list_models(server.url)
    assert "本机 Ollama" in failure.args[1]
    assert "服务已启动" in failure.args[1]


def stream_line(content: str, *, done: bool = False, thinking: str = "") -> bytes:
    return json.dumps(
        {"message": {"content": content, "thinking": thinking}, "done": done},
        ensure_ascii=False,
    ).encode("utf-8")


def test_stream_handles_split_utf8_multiple_lines_and_unterminated_final_line(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    first = stream_line("连接") + b"\n"
    split = first.index("连".encode()) + 1
    server.routes["/api/chat"] = Response(
        chunks=[
            first[:split],
            first[split:],
            stream_line("两块棋。") + b"\n" + stream_line("", done=True),
        ],
        send_length=False,
    )
    partials: list[tuple[str, str]] = []
    client.explanation_partial.connect(lambda rid, text: partials.append((rid, text)))
    with qtbot.waitSignal(client.explanation_ready, timeout=2000) as result:
        request_id = client.generate(server.url, "local:4b", messages())
    assert partials == [(request_id, "连接"), (request_id, "连接两块棋。")]
    assert result.args == [request_id, "连接两块棋。"]


def test_stream_never_displays_thinking_content(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/chat"] = Response(
        chunks=[
            stream_line("", thinking="这是内部思考") + b"\n",
            stream_line("已核实的说明。", done=True),
        ]
    )
    partials: list[str] = []
    client.explanation_partial.connect(lambda _rid, text: partials.append(text))
    with qtbot.waitSignal(client.explanation_ready, timeout=2000) as result:
        client.generate(server.url, "local:4b", messages())
    assert partials == ["已核实的说明。"]
    assert result.args[1] == "已核实的说明。"


@pytest.mark.parametrize(
    ("ending", "expected"),
    [
        (b"", "完整"),
        (b'{"error":"generation failed"}\n', "generation failed"),
        (b"broken json\n", "JSON"),
    ],
)
def test_stream_error_or_eof_without_done_does_not_emit_ready(
    qtbot: QtBot,
    client: OllamaClient,
    server: LocalOllama,
    ending: bytes,
    expected: str,
) -> None:
    server.routes["/api/chat"] = Response(chunks=[stream_line("前半句") + b"\n", ending])
    partials: list[str] = []
    completed: list[str] = []
    client.explanation_partial.connect(lambda _rid, text: partials.append(text))
    client.explanation_ready.connect(lambda _rid, text: completed.append(text))
    with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
        client.generate(server.url, "local:4b", messages())
    assert expected in failure.args[1]
    assert partials == ["前半句"]
    assert completed == []


def test_cancelling_from_partial_callback_stops_later_text_and_completion(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/chat"] = Response(
        chunks=[stream_line("前半句") + b"\n", stream_line("后半句", done=True)],
        chunk_delay=0.05,
    )
    seen: list[str] = []
    terminal: list[str] = []

    def partial(request_id: str, text: str) -> None:
        seen.append(text)
        client.cancel(request_id)

    client.explanation_partial.connect(partial)
    client.explanation_ready.connect(lambda _rid, text: terminal.append(text))
    client.request_failed.connect(lambda _rid, text: terminal.append(text))
    client.generate(server.url, "local:4b", messages())
    qtbot.waitUntil(lambda: bool(seen))
    qtbot.wait(150)
    assert seen == ["前半句"]
    assert terminal == []


def test_stream_line_limit_and_total_response_limit_are_distinct(
    qtbot: QtBot, server: LocalOllama
) -> None:
    service = OllamaClient(
        QCoreApplication.instance(), max_response_bytes=1024, max_line_bytes=100
    )
    server.routes["/api/chat"] = Response(raw=stream_line("x" * 150, done=True))
    try:
        with qtbot.waitSignal(service.request_failed, timeout=2000) as failure:
            service.generate(server.url, "local:4b", messages())
        assert "单行过大" in failure.args[1]
    finally:
        service.shutdown()
        service.deleteLater()


@pytest.mark.parametrize("stage", ["tags", "show"])
def test_deep_model_metadata_does_not_leave_request_pending(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama, stage: str
) -> None:
    nested = b"[" * 500 + b'{"remote_host":"https://example.com"}' + b"]" * 500
    if stage == "show":
        server.routes["/api/show"] = Response(raw=b'{"details":' + nested + b"}")
        with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
            client.generate(server.url, "local:4b", messages())
        assert "远程" in failure.args[1]
        assert [path for path, _body in server.calls] == ["/api/show"]
    else:
        server.routes["/api/tags"] = Response(
            raw=b'{"models":[{"name":"nested:4b","details":' + nested + b"}]}"
        )
        with qtbot.waitSignal(client.models_ready, timeout=2000) as result:
            client.list_models(server.url)
        assert result.args[1] == []


def test_output_length_limit_is_reported_as_truncation_not_complete_explanation(
    qtbot: QtBot, client: OllamaClient, server: LocalOllama
) -> None:
    server.routes["/api/chat"] = Response(
        chunks=[
            stream_line("没有完成的前半句") + b"\n",
            json.dumps(
                {"done": True, "done_reason": "length", "message": {"content": "后续"}},
                ensure_ascii=False,
            ).encode(),
        ]
    )
    partials: list[str] = []
    ready: list[str] = []
    client.explanation_partial.connect(lambda _rid, text: partials.append(text))
    client.explanation_ready.connect(lambda _rid, text: ready.append(text))
    with qtbot.waitSignal(client.request_failed, timeout=2000) as failure:
        request_id = client.generate(server.url, "local:4b", messages())
    assert failure.args[0] == request_id
    assert "截断" in failure.args[1]
    qtbot.wait(20)
    assert partials == ["没有完成的前半句"]
    assert ready == []

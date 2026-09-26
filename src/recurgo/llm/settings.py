"""Local-only Ollama configuration, independent of engine strength settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


def normalize_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Ollama 地址必须是本机 HTTP 地址。")
    value = value.strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError("Ollama 地址不能为空或包含空白字符。")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Ollama 地址或端口格式不正确。") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or "?" in value
        or "#" in value
        or "\\" in value
        or (port is not None and not 1 <= port <= 65535)
        or parsed.netloc.endswith(":")
    ):
        raise ValueError(
            "仅允许本机 HTTP 根地址，例如 http://127.0.0.1:11434；"
            "不允许外部地址、用户名、路径、查询参数或片段。"
        )
    host = "[::1]" if parsed.hostname == "::1" else "127.0.0.1"
    return f"http://{host}" + (f":{port}" if port is not None else "")


def validate_model(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("请选择已安装的本地 Ollama 模型。")
    value = value.strip()
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("Ollama 模型名称不能为空或包含空白字符。")
    if ":cloud" in value.lower() or "-cloud" in value.lower():
        raise ValueError("不允许使用云端模型；请选择已安装的本地模型。")
    return value


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    enabled: bool = False
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b-instruct-2507-q4_K_M"

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("Ollama 启用状态必须是布尔值。")
        object.__setattr__(self, "base_url", normalize_base_url(self.base_url))
        object.__setattr__(self, "model", validate_model(self.model))

    @classmethod
    def from_mapping(cls, raw: dict[str, object] | None) -> OllamaSettings:
        if not isinstance(raw, dict):
            return cls()
        enabled = raw.get("enabled", False)
        base_url = raw.get("base_url", "http://127.0.0.1:11434")
        model = raw.get("model", "qwen3:4b-instruct-2507-q4_K_M")
        if not isinstance(enabled, bool) or not isinstance(base_url, str) or not isinstance(
            model, str
        ):
            return cls()
        try:
            return cls(enabled=enabled, base_url=base_url, model=model)
        except ValueError:
            return cls()

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

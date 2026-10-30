"""v1.1.0.dev1: stable provenance for persisted KataGo analysis results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

_NON_ANALYSIS_SETTINGS = frozenset(
    {
        "logdir",
        "logfile",
        "logtostderr",
        "logallrequests",
        "logallresponses",
        "logerrorsandwarnings",
        "logsearchinfo",
        "warnunusedfields",
        "homedatadir",
        "cudacachedir",
        "tensorrtcachedir",
        "openclcachedir",
    }
)


def _digest(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _configuration(runtime: object) -> list[str]:
    path = getattr(runtime, "analysis_config", None)
    if path is None:
        return ["configuration-unavailable"]
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, TypeError, ValueError):
        # Never fall back to a previous, successfully loaded configuration.
        return ["configuration-unavailable", str(path)]
    settings = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        key, separator, value = line.partition("=")
        if key.strip().casefold() in _NON_ANALYSIS_SETTINGS:
            continue
        settings.append(f"{key.strip()}={value.strip()}" if separator else line)
    # Keep order: repeated settings or include directives may be order-sensitive.
    return settings


@dataclass(frozen=True, slots=True)
class AnalysisIdentity:
    """One engine/model/configuration source, fixed for an engine session.

    Visit budget remains part of each query's cache key. Human SL data is an
    auxiliary output: its model/profile scopes realtime snapshots separately,
    without splitting objective win-rate charts and full-game analysis.
    """

    key: str
    engine_version: str
    engine_sha256: str
    backend: str
    model_sha256: str
    config_sha256: str
    human_model_sha256: str

    @property
    def is_available(self) -> bool:
        return (
            self.engine_version not in {"", "unavailable"}
            and self.model_sha256 not in {"", "unavailable"}
        )

    @classmethod
    def from_runtime(cls, runtime: object) -> AnalysisIdentity:
        engine_version = str(getattr(runtime, "engine_version", "unavailable"))
        engine_sha256 = str(getattr(runtime, "engine_sha256", ""))
        backend = str(getattr(runtime, "backend", "unavailable"))
        model_sha256 = str(getattr(runtime, "model_sha256", "unavailable"))
        config_sha256 = _digest(_configuration(runtime))
        human_model_sha256 = str(getattr(runtime, "human_model_sha256", ""))
        if not human_model_sha256:
            # Older runtime adapters do not expose this field. Include their
            # declared model path rather than silently equating two models.
            human_model_sha256 = str(getattr(runtime, "human_model", "unavailable"))
        key = _digest(
            {
                "schema": 1,
                "engine": engine_version,
                "engineHash": engine_sha256,
                "backend": backend,
                "model": model_sha256,
                "configuration": config_sha256,
                "query_contract": "black-history-pv12-policy-v1",
            }
        )
        return cls(
            key,
            engine_version,
            engine_sha256,
            backend,
            model_sha256,
            config_sha256,
            human_model_sha256,
        )

    def realtime_key(self, visits: int, ownership: bool, human_profile: str) -> str:
        human_key = _digest([self.human_model_sha256, human_profile])
        return f"realtime-{visits}-{int(ownership)}-human-{human_key}"

    def metadata(self) -> dict[str, str]:
        return {
            "analysisIdentity": self.key,
            "engineSha256": self.engine_sha256,
            "backend": self.backend,
            "configSha256": self.config_sha256,
            "humanModelSha256": self.human_model_sha256,
        }

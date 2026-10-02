"""Validated, persistent appearance and sound preferences."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class BoardTheme:
    label: str
    background: str
    background_dark: str
    line: str
    star: str
    coordinate: str


@dataclass(frozen=True, slots=True)
class StoneStyle:
    label: str
    rendering: str


BOARD_THEMES: dict[str, BoardTheme] = {
    "classic": BoardTheme(
        "经典榧木",
        "#d7a94f",
        "#b98232",
        "#2b2115",
        "#21180f",
        "#cbd1d7",
    ),
    "light": BoardTheme(
        "浅色枫木",
        "#e7c982",
        "#cda758",
        "#4a3420",
        "#372718",
        "#d9dee3",
    ),
    "dark": BoardTheme(
        "深色胡桃木",
        "#7a5636",
        "#50351f",
        "#21160f",
        "#17100b",
        "#d7dbe0",
    ),
    "paper": BoardTheme(
        "宣纸棋盘",
        "#d8d0ba",
        "#b8ad92",
        "#3f3b34",
        "#302d28",
        "#d4d9de",
    ),
}

STONE_STYLES: dict[str, StoneStyle] = {
    "classic": StoneStyle("经典立体", "glossy"),
    "matte": StoneStyle("磨砂陶瓷", "matte"),
    "jade": StoneStyle("玉石质感", "jade"),
    "flat": StoneStyle("简洁扁平", "flat"),
}

PLACEMENT_SOUNDS: dict[str, str] = {
    "wood": "沉稳木质",
    "crisp": "清脆落子",
    "soft": "轻柔落子",
}

CAPTURE_SOUNDS: dict[str, str] = {
    "wood": "连续提子",
    "crisp": "清脆提子",
    "soft": "轻柔提子",
}


@dataclass(frozen=True, slots=True)
class AnalysisControls:
    realtime_enabled: bool = False
    ownership_enabled: bool = False

    @classmethod
    def from_mapping(cls, raw: dict[str, object] | None) -> AnalysisControls:
        raw = raw or {}
        return cls(
            realtime_enabled=raw.get("realtime_enabled") is True,
            ownership_enabled=raw.get("ownership_enabled") is True,
        )

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AppPreferences:
    board_theme: str = "classic"
    custom_board_path: str = ""
    stone_style: str = "classic"
    placement_sound: str = "wood"
    capture_sound: str = "wood"
    volume: int = 72
    muted: bool = False
    language: str = "en"

    @classmethod
    def from_mapping(cls, raw: dict[str, object] | None) -> AppPreferences:
        if raw is None:
            return cls()
        board_theme = str(raw.get("board_theme", "classic"))
        stone_style = str(raw.get("stone_style", "classic"))
        placement_sound = str(raw.get("placement_sound", "wood"))
        capture_sound = str(raw.get("capture_sound", "wood"))
        volume_value = raw.get("volume", 72)
        volume = int(volume_value) if isinstance(volume_value, (int, float)) else 72
        return cls(
            board_theme=(board_theme if board_theme in BOARD_THEMES else "classic"),
            custom_board_path=str(raw.get("custom_board_path", "")),
            stone_style=(stone_style if stone_style in STONE_STYLES else "classic"),
            placement_sound=(
                placement_sound if placement_sound in PLACEMENT_SOUNDS else "wood"
            ),
            capture_sound=capture_sound if capture_sound in CAPTURE_SOUNDS else "wood",
            volume=max(0, min(100, volume)),
            muted=bool(raw.get("muted", False)),
            language=("zh" if raw.get("language") == "zh" else "en"),
        )

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

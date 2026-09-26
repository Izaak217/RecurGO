"""Localized display formatting that does not alter engine values."""

from __future__ import annotations

from recurgo.domain.scoring import display_sgf_result, format_stones
from recurgo.i18n import Language


def format_rules_and_komi(rules: str, komi: float, *, language: Language = "zh") -> str:
    normalized = rules.strip().lower()
    if normalized in {"chinese", "chinese-ogs"}:
        if language == "en":
            return f"Chinese rules · Black gives {_format_quarter(komi / 2.0)} stones"
        return f"中国规则 · 黑贴{_format_quarter(komi / 2.0)}子"
    if normalized == "japanese":
        if language == "en":
            return f"Japanese rules · White komi {komi:g} points"
        return f"日本规则 · 黑贴{komi:g}目"
    if normalized == "korean":
        if language == "en":
            return f"Korean rules · White komi {komi:g} points"
        return f"韩国规则 · 黑贴{komi:g}目"
    return f"{rules} · komi {komi:g}"


def format_result(result: str, *, language: Language = "zh") -> str:
    """Format an SGF result for display without changing the saved SGF value."""
    if language == "zh":
        return display_sgf_result(result)
    normalized = result.strip().upper()
    if normalized in {"", "?"}:
        return "Result undecided"
    if normalized in {"0", "DRAW"}:
        return "Draw"
    if "+" not in normalized:
        return result
    winner, margin = normalized.split("+", 1)
    winner_name = "Black" if winner == "B" else "White" if winner == "W" else winner
    if margin in {"R", "RESIGN"}:
        return f"{winner_name} wins by resignation"
    try:
        numeric_margin = float(margin)
    except ValueError:
        return result
    return f"{winner_name} wins by {format_stones(numeric_margin)} (recorded margin)"


def _format_quarter(value: float) -> str:
    quarter_count = round(value * 4)
    if abs(value * 4 - quarter_count) > 1e-7:
        return f"{value:g}"
    integer, remainder = divmod(quarter_count, 4)
    fractions = {0: "", 1: "¼", 2: "½", 3: "¾"}
    return f"{integer if integer else ''}{fractions[remainder]}" or "0"

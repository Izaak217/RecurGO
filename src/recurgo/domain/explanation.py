"""Deterministic, evidence-backed explanations for KataGo candidate moves."""

from __future__ import annotations

import math
from dataclasses import dataclass

from recurgo.i18n import Language, tr

from .board import BoardState, Color, IllegalMove
from .coordinates import Point, gtp_to_point


@dataclass(frozen=True, slots=True)
class ExplanationEvidence:
    """One locally verified reason that supports a candidate's intent."""

    code: str
    text: str
    confidence: int


@dataclass(frozen=True, slots=True)
class CandidateExplanation:
    move: str
    rank: int
    side: Color
    evidences: tuple[ExplanationEvidence, ...]
    side_winrate: float | None
    side_score_lead: float | None
    human_policy: float | None
    visits: int | None
    variation: tuple[str, ...]
    best_winrate_gap: float | None
    best_score_gap: float | None
    variation_notes: tuple[str, ...] = ()
    language: Language = "zh"

    @property
    def confidence_label(self) -> str:
        confidence = max((item.confidence for item in self.evidences), default=0)
        if confidence >= 3:
            return tr(self.language, "高", "High")
        if confidence == 2:
            return tr(self.language, "中", "Medium")
        if confidence == 1:
            return tr(self.language, "较低", "Low")
        return tr(self.language, "证据不足", "Insufficient evidence")

    def render(self) -> str:
        heading = tr(
            self.language,
            f"推荐候选：{self.move}（第 {self.rank} 候选）",
            f"Candidate move: {self.move} (rank {self.rank})",
        )
        if self.evidences:
            reasons = tr(
                self.language,
                "；".join(item.text for item in self.evidences[:3]) + "。",
                "; ".join(item.text for item in self.evidences[:3]) + ".",
            )
            intent = tr(self.language, f"棋理判断：{reasons}", f"Go reasoning: {reasons}")
        else:
            intent = tr(
                self.language,
                (
                    "棋理判断：当前局部没有识别出足够明确的提子、连接、切断或补强证据，"
                    "因此不推断这手棋的具体意图；可结合右侧数据和下方参考变化判断。"
                ),
                (
                    "Go reasoning: The local rules did not find clear enough evidence of a capture, "
                    "connection, cut, or reinforcement. The move's exact intent is therefore uncertain; "
                    "use the analysis figures and reference variation as context."
                ),
            )

        comparison = ""
        if self.rank == 1:
            comparison = tr(
                self.language, "这是当前搜索的首选。", "This is the current search's top move."
            )
        else:
            gaps: list[str] = []
            if self.best_winrate_gap is not None:
                gaps.append(
                    tr(
                        self.language,
                        f"胜率低 {max(0.0, self.best_winrate_gap):.1f} 个百分点",
                        f"win rate lower by {max(0.0, self.best_winrate_gap):.1f} percentage points",
                    )
                )
            if self.best_score_gap is not None:
                gaps.append(
                    tr(
                        self.language,
                        f"目差少 {max(0.0, self.best_score_gap):.1f} 目",
                        f"score lead lower by {max(0.0, self.best_score_gap):.1f} points",
                    )
                )
            if gaps:
                comparison = tr(
                    self.language,
                    "与首选相比，" + "，".join(gaps) + "。",
                    "Compared with the top move: " + "; ".join(gaps) + ".",
                )

        human = ""
        if self.human_policy is not None:
            human = tr(
                self.language,
                f"人类策略模型偏好约 {self.human_policy * 100.0:.1f}%。",
                f"Human-policy preference is about {self.human_policy * 100.0:.1f}%.",
            )
        variation = (
            tr(
                self.language,
                "主要变化：" + " → ".join(self.variation) + "。",
                "Reference variation: " + " → ".join(self.variation) + ".",
            )
            if self.variation
            else tr(
                self.language,
                "主要变化：KataGo 暂未返回可用的后续变化。",
                "Reference variation: KataGo has not returned a usable continuation.",
            )
        )
        consequences = (
            tr(
                self.language,
                "变化中的可见结果："
                + "；".join(self.variation_notes)
                + "。这只是搜索参考变化。",
                "Visible results in the variation: "
                + "; ".join(self.variation_notes)
                + ". This is only a search reference line.",
            )
            if self.variation_notes
            else ""
        )
        footer = tr(
            self.language,
            (
                f"棋理判断置信度：{self.confidence_label}。棋形说明由本地规则根据当前棋盘、"
                "气、连接关系和 KataGo 数据生成，不使用外部语言模型。"
            ),
            (
                f"Go-reasoning confidence: {self.confidence_label}. This explanation comes from local "
                "rules using the board, liberties, connections, and KataGo data; it does not use an external language model."
            ),
        )
        return "\n\n".join(
            part
            for part in (
                heading,
                intent,
                comparison,
                human,
                variation,
                consequences,
                footer,
            )
            if part
        )


def explain_candidate(
    state: BoardState,
    payload: dict[str, object],
    info: dict[str, object],
    *,
    rank: int,
    language: Language = "zh",
) -> CandidateExplanation:
    """Explain a searched candidate without inventing unsupported strategy."""
    move = str(info.get("move", "pass"))
    evidences = _move_evidences(state, payload, move, language=language)
    side_winrate = _side_value(_number(info.get("winrate")), state.to_play, percent=True)
    side_score = _side_value(
        _number(info.get("scoreLead", info.get("scoreMean"))),
        state.to_play,
        percent=False,
    )
    best_info = _best_info(payload)
    best_winrate = (
        None
        if best_info is None
        else _side_value(_number(best_info.get("winrate")), state.to_play, percent=True)
    )
    best_score = (
        None
        if best_info is None
        else _side_value(
            _number(best_info.get("scoreLead", best_info.get("scoreMean"))),
            state.to_play,
            percent=False,
        )
    )
    policy = _human_policy(payload, move, state.size)
    visits_value = info.get("visits")
    visits = int(visits_value) if isinstance(visits_value, (int, float)) else None
    pv = info.get("pv")
    variation = tuple(str(value) for value in pv[:8]) if isinstance(pv, list) else ()
    return CandidateExplanation(
        move=move,
        rank=rank,
        side=state.to_play,
        evidences=evidences,
        side_winrate=side_winrate,
        side_score_lead=side_score,
        human_policy=policy,
        visits=visits,
        variation=variation,
        best_winrate_gap=_gap(best_winrate, side_winrate),
        best_score_gap=_gap(best_score, side_score),
        variation_notes=_variation_observations(state, move, variation, language=language),
        language=language,
    )


def _variation_observations(
    state: BoardState,
    candidate: str,
    variation: tuple[str, ...],
    *,
    language: Language = "zh",
) -> tuple[str, ...]:
    """Replay the reference line locally; report captures, never infer forced outcomes."""
    if not variation or variation[0] != candidate:
        return ()
    current = state
    observations: list[str] = []
    for index, move in enumerate(variation):
        if current.is_game_over:
            break
        try:
            point = gtp_to_point(move, current.size)
            after = current.play(point)
        except (ValueError, IllegalMove):
            break
        captured = _capture_difference(current, after, current.to_play)
        # The first move's capture is already explained by the immediate shape rules.
        if index > 0 and captured:
            side = (
                tr(language, "黑方", "Black")
                if current.to_play is Color.BLACK
                else tr(language, "白方", "White")
            )
            observations.append(
                tr(
                    language,
                    f"第 {index + 1} 手{side}在 {move} 提走 {captured} 子",
                    f"On move {index + 1}, {side} captures {captured} stones at {move}",
                )
            )
        current = after
    return tuple(observations[:2])


def _move_evidences(
    state: BoardState,
    payload: dict[str, object],
    move: str,
    *,
    language: Language = "zh",
) -> tuple[ExplanationEvidence, ...]:
    try:
        point = gtp_to_point(move, state.size)
    except ValueError:
        return ()
    if point is None:
        return ()
    try:
        after = state.play(point)
    except IllegalMove:
        return ()

    friendly_groups = _adjacent_groups(state, point, state.to_play)
    opponent_groups = _adjacent_groups(state, point, state.to_play.opponent)
    placed_group = _group_at(after, point)
    placed_liberties = _liberties(after, placed_group)
    evidences: list[ExplanationEvidence] = []
    capture_count = _capture_difference(state, after, state.to_play)
    if capture_count:
        evidences.append(
            ExplanationEvidence(
                "capture",
                tr(
                    language,
                    f"直接提走 {capture_count} 颗对方棋子",
                    f"directly captures {capture_count} opposing stones",
                ),
                3,
            )
        )

    rescued = [group for group in friendly_groups if _liberties(state, group) == {point}]
    if rescued and len(placed_liberties) > 1:
        stone_count = sum(len(group) for group in rescued)
        evidences.append(
            ExplanationEvidence(
                "rescue",
                tr(
                    language,
                    f"使正被打吃的 {stone_count} 颗己方棋子暂时脱离打吃，不代表已经做活",
                    f"takes {stone_count} friendly stones out of immediate atari, without proving they are alive",
                ),
                3,
            )
        )
    elif rescued:
        evidences.append(
            ExplanationEvidence(
                "extend_atari",
                tr(
                    language,
                    "延长了被打吃的己方棋串，但落子后仍只有一口气，尚未解除打吃",
                    "extends a friendly group in atari, but it still has only one liberty afterwards",
                ),
                3,
            )
        )

    if len(friendly_groups) >= 2:
        evidences.append(
            ExplanationEvidence(
                "connect",
                tr(
                    language,
                    f"把相邻的 {len(friendly_groups)} 块己方棋连接成整体",
                    f"connects {len(friendly_groups)} adjacent friendly groups",
                ),
                3,
            )
        )

    if len(opponent_groups) >= 2:
        evidences.append(
            ExplanationEvidence(
                "cut",
                tr(
                    language,
                    "占据两块对方棋之间的要点，形成分断压力",
                    "occupies a key point between opposing groups and threatens to cut them",
                ),
                2,
            )
        )

    weak_friendly = [
        group for group in friendly_groups if 1 < len(_liberties(state, group)) <= 3
    ]
    if weak_friendly and len(placed_liberties) > max(
        len(_liberties(state, group)) for group in weak_friendly
    ):
        evidences.append(
            ExplanationEvidence(
                "reinforce",
                tr(
                    language,
                    f"补强气紧的己方棋，落子后相连棋串约有 {len(placed_liberties)} 口气",
                    f"reinforces a low-liberty friendly group; the connected group has about {len(placed_liberties)} liberties afterwards",
                ),
                2,
            )
        )

    attacked = [group for group in opponent_groups if 1 < len(_liberties(state, group)) <= 3]
    if attacked and not capture_count:
        target_count = sum(len(group) for group in attacked)
        evidences.append(
            ExplanationEvidence(
                "attack",
                tr(
                    language,
                    f"压缩附近 {target_count} 颗对方棋的气，带有攻击意味",
                    f"reduces liberties around {target_count} opposing stones, suggesting an attack",
                ),
                2,
            )
        )

    ownership = _ownership_at(payload, point, state.size)
    opponent_owned = ownership is not None and (
        state.to_play is Color.BLACK
        and ownership <= -0.45
        or state.to_play is Color.WHITE
        and ownership >= 0.45
    )
    if opponent_owned:
        evidences.append(
            ExplanationEvidence(
                "reduction",
                tr(
                    language,
                    "落在对方 ownership 较高的区域，具有侵消或破空意图",
                    "plays in an area with high opponent ownership, suggesting invasion or reduction",
                ),
                2,
            )
        )

    if not evidences and _looks_like_endgame_boundary(state, point):
        evidences.append(
            ExplanationEvidence(
                "endgame",
                tr(
                    language,
                    "位于双方棋势交界处，结合当前手数更像是边界官子",
                    "lies near a boundary between both players' stones and may be an endgame move",
                ),
                1,
            )
        )
    return tuple(evidences)


def _neighbors(state: BoardState, point: Point) -> tuple[Point, ...]:
    candidates = (
        Point(point.x - 1, point.y),
        Point(point.x + 1, point.y),
        Point(point.x, point.y - 1),
        Point(point.x, point.y + 1),
    )
    return tuple(
        candidate
        for candidate in candidates
        if 0 <= candidate.x < state.size and 0 <= candidate.y < state.size
    )


def _group_at(state: BoardState, start: Point) -> frozenset[Point]:
    color = state.stone_at(start)
    if color is None:
        return frozenset()
    group: set[Point] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current in group:
            continue
        group.add(current)
        pending.extend(
            neighbor
            for neighbor in _neighbors(state, current)
            if neighbor not in group and state.stone_at(neighbor) is color
        )
    return frozenset(group)


def _liberties(state: BoardState, group: frozenset[Point]) -> set[Point]:
    return {
        neighbor
        for stone in group
        for neighbor in _neighbors(state, stone)
        if state.stone_at(neighbor) is None
    }


def _adjacent_groups(
    state: BoardState,
    point: Point,
    color: Color,
) -> tuple[frozenset[Point], ...]:
    groups: list[frozenset[Point]] = []
    seen: set[Point] = set()
    for neighbor in _neighbors(state, point):
        if neighbor in seen or state.stone_at(neighbor) is not color:
            continue
        group = _group_at(state, neighbor)
        seen.update(group)
        groups.append(group)
    return tuple(groups)


def _capture_difference(before: BoardState, after: BoardState, color: Color) -> int:
    if color is Color.BLACK:
        return after.black_captures - before.black_captures
    return after.white_captures - before.white_captures


def _looks_like_endgame_boundary(state: BoardState, point: Point) -> bool:
    threshold = round(state.size * state.size * 0.36)
    if state.move_number < threshold:
        return False
    nearby: set[Color] = set()
    radius = 3
    for y in range(max(0, point.y - radius), min(state.size, point.y + radius + 1)):
        for x in range(max(0, point.x - radius), min(state.size, point.x + radius + 1)):
            if abs(x - point.x) + abs(y - point.y) > radius:
                continue
            color = state.stone_at(Point(x, y))
            if color is not None:
                nearby.add(color)
    return nearby == {Color.BLACK, Color.WHITE}


def _ownership_at(payload: dict[str, object], point: Point, board_size: int) -> float | None:
    ownership = payload.get("ownership")
    index = point.y * board_size + point.x
    if not isinstance(ownership, list) or not (0 <= index < len(ownership)):
        return None
    return _number(ownership[index])


def _human_policy(payload: dict[str, object], move: str, board_size: int) -> float | None:
    policy = payload.get("humanPolicy")
    if not isinstance(policy, list):
        return None
    try:
        point = gtp_to_point(move, board_size)
    except ValueError:
        return None
    index = board_size * board_size if point is None else point.y * board_size + point.x
    if not (0 <= index < len(policy)):
        return None
    value = _number(policy[index])
    return value if value is not None and value >= 0 else None


def _best_info(payload: dict[str, object]) -> dict[str, object] | None:
    move_infos = payload.get("moveInfos")
    if not isinstance(move_infos, list):
        return None
    infos = [value for value in move_infos if isinstance(value, dict)]
    if not infos:
        return None
    return min(
        infos,
        key=lambda value: (
            int(value["order"]) if isinstance(value.get("order"), (int, float)) else 1_000_000
        ),
    )


def _side_value(value: float | None, side: Color, *, percent: bool) -> float | None:
    if value is None:
        return None
    normalized = value * 100.0 if percent else value
    if side is Color.BLACK:
        return normalized
    return 100.0 - normalized if percent else -normalized


def _gap(best: float | None, selected: float | None) -> float | None:
    if best is None or selected is None:
        return None
    return max(0.0, best - selected)


def _number(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


__all__ = [
    "CandidateExplanation",
    "ExplanationEvidence",
    "explain_candidate",
]

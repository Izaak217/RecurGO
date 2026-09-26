"""SGF import and export while preserving the in-memory variation tree."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from pathlib import Path
from typing import Any

from sgfmill import sgf

from recurgo.domain import BoardState, Color, GameTree, Point


@dataclass(frozen=True, slots=True)
class ImportedSgf:
    tree: GameTree
    name: str
    black_player: str
    white_player: str
    rules: str
    komi: float
    result: str


def export_sgf(
    path: Path,
    tree: GameTree,
    *,
    name: str,
    rules: str,
    komi: float,
    result: str = "",
    black_player: str = "",
    white_player: str = "",
) -> None:
    game = sgf.Sgf_game(tree.root.state.size)
    root = game.get_root()
    root.set("AP", ("RecurGO", "0.1"))
    root.set("GN", name)
    root.set("RU", rules)
    root.set("KM", komi)
    if black_player:
        root.set("PB", black_player)
    if white_player:
        root.set("PW", white_player)
    if result:
        root.set("RE", result)
    if tree.root.comment:
        root.set("C", tree.root.comment)

    black_setup: set[tuple[int, int]] = set()
    white_setup: set[tuple[int, int]] = set()
    state = tree.root.state
    for y in range(state.size):
        for x in range(state.size):
            color = state.stone_at(Point(x, y))
            if color is Color.BLACK:
                black_setup.add((y, x))
            elif color is Color.WHITE:
                white_setup.add((y, x))
    if black_setup or white_setup:
        root.set_setup_stones(black_setup, white_setup, set())
        root.set("PL", state.to_play.short_name.lower())

    def append_children(parent: Any, parent_id: str) -> None:
        for child_id in tree.nodes[parent_id].children:
            game_node = tree.nodes[child_id]
            child = parent.new_child()
            if game_node.move is not None:
                point = game_node.move.point
                sgf_point = None if point is None else (point.y, point.x)
                child.set_move(game_node.move.color.short_name.lower(), sgf_point)
            if game_node.comment:
                child.set("C", game_node.comment)
            append_children(child, child_id)

    append_children(root, tree.root_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(game.serialise())


def import_sgf(path: Path) -> ImportedSgf:
    game = sgf.Sgf_game.from_bytes(path.read_bytes())
    root = game.get_root()
    size = int(game.get_size())
    black_raw, white_raw, _empty_raw = root.get_setup_stones()
    setup: dict[Point, Color] = {Point(column, row): Color.BLACK for row, column in black_raw}
    setup.update({Point(column, row): Color.WHITE for row, column in white_raw})
    to_play = _root_player(root, black_count=len(black_raw))
    initial_state = BoardState.from_setup(setup, size=size, to_play=to_play)
    tree = GameTree(initial_state)
    tree.root.comment = _text_property(root, "C", "")
    main_line_last = tree.root_id

    def read_children(parent: Any, parent_id: str, main_line: bool) -> None:
        nonlocal main_line_last
        for child_index, sgf_node in enumerate(parent):
            tree.go_to(parent_id)
            color_name, raw_point = sgf_node.get_move()
            next_parent_id = parent_id
            if color_name is not None:
                expected_color = Color.BLACK if color_name == "b" else Color.WHITE
                original_state = tree.current.state
                if tree.current.state.to_play is not expected_color:
                    tree.current.state = replace(
                        tree.current.state,
                        to_play=expected_color,
                    )
                point = None if raw_point is None else Point(raw_point[1], raw_point[0])
                node, _created = tree.play(point)
                tree.nodes[parent_id].state = original_state
                node.comment = _text_property(sgf_node, "C", "")
                next_parent_id = node.id
                if main_line and child_index == 0:
                    main_line_last = node.id
            read_children(
                sgf_node,
                next_parent_id,
                main_line=main_line and child_index == 0,
            )

    read_children(root, tree.root_id, main_line=True)
    tree.go_to(main_line_last)
    rules = normalize_sgf_rules(_text_property(root, "RU", "chinese"))
    komi = normalize_sgf_komi(_float_property(root, "KM", 7.5), rules)
    return ImportedSgf(
        tree=tree,
        name=_text_property(root, "GN", path.stem),
        black_player=_text_property(root, "PB", ""),
        white_player=_text_property(root, "PW", ""),
        rules=rules,
        komi=komi,
        result=_text_property(root, "RE", ""),
    )


def normalize_sgf_rules(rules: str) -> str:
    """Return KataGo's canonical shorthand for common SGF rule names."""
    normalized = rules.strip().lower()
    aliases = {
        "china": "chinese",
        "chinese rules": "chinese",
        "japan": "japanese",
        "japanese rules": "japanese",
        "korea": "korean",
        "korean rules": "korean",
        "new zealand": "new-zealand",
        "new_zealand": "new-zealand",
    }
    return aliases.get(normalized, normalized or "chinese")


def normalize_sgf_komi(komi: float, rules: str) -> float:
    """Convert Fox's hundredths-of-a-stone komi to KataGo point units.

    Fox SGFs may store Chinese 3.75-stone compensation as ``KM[375]``.
    KataGo expects the equivalent 7.5 points. Only out-of-range values that
    convert exactly to an integer or half-integer are treated as this format.
    """
    if normalize_sgf_rules(rules) not in {"chinese", "chinese-ogs"}:
        return komi
    if abs(komi) <= 150.0:
        return komi
    converted = komi / 50.0
    nearest_half_point = round(converted * 2.0) / 2.0
    if abs(nearest_half_point) <= 150.0 and isclose(
        converted,
        nearest_half_point,
        abs_tol=1e-9,
    ):
        return nearest_half_point
    return komi


def _root_player(root: Any, *, black_count: int) -> Color:
    player = _text_property(root, "PL", "")
    if player.lower() == "w":
        return Color.WHITE
    if player.lower() == "b":
        return Color.BLACK
    return Color.WHITE if black_count >= 2 else Color.BLACK


def _text_property(node: Any, property_name: str, default: str) -> str:
    if not node.has_property(property_name):
        return default
    return str(node.get(property_name))


def _float_property(node: Any, property_name: str, default: float) -> float:
    if not node.has_property(property_name):
        return default
    value = node.get(property_name)
    return float(value) if isinstance(value, (int, float)) else default

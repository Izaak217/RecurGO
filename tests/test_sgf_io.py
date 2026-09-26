from __future__ import annotations

from pathlib import Path

from recurgo.domain import BoardState, Color, GameTree, Point
from recurgo.storage import export_sgf, import_sgf


def test_sgf_round_trip_preserves_variations_comments_and_metadata(
    tmp_path: Path,
) -> None:
    tree = GameTree()
    first, _ = tree.play(Point(3, 3))
    first.comment = "布局方向"
    main_reply, _ = tree.play(Point(15, 15))
    main_reply.comment = "主变化"
    tree.undo()
    variation, _ = tree.play(Point(15, 3))
    variation.comment = "备选变化"
    tree.go_to(main_reply.id)
    destination = tmp_path / "variations.sgf"

    export_sgf(
        destination,
        tree,
        name="测试棋谱",
        rules="chinese",
        komi=7.5,
        result="W+1.25",
        black_player="黑方棋手",
        white_player="白方棋手",
    )
    imported = import_sgf(destination)

    assert imported.name == "测试棋谱"
    assert imported.black_player == "黑方棋手"
    assert imported.white_player == "白方棋手"
    assert imported.rules == "chinese"
    assert imported.komi == 7.5
    assert imported.result == "W+1.25"
    assert imported.tree.current.state.move_number == 2
    imported_first = imported.tree.path_to()[1]
    assert imported_first.comment == "布局方向"
    assert len(imported_first.children) == 2
    child_comments = {
        imported.tree.nodes[child_id].comment for child_id in imported_first.children
    }
    assert child_comments == {"主变化", "备选变化"}


def test_sgf_round_trip_preserves_root_setup_and_player(tmp_path: Path) -> None:
    state = BoardState.from_setup(
        {
            Point(3, 3): Color.BLACK,
            Point(15, 15): Color.WHITE,
        },
        to_play=Color.WHITE,
    )
    tree = GameTree(state)
    destination = tmp_path / "setup.sgf"

    export_sgf(destination, tree, name="摆谱", rules="chinese", komi=0.5)
    imported = import_sgf(destination)

    assert imported.tree.root.state.stone_at(Point(3, 3)) is Color.BLACK
    assert imported.tree.root.state.stone_at(Point(15, 15)) is Color.WHITE
    assert imported.tree.root.state.to_play is Color.WHITE


def test_fox_komi_and_rule_name_are_normalized_for_katago(tmp_path: Path) -> None:
    source = tmp_path / "fox.sgf"
    source.write_text(
        "(;FF[4]GM[1]SZ[19]RU[Chinese]KM[375];B[pd];W[dd])",
        encoding="utf-8",
    )

    imported = import_sgf(source)

    assert imported.rules == "chinese"
    assert imported.komi == 7.5


def test_import_sgf_never_modifies_the_selected_source_file(tmp_path: Path) -> None:
    source = tmp_path / "read-only-source.sgf"
    original = b"(;FF[4]GM[1]SZ[19]GN[Original];B[pd];W[dd])"
    source.write_bytes(original)

    imported = import_sgf(source)

    assert imported.name == "Original"
    assert source.read_bytes() == original

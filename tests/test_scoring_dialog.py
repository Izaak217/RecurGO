from PySide6.QtCore import QObject, QPoint, Qt, Signal

from recurgo.domain import BoardState, Color, GameTree, Point
from recurgo.engine import AnalysisUpdate, EngineFailure, EngineFailureKind
from recurgo.ui.scoring_dialog import CompletedGameDialog, ScoringDialog


class EstimateEngine(QObject):
    analysis_updated = Signal(object)
    analysis_finished = Signal(object)
    failure_reported = Signal(object)

    def __init__(self):
        super().__init__()
        self.queries = []
        self.stops = 0

    def analyze(self, **kwargs):
        self.queries.append(kwargs)
        return f"estimate-{len(self.queries)}"

    def stop_analysis(self):
        self.stops += 1


def make_dialog(qtbot, *, initial=None, language="en"):
    tree = GameTree(
        BoardState.from_setup(
            {Point(0, 0): Color.BLACK, Point(2, 2): Color.WHITE},
            size=3,
        )
    )
    engine = EstimateEngine()
    dialog = ScoringDialog(
        tree.current.state,
        rules="chinese",
        komi=7.5,
        last_move=None,
        engine=engine,
        tree=tree,
        max_visits=1600,
        initial_ownership=initial,
        language=language,
    )
    qtbot.addWidget(dialog)
    return dialog, engine, tree


def update(tree, *, request="estimate-1", final=True, values=None, node=None):
    return AnalysisUpdate(
        request,
        node or tree.current_id,
        "scoring",
        {
            "ownership": values if values is not None else [1.0] * 5 + [-1.0] * 4,
            "isDuringSearch": not final,
        },
    )


def test_live_map_previews_but_waits_for_complete_final_position_search(qtbot):
    initial = [0.95] * 5 + [-0.95] * 4
    dialog, engine, tree = make_dialog(qtbot, initial=initial)
    assert not dialog.confirm_button.isEnabled()
    qtbot.waitUntil(lambda: len(engine.queries) == 1)
    assert engine.queries[0]["max_visits"] == 1600
    engine.analysis_updated.emit(update(tree, final=False))
    assert not dialog.confirm_button.isEnabled()
    engine.analysis_finished.emit(update(tree))
    assert dialog.ownership == (1,) * 5 + (-1,) * 4
    assert "Black area: 5" in dialog.score_label.text()
    assert "3.25 stones" in dialog.score_label.text()
    assert dialog.confirm_button.isEnabled()
    assert tree.current.state.stone_at(Point(0, 0)) is Color.BLACK


def test_mouse_edits_empty_and_occupied_points_and_all_brushes(qtbot):
    dialog, engine, tree = make_dialog(qtbot, initial=[0.0] * 9)
    dialog.show()
    ox, oy, cell = dialog.board._geometry()
    pos = QPoint(round(ox + cell), round(oy + cell))
    for expected in (1, -1, 0, 2):
        qtbot.mouseClick(dialog.board, Qt.MouseButton.LeftButton, pos=pos)
        assert dialog.ownership[4] == expected
    for brush, expected in ((1, 1), (2, -1), (3, 0), (4, 2)):
        dialog.brush_combo.setCurrentIndex(brush)
        qtbot.mouseClick(
            dialog.board, Qt.MouseButton.LeftButton, pos=QPoint(round(ox), round(oy))
        )
        assert dialog.ownership[0] == expected
    assert tree.current.state.stone_at(Point(0, 0)) is Color.BLACK
    dialog._reset_points()
    assert dialog.ownership == (2,) * 9
    dialog._edit_point(-1, 0)
    assert not dialog._overrides


def test_analysis_missing_map_preserves_budget_and_corrections(qtbot):
    dialog, engine, tree = make_dialog(qtbot)
    assert not dialog.confirm_button.isEnabled()
    dialog._confirm()
    assert dialog.confirmed_score is None
    qtbot.waitUntil(lambda: len(engine.queries) == 1)
    assert engine.queries[0]["max_visits"] == 1600
    assert engine.queries[0]["include_ownership"] is True
    assert engine.queries[0]["human_profile"] is None
    dialog.brush_combo.setCurrentIndex(2)
    dialog._edit_point(1, 1)
    engine.analysis_updated.emit(update(tree, final=False))
    assert not dialog._has_map
    engine.analysis_finished.emit(update(tree))
    assert dialog.ownership[4] == -1
    assert dialog.ownership[0] == 1
    dialog.refresh_button.click()
    engine.analysis_finished.emit(update(tree, request="estimate-2"))
    assert dialog.ownership[4] == -1
    dialog._reset_points()
    assert dialog.ownership[4] == 1


def test_wrong_request_node_late_and_invalid_results_do_not_overwrite(qtbot):
    dialog, engine, tree = make_dialog(qtbot, initial=[1.0] * 9)
    qtbot.waitUntil(lambda: len(engine.queries) == 1)
    engine.analysis_finished.emit(update(tree, request="old"))
    engine.analysis_finished.emit(update(tree, node="another-node"))
    assert dialog.ownership == (1,) * 9
    engine.analysis_finished.emit(update(tree, values=[float("nan")] * 9))
    assert dialog.ownership == (1,) * 9
    assert "failed" in dialog.source_label.text()
    dialog.refresh_button.click()
    engine.failure_reported.emit(
        EngineFailure(
            EngineFailureKind.PROCESS_EXITED,
            "test",
            True,
            request_id="estimate-2",
        )
    )
    assert dialog.ownership == (1,) * 9
    dialog.refresh_button.click()
    dialog.reject()
    engine.analysis_finished.emit(update(tree, request="estimate-3"))
    assert dialog.ownership == (1,) * 9
    assert engine.stops == 1


def test_confirmation_uses_edited_map_and_freezes_every_control(qtbot):
    dialog, engine, tree = make_dialog(qtbot, initial=[1.0] * 5 + [-1.0] * 4)
    qtbot.waitUntil(lambda: len(engine.queries) == 1)
    engine.analysis_finished.emit(update(tree))
    dialog._edit_point(0, 0)  # Black -> White: margin drops by two points.
    dialog._confirm()
    assert dialog.confirmed_score.black_area == 4
    assert dialog.confirmed_score.white_area == 5
    assert dialog.confirmed_score.dead_black == 1
    assert dialog.confirmed_score.sgf_result == "W+4.25"
    assert not dialog.board.input_enabled
    before = dialog.ownership
    dialog._edit_point(1, 1)
    dialog._reset_points()
    assert dialog.ownership == before
    assert dialog.confirm_button.isHidden()
    assert not dialog.stay_button.isHidden()
    dialog._new_game()
    assert dialog.action == "new"


def test_close_before_delayed_request_and_manual_fallback(qtbot):
    dialog, engine, _tree = make_dialog(qtbot, language="zh")
    dialog.reject()
    qtbot.wait(10)
    assert not engine.queries
    manual = ScoringDialog(BoardState.new(size=3), rules="chinese", komi=7.5, last_move=None)
    qtbot.addWidget(manual)
    assert not manual.refresh_button.isEnabled()
    manual.brush_combo.setCurrentIndex(3)
    for y in range(3):
        for x in range(3):
            manual._edit_point(x, y)
    manual._confirm()
    assert manual.confirmed_score.black_area == 4.5
    assert manual.confirmed_score.white_area == 4.5
    completed = CompletedGameDialog("白胜¼子")
    qtbot.addWidget(completed)
    completed._new_game()
    assert completed.action == "new"


def test_dead_group_can_be_restored_or_removed_before_sharing(qtbot):
    state = BoardState.from_setup({Point(0, 0): Color.BLACK, Point(1, 0): Color.BLACK}, size=3)
    dialog = ScoringDialog(
        state, rules="chinese", komi=0, last_move=None, confirmed_ownership=(1,) * 9
    )
    qtbot.addWidget(dialog)
    dialog.brush_combo.setCurrentIndex(3)
    dialog._edit_point(0, 0)
    assert not dialog.confirm_button.isEnabled()
    dialog.brush_combo.setCurrentIndex(5)
    dialog._edit_point(0, 0)
    assert dialog.ownership[:2] == (2, 2)
    assert len(dialog.dead_points) == 2
    dialog.brush_combo.setCurrentIndex(3)
    dialog._edit_point(0, 0)
    dialog._edit_point(1, 0)
    assert dialog.confirm_button.isEnabled()
    dialog.brush_combo.setCurrentIndex(5)
    dialog._edit_point(0, 0)
    assert dialog.ownership[:2] == (1, 1)
    assert not dialog.dead_points


def test_invalid_komi_and_other_rules_cannot_confirm(qtbot):
    for rules, komi in (("japanese", 6.5), ("chinese", 0.25)):
        dialog = ScoringDialog(
            BoardState.new(size=3),
            rules=rules,
            komi=komi,
            last_move=None,
            confirmed_ownership=(1,) * 9,
        )
        qtbot.addWidget(dialog)
        assert not dialog.confirm_button.isEnabled()

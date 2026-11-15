from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from recurgo.domain.board import BoardState, Color
from recurgo.domain.coordinates import Point, gtp_to_point
from recurgo.domain.game_tree import GameTree
from recurgo.reporting.data import build_report_data, list_report_sources
from recurgo.storage import GameRecord, GameRepository


def _payload(
    winrate: float = 0.6,
    *,
    move: str = "D4",
    score: float = 2.0,
    complete: bool = True,
    visits: int = 800,
    pv: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "rootInfo": {"winrate": winrate, "scoreLead": score, "visits": visits},
        "moveInfos": [
            {
                "move": move,
                "order": 0,
                "winrate": winrate,
                "scoreLead": score,
                "visits": visits,
                "pv": [move, "pass"] if pv is None else pv,
            }
        ],
        "isDuringSearch": not complete,
    }


def _save(
    repository: GameRepository,
    game_id: str,
    node_id: str,
    payload: dict[str, Any],
    *,
    identity: str = "source-a",
    model: str = "model-a",
    config: str = "config-a",
    visits: int = 800,
    cache_key: str | None = None,
    extra_parameters: dict[str, Any] | None = None,
) -> None:
    parameters = {"maxVisits": visits, "configSha256": config}
    if identity:
        parameters["analysisIdentity"] = identity
    parameters.update(extra_parameters or {})
    repository.save_analysis_snapshot(
        game_id=game_id,
        node_id=node_id,
        analysis_identity=identity,
        cache_key=cache_key or f"full-game-{visits}",
        engine_version="1.18.2",
        model_hash=model,
        parameters=parameters,
        result=payload,
    )


def _repository(
    tmp_path: Path,
    *,
    state: BoardState | None = None,
) -> tuple[GameRepository, GameRecord, GameTree]:
    tree = GameTree(state)
    repository = GameRepository(tmp_path / "report.db")
    record = repository.create_game(tree)
    return repository, record, tree


def test_sources_isolate_identity_model_configuration_budget_and_simulation(
    tmp_path: Path,
) -> None:
    repository, record, tree = _repository(tmp_path)
    _save(repository, record.id, tree.root_id, _payload())
    for identity, model, config, visits in [
        ("source-b", "model-b", "config-b", 800),
        ("source-a", "model-a", "config-a", 1600),
        ("source-a", "different-model", "different-config", 2400),
    ]:
        _save(
            repository,
            record.id,
            tree.root_id,
            _payload(0.9, visits=visits),
            identity=identity,
            model=model,
            config=config,
            visits=visits,
        )
    _save(repository, record.id, tree.root_id, _payload(0.99), cache_key="ai-move-800")
    sources = list_report_sources(repository, record.id)
    assert len(sources) == 4
    source = next(
        item for item in sources if item.identity == "source-a" and item.visits == 800
    )
    report = build_report_data(repository, record, tree, source)
    assert report["nodes"][tree.root_id]["analysis"]["blackWinrate"] == 60.0
    assert report["source"]["modelHash"] == "model-a"
    repository.close()


def test_complete_snapshot_is_not_replaced_by_new_partial_record(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    _save(repository, record.id, tree.root_id, _payload(0.6))
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(0.1, complete=False, visits=10),
        cache_key="realtime-800-0-human-test",
    )
    source = list_report_sources(repository, record.id)[0]
    assert source.completed_positions == 1
    assert source.available_positions == 1
    report = build_report_data(repository, record, tree, source)
    assert report["nodes"][tree.root_id]["analysis"]["blackWinrate"] == 60.0
    repository.close()


def test_review_uses_parent_recommendation_child_position_and_preserves_branch(
    tmp_path: Path,
) -> None:
    repository, record, tree = _repository(tmp_path)
    root_id = tree.root_id
    _save(repository, record.id, root_id, _payload(0.7, move="D4", score=5))
    played, _ = tree.play(gtp_to_point("C3"))
    repository.save_node(record.id, played)
    _save(repository, record.id, played.id, _payload(0.5, move="Q16", score=1))
    tree.go_to(root_id)
    branch, _ = tree.play(gtp_to_point("D4"))
    repository.save_node(record.id, branch)
    original_tree = deepcopy(tree)
    before_changes = repository.connection.total_changes
    source = list_report_sources(repository, record.id)[0]
    report = build_report_data(repository, record, tree, source)
    reviewed = report["nodes"][played.id]
    assert reviewed["review"]["bestMove"] == "D4"
    assert reviewed["analysis"]["candidates"][0]["move"] == "Q16"
    assert reviewed["review"]["winrateLoss"] == pytest.approx(20)
    assert reviewed["review"]["scoreLoss"] == pytest.approx(4)
    assert reviewed["review"]["grade"] == "严重失误"
    assert report["nodes"][branch.id]["review"]["grade"] is None
    assert report["nodes"][branch.id]["review"]["complete"] is False
    assert report["defaultLine"] == [root_id, branch.id]
    assert report["nodes"][root_id]["children"] == [played.id, branch.id]
    assert tree.current_id == original_tree.current_id
    assert tree.nodes == original_tree.nodes
    assert repository.connection.total_changes == before_changes
    repository.close()


@pytest.mark.parametrize("size", [9, 13, 19])
def test_pv_handles_capture_pass_and_occupied_point_without_mutation(
    tmp_path: Path, size: int
) -> None:
    state = BoardState.from_setup(
        {
            Point(1, size - 2): Color.WHITE,
            Point(0, size - 2): Color.BLACK,
            Point(2, size - 2): Color.BLACK,
            Point(1, size - 3): Color.BLACK,
        },
        size=size,
    )
    repository, record, tree = _repository(tmp_path, state=state)
    _save(repository, record.id, tree.root_id, _payload(move="B1", pv=["B1", "pass", "B1"]))
    report = build_report_data(
        repository, record, tree, list_report_sources(repository, record.id)[0]
    )
    candidate = report["nodes"][tree.root_id]["analysis"]["candidates"][0]
    assert candidate["pvTruncated"] is True
    assert len(candidate["pv"]) == 2
    assert candidate["pv"][0]["stones"][(size - 2) * size + 1] == 0
    assert candidate["pv"][0]["lastMove"] == {"x": 1, "y": size - 1}
    assert candidate["pv"][1]["move"] == "pass"
    assert candidate["pv"][1]["lastMove"] is None
    assert tree.root.state == state
    repository.close()


def test_pv_stops_at_ko_recapture(tmp_path: Path) -> None:
    state = BoardState.from_setup(
        {
            Point(1, 0): Color.WHITE,
            Point(0, 1): Color.WHITE,
            Point(2, 1): Color.WHITE,
            Point(1, 2): Color.WHITE,
            Point(0, 2): Color.BLACK,
            Point(2, 2): Color.BLACK,
            Point(1, 3): Color.BLACK,
        },
        size=9,
    )
    repository, record, tree = _repository(tmp_path, state=state)
    _save(repository, record.id, tree.root_id, _payload(move="B8", pv=["B8", "B7"]))
    report = build_report_data(
        repository, record, tree, list_report_sources(repository, record.id)[0]
    )
    candidate = report["nodes"][tree.root_id]["analysis"]["candidates"][0]
    assert len(candidate["pv"]) == 1
    assert candidate["pvTruncated"]
    repository.close()


@pytest.mark.parametrize("invalid_best", ["A1", "invalid", "", "T20"])
def test_missing_or_illegal_order_zero_never_promotes_other_candidates(
    tmp_path: Path,
    invalid_best: str,
) -> None:
    state = BoardState.from_setup({Point(0, 18): Color.BLACK})
    repository, record, tree = _repository(tmp_path, state=state)
    payload = _payload(move=invalid_best)
    payload["moveInfos"].append({"move": "D4", "order": 1, "visits": 800, "winrate": 0.6})
    _save(repository, record.id, tree.root_id, payload)
    report = build_report_data(
        repository, record, tree, list_report_sources(repository, record.id)[0]
    )
    assert report["nodes"][tree.root_id]["analysis"]["candidates"] == []
    repository.close()


def test_white_candidate_perspective_and_nonfinite_values_are_safe(tmp_path: Path) -> None:
    state = BoardState.new(to_play=Color.WHITE)
    repository, record, tree = _repository(tmp_path, state=state)
    payload = _payload(0.7, score=3.5)
    payload["humanPolicy"] = [float("nan")] * 362
    payload["moveInfos"].append(
        {
            "move": "Q16",
            "order": float("inf"),
            "winrate": float("nan"),
            "scoreLead": 1,
        }
    )
    _save(repository, record.id, tree.root_id, payload)
    report = build_report_data(
        repository, record, tree, list_report_sources(repository, record.id)[0]
    )
    candidate = report["nodes"][tree.root_id]["analysis"]["candidates"][0]
    assert candidate["winrate"] == pytest.approx(30)
    assert candidate["scoreLead"] == -3.5
    assert candidate["humanPolicy"] is None
    assert report["nodes"][tree.root_id]["analysis"]["blackWinrate"] == 70
    json.dumps(report, allow_nan=False)
    repository.close()


def test_legacy_sources_keep_unknown_parameter_sets_separate(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(),
        identity="",
        config="",
        extra_parameters={"difficulty": "最强"},
    )
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(0.3),
        identity="",
        config="",
        cache_key="realtime-800-0",
        extra_parameters={"difficulty": "中级"},
    )
    sources = list_report_sources(repository, record.id)
    assert len(sources) == 2
    assert all(source.identity.startswith("legacy-") for source in sources)
    report = build_report_data(repository, record, tree, sources[0])
    assert report["source"]["legacy"] is True
    repository.close()


def test_backfilled_winrate_is_display_only_and_does_not_create_review(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    repository.register_analysis_source(
        "source-a",
        engine_version="1.18.2",
        model_hash="model-a",
        config_hash="config-a",
    )
    repository.save_winrate_point(
        game_id=record.id,
        node_id=tree.root_id,
        max_visits=800,
        black_winrate=63,
        search_visits=800,
        is_complete=True,
        analysis_identity="source-a",
    )
    source = list_report_sources(repository, record.id)[0]
    assert source.completed_positions == 0
    report = build_report_data(repository, record, tree, source)
    analysis = report["nodes"][tree.root_id]["analysis"]
    assert analysis["status"] == "winrateOnly"
    assert analysis["blackWinrate"] == 63
    assert analysis["candidates"] == []
    repository.close()


def test_budget_conflicts_malformed_json_and_nonobjective_records_are_excluded(
    tmp_path: Path,
) -> None:
    repository, record, tree = _repository(tmp_path)
    _save(repository, record.id, tree.root_id, _payload(), cache_key="full-game-1600")
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(),
        cache_key="realtime-800-0",
        extra_parameters={"purpose": "ai_move"},
    )
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(),
        cache_key="realtime-800-1",
        extra_parameters={"analysisIdentity": "wrong-source"},
    )
    assert list_report_sources(repository, record.id) == []
    repository.connection.execute(
        "UPDATE analysis_snapshots SET result_json = ?",
        ("not-json",),
    )
    assert list_report_sources(repository, record.id) == []
    repository.close()


def test_partial_analysis_and_missing_first_candidate_are_explicit(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    payload = _payload(complete=False, visits=35)
    payload["moveInfos"][0]["order"] = 1
    _save(repository, record.id, tree.root_id, payload)
    played, _ = tree.play(gtp_to_point("D4"))
    repository.save_node(record.id, played)
    _save(repository, record.id, played.id, _payload(move="Q16"))
    source = list_report_sources(repository, record.id)[0]
    report = build_report_data(repository, record, tree, source)
    assert source.completed_positions == 1
    assert report["nodes"][tree.root_id]["analysis"]["status"] == "partial"
    assert report["nodes"][tree.root_id]["analysis"]["candidates"] == []
    review = report["nodes"][played.id]["review"]
    assert review["complete"] is False
    assert review["grade"] is None
    assert review["bestMove"] is None
    repository.close()


def test_pv_does_not_replay_a_different_candidate_and_repeated_exports_are_stable(
    tmp_path: Path,
) -> None:
    repository, record, tree = _repository(tmp_path)
    _save(repository, record.id, tree.root_id, _payload(move="D4", pv=["Q16", "D4"]))
    source = list_report_sources(repository, record.id)[0]
    first = build_report_data(repository, record, tree, source)
    second = build_report_data(repository, record, tree, source)
    candidate = first["nodes"][tree.root_id]["analysis"]["candidates"][0]
    assert candidate["pv"] == []
    assert candidate["pvTruncated"] is True
    assert first["nodes"] == second["nodes"]
    assert first["source"] == second["source"]
    repository.close()


def test_partial_backfill_cannot_appear_as_a_finished_chart_point(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    repository.register_analysis_source(
        "source-a",
        engine_version="1.18.2",
        model_hash="model-a",
        config_hash="config-a",
    )
    repository.save_winrate_point(
        game_id=record.id,
        node_id=tree.root_id,
        max_visits=800,
        black_winrate=63,
        search_visits=20,
        is_complete=False,
        analysis_identity="source-a",
    )
    assert list_report_sources(repository, record.id) == []
    repository.close()


def test_malformed_huge_values_do_not_overflow_export(tmp_path: Path) -> None:
    repository, record, tree = _repository(tmp_path)
    payload = _payload()
    payload["moveInfos"].append(
        {
            "move": "Q16",
            "order": 10**1000,
            "visits": 10**1000,
            "winrate": 0.6,
            "scoreLead": 0,
        }
    )
    _save(repository, record.id, tree.root_id, payload)
    source = list_report_sources(repository, record.id)[0]
    report = build_report_data(repository, record, tree, source)
    assert len(report["nodes"][tree.root_id]["analysis"]["candidates"]) == 1
    json.dumps(report, allow_nan=False)
    repository.close()


@pytest.mark.parametrize("color", [Color.BLACK, Color.WHITE])
def test_derived_score_loss_overflow_does_not_prevent_export(
    tmp_path: Path, color: Color
) -> None:
    repository, record, tree = _repository(tmp_path, state=BoardState.new(to_play=color))
    before_score = 1e308 if color is Color.BLACK else -1e308
    before_winrate = 0.7 if color is Color.BLACK else 0.3
    _save(
        repository,
        record.id,
        tree.root_id,
        _payload(before_winrate, move="D4", score=before_score),
    )
    played, _ = tree.play(gtp_to_point("C3"))
    repository.save_node(record.id, played)
    _save(repository, record.id, played.id, _payload(0.5, move="Q16", score=-before_score))
    source = list_report_sources(repository, record.id)[0]
    report = build_report_data(repository, record, tree, source)
    review = report["nodes"][played.id]["review"]
    assert review["scoreLoss"] is None
    assert review["winrateLoss"] == pytest.approx(20)
    assert review["complete"] is True
    assert review["grade"] == "严重失误"
    assert (
        json.loads(json.dumps(report, allow_nan=False))["nodes"][played.id]["review"][
            "scoreLoss"
        ]
        is None
    )
    repository.close()

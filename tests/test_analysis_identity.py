from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from recurgo.domain import GameTree, Point
from recurgo.engine.analysis_identity import AnalysisIdentity
from recurgo.storage import GameRepository


def _runtime(config: Path, **changes: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "engine_version": "1.18.2",
        "model_sha256": "tf3-model",
        "analysis_config": config,
        "human_model_sha256": "human-model",
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_identity_survives_install_path_and_log_changes_but_not_search_changes(
    tmp_path: Path,
) -> None:
    first = tmp_path / "source.cfg"
    second = tmp_path / "installed.cfg"
    first.write_text("# source\nlogDir = D:/logs\nnumSearchThreadsPerAnalysisThread = 16\n")
    second.write_text(
        "logDir=C:/user/logs\nhomeDataDir=D:/isolated\n"
        "cudaCacheDir=D:/isolated/cuda\nnumSearchThreadsPerAnalysisThread=16 # same\n"
    )
    baseline = AnalysisIdentity.from_runtime(_runtime(first))
    assert baseline == AnalysisIdentity.from_runtime(_runtime(second))
    second.write_text("numSearchThreadsPerAnalysisThread=32\n")
    assert baseline.key != AnalysisIdentity.from_runtime(_runtime(second)).key
    assert (
        baseline.key
        != AnalysisIdentity.from_runtime(_runtime(first, engine_version="1.16.5")).key
    )
    assert (
        baseline.key
        != AnalysisIdentity.from_runtime(_runtime(first, model_sha256="old-model")).key
    )
    assert (
        baseline.key
        != AnalysisIdentity.from_runtime(_runtime(first, engine_sha256="another-build")).key
    )
    assert (
        baseline.key
        != AnalysisIdentity.from_runtime(_runtime(first, backend="tensorrt")).key
    )


def test_human_output_is_isolated_without_splitting_objective_source(tmp_path: Path) -> None:
    config = tmp_path / "analysis.cfg"
    config.write_text("reportAnalysisWinratesAs=BLACK\n")
    first = AnalysisIdentity.from_runtime(_runtime(config))
    second = AnalysisIdentity.from_runtime(_runtime(config, human_model_sha256="human-v2"))
    assert first.key == second.key
    assert first.realtime_key(800, True, "rank_3k") != second.realtime_key(800, True, "rank_3k")
    assert first.realtime_key(800, True, "rank_3k") != first.realtime_key(800, True, "rank_6d")
    unavailable = AnalysisIdentity.from_runtime(None)
    assert not unavailable.is_available
    assert first.is_available
    assert unavailable.key != first.key
    assert AnalysisIdentity.from_runtime(SimpleNamespace()).key == unavailable.key


def _snapshot(repo: GameRepository, game: str, node: str, source: str, value: float) -> None:
    repo.save_analysis_snapshot(
        game_id=game,
        node_id=node,
        cache_key="full-game-800",
        engine_version=f"engine-{source}",
        model_hash=f"model-{source}",
        analysis_identity=source,
        parameters={"source": source},
        result={"rootInfo": {"winrate": value}},
    )


def test_upgrade_preserves_legacy_data_and_keeps_each_source_separate(tmp_path: Path) -> None:
    path = tmp_path / "preserved.db"
    repo = GameRepository(path)
    tree = GameTree()
    record = repo.create_game(tree)
    for source, winrate in (("", 30.0), ("old-engine", 40.0), ("tf3", 60.0)):
        _snapshot(repo, record.id, tree.root_id, source, winrate / 100)
        repo.queue_winrate_analysis(
            record.id,
            tree.root_id,
            max_visits=800,
            analysis_identity=source,
        )
        repo.save_winrate_point(
            game_id=record.id,
            node_id=tree.root_id,
            max_visits=800,
            black_winrate=winrate,
            search_visits=9,
            is_complete=False,
            analysis_identity=source,
        )
    repo.close()

    repo = GameRepository(path)
    for source, winrate in (("", 30.0), ("old-engine", 40.0), ("tf3", 60.0)):
        assert repo.analysis_snapshots_for_game(
            record.id,
            cache_keys=("full-game-800",),
            analysis_identity=source,
        ) == {tree.root_id: {"rootInfo": {"winrate": winrate / 100}}}
        if source:
            assert repo.analysis_winrates_for_game(
                record.id, analysis_identity=source,
            ) == {tree.root_id: pytest.approx(winrate)}
        assert repo.winrate_points_for_game(
            record.id,
            max_visits=800,
            analysis_identity=source,
        ) == {tree.root_id: winrate}
        assert repo.pending_winrate_nodes(
            record.id,
            max_visits=800,
            analysis_identity=source,
        ) == [tree.root_id]
    assert repo.analysis_snapshots_for_game(record.id, analysis_identity="new-config") == {}
    assert (
        repo.winrate_points_for_game(
            record.id,
            max_visits=800,
            analysis_identity="new-config",
        )
        == {}
    )
    assert (
        repo.pending_winrate_nodes(
            record.id,
            max_visits=800,
            analysis_identity="new-config",
        )
        == []
    )
    repo.save_winrate_point(
        game_id=record.id,
        node_id=tree.root_id,
        max_visits=800,
        black_winrate=65.0,
        search_visits=800,
        is_complete=True,
        analysis_identity="tf3",
    )
    assert (
        repo.pending_winrate_nodes(
            record.id,
            max_visits=800,
            analysis_identity="tf3",
        )
        == []
    )
    assert repo.pending_winrate_nodes(record.id, max_visits=800) == [tree.root_id]
    assert repo.pending_winrate_nodes(
        record.id,
        max_visits=800,
        analysis_identity="old-engine",
    ) == [tree.root_id]
    repo.close()


def test_snapshot_replacement_updates_provenance_and_parameters(tmp_path: Path) -> None:
    repo = GameRepository(tmp_path / "metadata.db")
    tree = GameTree()
    record = repo.create_game(tree)
    for version in ("old", "new"):
        repo.save_analysis_snapshot(
            game_id=record.id,
            node_id=tree.root_id,
            cache_key="realtime",
            engine_version=version,
            model_hash=f"model-{version}",
            parameters={"version": version},
            result={"version": version},
        )
    row = repo.connection.execute("SELECT * FROM analysis_snapshots").fetchone()
    assert row["engine_version"] == "new"
    assert row["model_hash"] == "model-new"
    assert json.loads(row["parameters_json"]) == {"version": "new"}
    assert json.loads(row["result_json"]) == {"version": "new"}
    repo.close()


def test_source_task_completion_remains_atomic(tmp_path: Path) -> None:
    repo = GameRepository(tmp_path / "atomic.db")
    tree = GameTree()
    record = repo.create_game(tree)
    repo.queue_winrate_analysis(
        record.id, tree.root_id, max_visits=800, analysis_identity="tf3"
    )
    with repo.connection:
        repo.connection.execute(
            "CREATE TRIGGER block_complete BEFORE DELETE ON winrate_tasks_by_source "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )
    with pytest.raises(sqlite3.DatabaseError):
        repo.save_winrate_point(
            game_id=record.id,
            node_id=tree.root_id,
            max_visits=800,
            black_winrate=50.0,
            search_visits=800,
            is_complete=True,
            analysis_identity="tf3",
        )
    assert (
        repo.winrate_points_for_game(record.id, max_visits=800, analysis_identity="tf3") == {}
    )
    assert repo.pending_winrate_nodes(
        record.id,
        max_visits=800,
        analysis_identity="tf3",
    ) == [tree.root_id]
    repo.close()


def test_undo_and_delete_cover_every_source_without_touching_other_games(
    tmp_path: Path,
) -> None:
    repo = GameRepository(tmp_path / "undo-delete.db")
    tree = GameTree()
    record = repo.create_game(tree)
    move, _ = tree.play(Point(3, 3))
    repo.save_node(record.id, move)
    other = GameTree()
    other_record = repo.create_game(other)
    for game, node in ((record.id, move.id), (other_record.id, other.root_id)):
        for source in ("", "old", "tf3"):
            _snapshot(repo, game, node, source, 0.5)
            repo.queue_winrate_analysis(game, node, max_visits=800, analysis_identity=source)
            repo.save_winrate_point(
                game_id=game,
                node_id=node,
                max_visits=800,
                black_winrate=50.0,
                search_visits=9,
                is_complete=False,
                analysis_identity=source,
            )
    repo.remove_subtree(record.id, move.id, current_node_id=tree.root_id)
    for source in ("", "old", "tf3"):
        assert (
            repo.winrate_points_for_game(
                record.id,
                max_visits=800,
                analysis_identity=source,
            )
            == {}
        )
        assert repo.pending_winrate_nodes(
            other_record.id,
            max_visits=800,
            analysis_identity=source,
        ) == [other.root_id]
    repo.delete_game(other_record.id)
    for table in (
        "analysis_snapshots",
        "winrate_points",
        "winrate_tasks",
        "winrate_points_by_source",
        "winrate_tasks_by_source",
    ):
        assert repo.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    repo.close()


def test_legacy_node_deletion_remains_compatible_with_new_source_tables(tmp_path: Path) -> None:
    repo = GameRepository(tmp_path / "rollback-compatibility.db")
    tree = GameTree()
    record = repo.create_game(tree)
    move, _ = tree.play(Point(3, 3))
    repo.save_node(record.id, move)
    repo.queue_winrate_analysis(record.id, move.id, max_visits=800, analysis_identity="tf3")
    repo.save_winrate_point(
        game_id=record.id, node_id=move.id, max_visits=800,
        black_winrate=60.0, search_visits=9, is_complete=False, analysis_identity="tf3",
    )
    # A rolled-back executable knows only the old tables. Deleting its node
    # must remain transactional rather than failing on a newly added FK.
    with repo.connection:
        repo.connection.execute(
            "UPDATE games SET current_node_id = ? WHERE id = ?", (tree.root_id, record.id),
        )
        repo.connection.execute("DELETE FROM game_nodes WHERE id = ?", (move.id,))
    assert repo.pending_winrate_nodes(record.id, max_visits=800, analysis_identity="tf3") == []
    assert repo.winrate_points_for_game(
        record.id, max_visits=800, analysis_identity="tf3",
    ) == {}
    repo.close()

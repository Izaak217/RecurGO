from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from recurgo.domain import GameTree, Point
from recurgo.domain.score_review import score_ownership
from recurgo.storage import GameRepository


def test_game_and_variations_survive_repository_reopen(tmp_path: Path) -> None:
    database_path = tmp_path / "coach.db"
    repository = GameRepository(database_path)
    tree = GameTree()
    record = repository.create_game(tree, name="自动保存测试")

    first, _ = tree.play(Point(3, 3))
    repository.save_node(record.id, first)
    main_line, _ = tree.play(Point(15, 15))
    repository.save_node(record.id, main_line)

    parent = tree.undo()
    repository.set_current(record.id, parent.id)
    variation, _ = tree.play(Point(15, 3))
    repository.save_node(record.id, variation)
    repository.close()

    reopened = GameRepository(database_path)
    loaded_record, loaded_tree = reopened.load_game(record.id)
    assert loaded_record.name == "自动保存测试"
    assert loaded_tree.current.id == variation.id
    assert loaded_tree.current.state.move_number == 2
    assert len(loaded_tree.nodes[first.id].children) == 2
    assert reopened.latest_game() is not None
    reopened.close()


def test_repository_persists_game_mode(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "games.db")
    tree = GameTree()
    record = repository.create_game(tree)

    repository.update_mode(record.id, "assisted")
    loaded, _tree = repository.load_game(record.id)

    assert loaded.mode == "assisted"
    repository.close()


def test_repository_persists_human_color(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "color.db")
    tree = GameTree()
    record = repository.create_game(tree, mode="assisted", human_color="white")

    loaded, _tree = repository.load_game(record.id)
    assert loaded.human_color == "white"

    repository.update_human_color(record.id, "black")
    updated, _tree = repository.load_game(record.id)
    assert updated.human_color == "black"
    repository.close()


def test_repository_persists_and_updates_difficulty(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "difficulty.db")
    record = repository.create_game(
        GameTree(),
        mode="assisted",
        difficulty="高级",
    )

    created, _tree = repository.load_game(record.id)
    assert created.difficulty == "高级"

    repository.update_difficulty(record.id, "顶级")
    updated, _tree = repository.load_game(record.id)
    assert updated.difficulty == "顶级"
    repository.close()


def test_repository_persists_and_updates_game_name_and_players(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "metadata.db")
    record = repository.create_game(
        GameTree(),
        name="最初名称",
        black_player="黑方甲",
        white_player="白方乙",
    )

    repository.update_metadata(
        record.id,
        name="修改后的棋谱",
        black_player="黑方丙",
        white_player="白方丁",
    )
    loaded, _tree = repository.load_game(record.id)
    summary = repository.list_games()[0]

    assert loaded.name == "修改后的棋谱"
    assert loaded.black_player == "黑方丙"
    assert loaded.white_player == "白方丁"
    assert summary.black_player == "黑方丙"
    assert summary.white_player == "白方丁"
    repository.close()


def test_repository_adds_player_columns_to_existing_database(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-metadata.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE games (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            board_size INTEGER NOT NULL,
            rules TEXT NOT NULL,
            komi REAL NOT NULL,
            mode TEXT NOT NULL,
            human_color TEXT NOT NULL DEFAULT 'black',
            status TEXT NOT NULL,
            result TEXT NOT NULL DEFAULT '',
            random_seed INTEGER NOT NULL,
            root_node_id TEXT NOT NULL,
            current_node_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.close()

    repository = GameRepository(database_path)
    columns = {
        str(row["name"])
        for row in repository.connection.execute("PRAGMA table_info(games)").fetchall()
    }
    record = repository.create_game(GameTree(), black_player="黑", white_player="白")

    assert {"black_player", "white_player"} <= columns
    assert repository.load_game(record.id)[0].black_player == "黑"
    assert repository.load_game(record.id)[0].white_player == "白"
    repository.close()


def test_repository_adds_default_difficulty_to_existing_database(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-difficulty.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE games (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            black_player TEXT NOT NULL DEFAULT '',
            white_player TEXT NOT NULL DEFAULT '',
            board_size INTEGER NOT NULL,
            rules TEXT NOT NULL,
            komi REAL NOT NULL,
            mode TEXT NOT NULL,
            human_color TEXT NOT NULL DEFAULT 'black',
            status TEXT NOT NULL,
            result TEXT NOT NULL DEFAULT '',
            random_seed INTEGER NOT NULL,
            root_node_id TEXT NOT NULL,
            current_node_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO games (
            id, name, black_player, white_player, board_size, rules, komi, mode,
            human_color, status, result, random_seed, root_node_id, current_node_id,
            created_at, updated_at
        ) VALUES (
            'legacy-game', '旧棋谱', '', '', 19, 'chinese', 7.5, 'assisted',
            'black', 'in_progress', '', 1, 'root', 'root',
            '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
        )
        """
    )
    connection.commit()
    connection.close()

    reopened = GameRepository(database_path)
    columns = {
        str(row["name"])
        for row in reopened.connection.execute("PRAGMA table_info(games)").fetchall()
    }
    difficulty = reopened.connection.execute(
        "SELECT difficulty FROM games WHERE id = 'legacy-game'"
    ).fetchone()[0]

    assert "difficulty" in columns
    assert difficulty == "中级"
    reopened.close()


def test_repository_lists_saved_games_with_move_counts(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "games.db")
    tree = GameTree()
    record = repository.create_game(tree, name="可恢复棋谱")
    move, _created = tree.play(Point(3, 3))
    repository.save_node(record.id, move)

    summaries = repository.list_games()

    assert len(summaries) == 1
    assert summaries[0].id == record.id
    assert summaries[0].name == "可恢复棋谱"
    assert summaries[0].move_count == 1
    repository.close()


def test_repository_can_list_all_games_without_the_default_limit(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "unlimited-list.db")
    for index in range(3):
        repository.create_game(GameTree(), name=f"棋谱 {index}")

    assert len(repository.list_games(limit=2)) == 2
    assert len(repository.list_games(limit=None)) == 3
    repository.close()


def test_import_game_tree_persists_whole_tree_and_result_atomically(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "atomic-import.db")
    tree = GameTree()
    first, _created = tree.play(Point(3, 3))
    main, _created = tree.play(Point(15, 15))
    tree.go_to(first.id)
    variation, _created = tree.play(Point(15, 3))
    tree.go_to(main.id)

    record = repository.import_game_tree(
        tree,
        name="原子导入",
        black_player="黑方",
        white_player="白方",
        result="B+R",
    )
    loaded_record, loaded_tree = repository.load_game(record.id)

    assert loaded_record.status == "completed"
    assert loaded_record.result == "B+R"
    assert loaded_tree.current.id == main.id
    assert set(loaded_tree.nodes) == {tree.root_id, first.id, main.id, variation.id}
    assert set(loaded_tree.nodes[first.id].children) == {main.id, variation.id}
    repository.close()


def test_import_game_tree_rolls_back_game_and_nodes_on_node_failure(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "atomic-import-rollback.db")
    with repository.connection:
        repository.connection.execute(
            """
            CREATE TRIGGER block_second_imported_move
            BEFORE INSERT ON game_nodes
            WHEN NEW.move_number = 2
            BEGIN
                SELECT RAISE(ABORT, 'blocked imported node');
            END
            """
        )
    tree = GameTree()
    tree.play(Point(3, 3))
    tree.play(Point(15, 15))

    with pytest.raises(sqlite3.DatabaseError):
        repository.import_game_tree(tree, name="不应留下")

    assert repository.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    assert repository.connection.execute("SELECT COUNT(*) FROM game_nodes").fetchone()[0] == 0
    repository.close()


def test_repository_restores_saved_black_winrates_by_node(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "analysis.db")
    tree = GameTree()
    record = repository.create_game(tree)
    black_move, _created = tree.play(Point(3, 3))
    repository.save_node(record.id, black_move)
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=tree.root_id,
        cache_key="realtime",
        engine_version="test",
        model_hash="test-model",
        parameters={"maxVisits": 10},
        result={"rootInfo": {"winrate": 0.625}},
    )
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=black_move.id,
        cache_key="realtime",
        engine_version="test",
        model_hash="test-model",
        parameters={"maxVisits": 10},
        result={"rootInfo": {"winrate": 0.343}},
    )

    restored = repository.analysis_winrates_for_game(record.id)

    assert restored == {
        tree.root_id: 62.5,
        black_move.id: pytest.approx(34.3),
    }
    repository.close()


def test_repository_restores_full_analysis_payloads_by_cache_prefix(
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "analysis-payloads.db")
    tree = GameTree()
    record = repository.create_game(tree)
    realtime_payload = {"rootInfo": {"winrate": 0.55}}
    full_payload = {
        "rootInfo": {"winrate": 0.60},
        "moveInfos": [{"move": "D4"}],
    }
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=tree.root_id,
        cache_key="realtime-800-0",
        engine_version="test",
        model_hash="test-model",
        parameters={"maxVisits": 800},
        result=realtime_payload,
    )
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=tree.root_id,
        cache_key="full-game-800",
        engine_version="test",
        model_hash="test-model",
        parameters={"maxVisits": 800},
        result=full_payload,
    )

    full_snapshots = repository.analysis_snapshots_for_game(
        record.id,
        cache_prefix="full-game-800",
    )

    assert full_snapshots == {tree.root_id: full_payload}
    repository.close()


def test_repository_persists_completed_game_result(tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "result.db")
    tree = GameTree()
    record = repository.create_game(tree)

    repository.finish_game(record.id, "W+0.25")
    loaded, _tree = repository.load_game(record.id)
    summary = repository.list_games()[0]

    assert loaded.status == "completed"
    assert loaded.result == "W+0.25"
    assert summary.result == "W+0.25"
    repository.close()


def test_review_map_survives_reopen_and_rejects_mismatched_result(tmp_path: Path) -> None:
    database_path = tmp_path / "review-map.db"
    repository = GameRepository(database_path)
    tree = GameTree()
    record = repository.create_game(tree)
    owners = (1,) * 180 + (-1,) * 180 + (0,)
    result = score_ownership(tree.current.state, owners, komi=7.5).sgf_result
    with pytest.raises(ValueError, match="match"):
        repository.finish_game(
            record.id, "B+100", scoring_node_id=tree.current_id, ownership=owners
        )
    assert repository.load_game(record.id)[0].status == "in_progress"
    repository.finish_game(record.id, result, scoring_node_id=tree.current_id, ownership=owners)
    repository.close()
    reopened = GameRepository(database_path)
    assert reopened.load_scoring(record.id) == (tree.current_id, owners, frozenset())
    assert reopened.load_game(record.id)[0].result == result
    reopened.close()


@pytest.mark.parametrize("corruption", ["missing_node", "unassigned", "empty_dead", "result"])
def test_invalid_saved_review_falls_back_to_recorded_result(
    tmp_path: Path, corruption: str,
) -> None:
    repository = GameRepository(tmp_path / "invalid-review.db")
    tree = GameTree()
    record = repository.create_game(tree)
    owners = [1] * 361
    payload = {"node_id": tree.current_id, "ownership": owners, "dead": []}
    result = score_ownership(tree.current.state, owners, komi=7.5).sgf_result
    if corruption == "missing_node":
        payload["node_id"] = "not-in-this-game"
    elif corruption == "unassigned":
        owners[0] = 2
    elif corruption == "empty_dead":
        payload["dead"] = [0]
    else:
        result = "W+1"
    with repository.connection:
        repository.connection.execute(
            "UPDATE games SET scoring_json = ?, result = ? WHERE id = ?",
            (json.dumps(payload), result, record.id),
        )
    assert repository.load_scoring(record.id) is None
    repository.close()


def test_repository_persists_global_app_settings(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.db"
    repository = GameRepository(database_path)
    repository.save_setting(
        "appearance_audio",
        {"board_theme": "dark", "volume": 54, "muted": True},
    )
    repository.close()

    reopened = GameRepository(database_path)
    assert reopened.load_setting("appearance_audio") == {
        "board_theme": "dark",
        "volume": 54,
        "muted": True,
    }
    assert reopened.load_setting("missing") is None
    with reopened.connection:
        reopened.connection.execute(
            "INSERT INTO app_settings (key, value_json, updated_at) VALUES (?, ?, ?)",
            ("corrupt", "{", "now"),
        )
    assert reopened.load_setting("corrupt") is None
    reopened.close()


def test_repository_repairs_legacy_fox_komi_on_reopen(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-fox.db"
    repository = GameRepository(database_path)
    tree = GameTree()
    record = repository.create_game(tree, rules="Chinese", komi=375.0)
    repository.close()

    reopened = GameRepository(database_path)
    repaired, _tree = reopened.load_game(record.id)

    assert repaired.rules == "chinese"
    assert repaired.komi == 7.5
    reopened.close()


def test_delete_game_removes_nodes_and_analysis_but_keeps_other_games(
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "delete.db")
    doomed_tree = GameTree()
    doomed = repository.create_game(doomed_tree, name="待删除")
    move, _created = doomed_tree.play(Point(3, 3))
    repository.save_node(doomed.id, move)
    repository.save_analysis_snapshot(
        game_id=doomed.id,
        node_id=doomed_tree.root_id,
        cache_key="full-game-800",
        engine_version="test",
        model_hash="test",
        parameters={},
        result={"rootInfo": {"winrate": 0.5}},
    )
    kept = repository.create_game(GameTree(), name="保留")

    repository.delete_game(doomed.id)

    with pytest.raises(KeyError):
        repository.load_game(doomed.id)
    assert repository.load_game(kept.id)[0].name == "保留"
    assert (
        repository.connection.execute(
            "SELECT COUNT(*) FROM game_nodes WHERE game_id = ?",
            (doomed.id,),
        ).fetchone()[0]
        == 0
    )
    assert (
        repository.connection.execute(
            "SELECT COUNT(*) FROM analysis_snapshots WHERE game_id = ?",
            (doomed.id,),
        ).fetchone()[0]
        == 0
    )
    repository.close()


def test_delete_game_rolls_back_all_changes_when_a_dependent_delete_fails(
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "delete-rollback.db")
    tree = GameTree()
    record = repository.create_game(tree, name="事务回滚")
    move, _created = tree.play(Point(3, 3))
    repository.save_node(record.id, move)
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=tree.root_id,
        cache_key="full-game-800",
        engine_version="test",
        model_hash="test",
        parameters={},
        result={"rootInfo": {"winrate": 0.5}},
    )
    with repository.connection:
        repository.connection.execute(
            """
            CREATE TRIGGER block_node_deletion
            BEFORE DELETE ON game_nodes
            BEGIN
                SELECT RAISE(ABORT, 'blocked for rollback test');
            END
            """
        )

    with pytest.raises(sqlite3.DatabaseError):
        repository.delete_game(record.id)

    assert repository.load_game(record.id)[0].name == "事务回滚"
    assert (
        repository.connection.execute(
            "SELECT COUNT(*) FROM game_nodes WHERE game_id = ?",
            (record.id,),
        ).fetchone()[0]
        == 2
    )
    assert (
        repository.connection.execute(
            "SELECT COUNT(*) FROM analysis_snapshots WHERE game_id = ?",
            (record.id,),
        ).fetchone()[0]
        == 1
    )
    repository.close()

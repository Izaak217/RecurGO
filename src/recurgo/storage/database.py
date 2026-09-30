"""SQLite game repository with per-move transactional autosave."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from recurgo.domain.board import BoardState, Color
from recurgo.domain.coordinates import Point
from recurgo.domain.game_tree import GameNode, GameTree, Move
from recurgo.domain.score_review import score_ownership, validate_assignments

from .sgf_io import normalize_sgf_komi, normalize_sgf_rules


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class GameRecord:
    id: str
    name: str
    black_player: str
    white_player: str
    board_size: int
    rules: str
    komi: float
    mode: str
    human_color: str
    difficulty: str
    status: str
    result: str
    random_seed: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class GameSummary:
    id: str
    name: str
    black_player: str
    white_player: str
    move_count: int
    mode: str
    status: str
    result: str
    updated_at: str


class GameRepository:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = NORMAL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    black_player TEXT NOT NULL DEFAULT '',
                    white_player TEXT NOT NULL DEFAULT '',
                    board_size INTEGER NOT NULL,
                    rules TEXT NOT NULL,
                    komi REAL NOT NULL,
                    mode TEXT NOT NULL,
                    human_color TEXT NOT NULL DEFAULT 'black',
                    difficulty TEXT NOT NULL DEFAULT '中级',
                    status TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '',
                    random_seed INTEGER NOT NULL,
                    root_node_id TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS game_nodes (
                    id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL REFERENCES games(id),
                    parent_id TEXT,
                    move_number INTEGER NOT NULL,
                    color INTEGER,
                    x INTEGER,
                    y INTEGER,
                    is_pass INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_game_nodes_game
                    ON game_nodes(game_id, move_number, created_at);

                CREATE TABLE IF NOT EXISTS analysis_snapshots (
                    id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL REFERENCES games(id),
                    node_id TEXT NOT NULL REFERENCES game_nodes(id),
                    cache_key TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    model_hash TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(node_id, cache_key)
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(
                "games",
                "result",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                "games",
                "human_color",
                "TEXT NOT NULL DEFAULT 'black'",
            )
            self._ensure_column(
                "games",
                "difficulty",
                "TEXT NOT NULL DEFAULT '中级'",
            )
            self._ensure_column(
                "games",
                "black_player",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                "games",
                "white_player",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._normalize_legacy_game_metadata()
            self._ensure_column("games", "scoring_json", "TEXT NOT NULL DEFAULT ''")

    def _normalize_legacy_game_metadata(self) -> None:
        """Repair metadata imported before Fox SGF normalization was added."""
        rows = self.connection.execute("SELECT id, rules, komi FROM games").fetchall()
        for row in rows:
            original_rules = str(row["rules"])
            original_komi = float(row["komi"])
            rules = normalize_sgf_rules(original_rules)
            komi = normalize_sgf_komi(original_komi, rules)
            if rules == original_rules and komi == original_komi:
                continue
            self.connection.execute(
                "UPDATE games SET rules = ?, komi = ? WHERE id = ?",
                (rules, komi, str(row["id"])),
            )

    def _ensure_column(
        self,
        table_name: str,
        column_name: str,
        declaration: str,
    ) -> None:
        columns = {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            self.connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {declaration}"
            )

    def create_game(
        self,
        tree: GameTree,
        *,
        name: str = "未命名棋局",
        black_player: str = "",
        white_player: str = "",
        rules: str = "chinese",
        komi: float = 7.5,
        mode: str = "manual",
        human_color: str = "black",
        difficulty: str = "中级",
        random_seed: int | None = None,
    ) -> GameRecord:
        record = self._new_record(
            tree,
            name=name,
            black_player=black_player,
            white_player=white_player,
            rules=rules,
            komi=komi,
            mode=mode,
            human_color=human_color,
            difficulty=difficulty,
            status="in_progress",
            result="",
            random_seed=random_seed,
        )
        with self.connection:
            self._insert_game(record, tree)
            self._upsert_node(record.id, tree.root)
        return record

    def import_game_tree(
        self,
        tree: GameTree,
        *,
        name: str,
        black_player: str = "",
        white_player: str = "",
        rules: str = "chinese",
        komi: float = 7.5,
        result: str = "",
        mode: str = "manual",
        human_color: str = "black",
        difficulty: str = "中级",
        random_seed: int | None = None,
    ) -> GameRecord:
        """Persist a complete imported tree in one all-or-nothing transaction.

        Unlike ``create_game`` followed by repeated ``save_node`` calls, no game,
        branch, or partial result remains if inserting any node fails.
        """
        record = self._new_record(
            tree,
            name=name,
            black_player=black_player,
            white_player=white_player,
            rules=rules,
            komi=komi,
            mode=mode,
            human_color=human_color,
            difficulty=difficulty,
            status="completed" if result else "in_progress",
            result=result,
            random_seed=random_seed,
        )
        with self.connection:
            self._insert_game(record, tree)
            for node in tree.nodes.values():
                self._upsert_node(record.id, node)
        return record

    def save_node(self, game_id: str, node: GameNode) -> None:
        timestamp = _now()
        with self.connection:
            self._upsert_node(game_id, node)
            self.connection.execute(
                """
                UPDATE games
                SET current_node_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (node.id, timestamp, game_id),
            )

    def set_current(self, game_id: str, node_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE games
                SET current_node_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (node_id, _now(), game_id),
            )

    def update_mode(self, game_id: str, mode: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE games
                SET mode = ?, updated_at = ?
                WHERE id = ?
                """,
                (mode, _now(), game_id),
            )

    def update_human_color(self, game_id: str, human_color: str) -> None:
        if human_color not in {"black", "white"}:
            raise ValueError(f"Unsupported human color: {human_color}")
        with self.connection:
            self.connection.execute(
                """
                UPDATE games
                SET human_color = ?, updated_at = ?
                WHERE id = ?
                """,
                (human_color, _now(), game_id),
            )

    def update_difficulty(self, game_id: str, difficulty: str) -> None:
        normalized = difficulty.strip()
        if not normalized:
            raise ValueError("Difficulty must not be empty")
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE games
                SET difficulty = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, _now(), game_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(game_id)

    def update_metadata(
        self,
        game_id: str,
        *,
        name: str,
        black_player: str,
        white_player: str,
    ) -> None:
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE games
                SET name = ?, black_player = ?, white_player = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, black_player, white_player, _now(), game_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(game_id)

    def load_setting(self, key: str) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(str(row["value_json"]))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def save_setting(self, key: str, value: dict[str, object]) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    json.dumps(value, separators=(",", ":"), ensure_ascii=False),
                    _now(),
                ),
            )

    def delete_game(self, game_id: str) -> None:
        """Delete one saved game and its locally cached analysis results."""
        with self.connection:
            self.connection.execute(
                "DELETE FROM analysis_snapshots WHERE game_id = ?",
                (game_id,),
            )
            self.connection.execute(
                "DELETE FROM game_nodes WHERE game_id = ?",
                (game_id,),
            )
            cursor = self.connection.execute(
                "DELETE FROM games WHERE id = ?",
                (game_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(game_id)

    def finish_game(
        self, game_id: str, result: str, *, scoring_node_id: str | None = None,
        ownership: tuple[int, ...] | None = None,
        dead_points: frozenset[Point] = frozenset(),
    ) -> None:
        scoring_json = ""
        if ownership is not None:
            row = self.connection.execute(
                "SELECT g.board_size, g.komi, n.state_json FROM games g "
                "JOIN game_nodes n ON n.game_id = g.id "
                "WHERE g.id = ? AND n.id = ?", (game_id, scoring_node_id),
            ).fetchone()
            if (row is None
                    or validate_assignments(ownership, int(row["board_size"])) != ownership):
                raise ValueError("Scoring ownership must match a node in this game")
            state = _decode_state(str(row["state_json"]))
            expected = score_ownership(
                state, ownership, komi=float(row["komi"]), dead_points=dead_points,
            )
            if expected.sgf_result != result:
                raise ValueError("Saved result must match the confirmed point assignments")
            scoring_json = json.dumps({
                "node_id": scoring_node_id, "ownership": ownership,
                "dead": sorted(p.y * state.size + p.x for p in dead_points),
            })
        with self.connection:
            self.connection.execute(
                """
                UPDATE games
                SET status = 'completed', result = ?, updated_at = ?, scoring_json = ?
                WHERE id = ?
                """,
                (result, _now(), scoring_json, game_id),
            )

    def load_scoring(
        self, game_id: str,
    ) -> tuple[str, tuple[int, ...], frozenset[Point]] | None:
        row = self.connection.execute(
            "SELECT board_size, scoring_json FROM games WHERE id = ?", (game_id,),
        ).fetchone()
        if row is None or not row["scoring_json"]:
            return None
        try:
            payload = json.loads(row["scoring_json"])
            size = int(row["board_size"])
            points = validate_assignments(payload.get("ownership"), size)
            node_id = payload.get("node_id")
            dead = payload.get("dead", [])
            if (points is not None and isinstance(node_id, str) and isinstance(dead, list)
                    and all(type(i) is int and 0 <= i < size * size for i in dead)):
                node = self.connection.execute(
                    "SELECT n.state_json, g.komi, g.result FROM game_nodes n "
                    "JOIN games g ON g.id = n.game_id WHERE n.id = ? AND g.id = ?",
                    (node_id, game_id),
                ).fetchone()
                if node is None:
                    return None
                dead_points = frozenset(Point(i % size, i // size) for i in dead)
                score = score_ownership(
                    _decode_state(str(node["state_json"])), points,
                    komi=float(node["komi"]), dead_points=dead_points,
                )
                if score.sgf_result == node["result"]:
                    return node_id, points, dead_points
        except (ValueError, TypeError, AttributeError):
            pass
        return None

    def save_analysis_snapshot(
        self,
        *,
        game_id: str,
        node_id: str,
        cache_key: str,
        engine_version: str,
        model_hash: str,
        parameters: dict[str, object],
        result: dict[str, object],
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO analysis_snapshots (
                    id, game_id, node_id, cache_key, engine_version, model_hash,
                    parameters_json, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id, cache_key) DO UPDATE SET
                    result_json = excluded.result_json,
                    created_at = excluded.created_at
                """,
                (
                    str(uuid4()),
                    game_id,
                    node_id,
                    cache_key,
                    engine_version,
                    model_hash,
                    json.dumps(parameters, separators=(",", ":"), ensure_ascii=False),
                    json.dumps(result, separators=(",", ":"), ensure_ascii=False),
                    _now(),
                ),
            )

    def latest_game(self) -> tuple[GameRecord, GameTree] | None:
        row = self.connection.execute(
            "SELECT id FROM games ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        return None if row is None else self.load_game(str(row["id"]))

    def list_games(self, *, limit: int | None = 200) -> list[GameSummary]:
        query = """
            SELECT
                games.id,
                games.name,
                games.black_player,
                games.white_player,
                games.mode,
                games.status,
                games.result,
                games.updated_at,
                COALESCE(MAX(game_nodes.move_number), 0) AS move_count
            FROM games
            LEFT JOIN game_nodes ON game_nodes.game_id = games.id
            GROUP BY games.id
            ORDER BY games.updated_at DESC
            """
        if limit is None:
            rows = self.connection.execute(query).fetchall()
        else:
            if limit < 0:
                raise ValueError("limit must be non-negative or None")
            rows = self.connection.execute(f"{query} LIMIT ?", (limit,)).fetchall()
        return [
            GameSummary(
                id=str(row["id"]),
                name=str(row["name"]),
                black_player=str(row["black_player"]),
                white_player=str(row["white_player"]),
                move_count=int(row["move_count"]),
                mode=str(row["mode"]),
                status=str(row["status"]),
                result=str(row["result"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def analysis_snapshots_for_game(
        self,
        game_id: str,
        *,
        cache_prefix: str | None = None,
        cache_keys: tuple[str, ...] | None = None,
    ) -> dict[str, dict[str, object]]:
        if cache_prefix is not None and cache_keys is not None:
            raise ValueError("cache_prefix and cache_keys cannot be combined")
        if cache_keys is not None:
            if not cache_keys:
                return {}
            placeholders = ", ".join("?" for _ in cache_keys)
            rows = self.connection.execute(
                f"""
                SELECT node_id, result_json
                FROM analysis_snapshots
                WHERE game_id = ? AND cache_key IN ({placeholders})
                ORDER BY created_at
                """,
                (game_id, *cache_keys),
            ).fetchall()
        elif cache_prefix is None:
            rows = self.connection.execute(
                """
                SELECT node_id, result_json
                FROM analysis_snapshots
                WHERE game_id = ?
                ORDER BY created_at
                """,
                (game_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT node_id, result_json
                FROM analysis_snapshots
                WHERE game_id = ? AND cache_key LIKE ?
                ORDER BY created_at
                """,
                (game_id, f"{cache_prefix}%"),
            ).fetchall()
        snapshots: dict[str, dict[str, object]] = {}
        for row in rows:
            payload = json.loads(str(row["result_json"]))
            if isinstance(payload, dict):
                snapshots[str(row["node_id"])] = payload
        return snapshots

    def analysis_winrates_for_game(self, game_id: str) -> dict[str, float]:
        snapshots = self.analysis_snapshots_for_game(game_id)
        winrates: dict[str, float] = {}
        for node_id, payload in snapshots.items():
            root_info = payload.get("rootInfo")
            if not isinstance(root_info, dict):
                continue
            raw_winrate = root_info.get("winrate")
            if isinstance(raw_winrate, (int, float)):
                winrates[node_id] = float(raw_winrate) * 100.0
        return winrates

    def load_game(self, game_id: str) -> tuple[GameRecord, GameTree]:
        game_row = self.connection.execute(
            "SELECT * FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if game_row is None:
            raise KeyError(game_id)
        node_rows = self.connection.execute(
            """
            SELECT * FROM game_nodes
            WHERE game_id = ?
            ORDER BY move_number, created_at
            """,
            (game_id,),
        ).fetchall()
        nodes: list[GameNode] = []
        for row in node_rows:
            move: Move | None = None
            if row["color"] is not None:
                point = None if bool(row["is_pass"]) else Point(int(row["x"]), int(row["y"]))
                move = Move(Color(int(row["color"])), point)
            nodes.append(
                GameNode(
                    id=str(row["id"]),
                    parent_id=(None if row["parent_id"] is None else str(row["parent_id"])),
                    move=move,
                    state=_decode_state(str(row["state_json"])),
                    comment=str(row["comment"]),
                    created_at=str(row["created_at"]),
                )
            )
        tree = GameTree.restore(
            nodes=nodes,
            root_id=str(game_row["root_node_id"]),
            current_id=str(game_row["current_node_id"]),
        )
        record = GameRecord(
            id=str(game_row["id"]),
            name=str(game_row["name"]),
            black_player=str(game_row["black_player"]),
            white_player=str(game_row["white_player"]),
            board_size=int(game_row["board_size"]),
            rules=str(game_row["rules"]),
            komi=float(game_row["komi"]),
            mode=str(game_row["mode"]),
            human_color=str(game_row["human_color"]),
            difficulty=str(game_row["difficulty"]),
            status=str(game_row["status"]),
            result=str(game_row["result"]),
            random_seed=int(game_row["random_seed"]),
            created_at=str(game_row["created_at"]),
            updated_at=str(game_row["updated_at"]),
        )
        return record, tree

    def close(self) -> None:
        self.connection.close()

    def _upsert_node(self, game_id: str, node: GameNode) -> None:
        move = node.move
        point = None if move is None else move.point
        self.connection.execute(
            """
            INSERT INTO game_nodes (
                id, game_id, parent_id, move_number, color, x, y, is_pass,
                state_json, comment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                comment = excluded.comment
            """,
            (
                node.id,
                game_id,
                node.parent_id,
                node.state.move_number,
                None if move is None else int(move.color),
                None if point is None else point.x,
                None if point is None else point.y,
                int(move is not None and move.is_pass),
                _encode_state(node.state),
                node.comment,
                node.created_at,
            ),
        )

    def _new_record(
        self,
        tree: GameTree,
        *,
        name: str,
        black_player: str,
        white_player: str,
        rules: str,
        komi: float,
        mode: str,
        human_color: str,
        difficulty: str,
        status: str,
        result: str,
        random_seed: int | None,
    ) -> GameRecord:
        normalized_difficulty = difficulty.strip()
        if not normalized_difficulty:
            raise ValueError("Difficulty must not be empty")
        timestamp = _now()
        return GameRecord(
            id=str(uuid4()),
            name=name,
            black_player=black_player,
            white_player=white_player,
            board_size=tree.root.state.size,
            rules=rules,
            komi=komi,
            mode=mode,
            human_color=human_color,
            difficulty=normalized_difficulty,
            status=status,
            result=result,
            random_seed=random_seed if random_seed is not None else uuid4().int & 0x7FFFFFFF,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _insert_game(self, record: GameRecord, tree: GameTree) -> None:
        self.connection.execute(
            """
            INSERT INTO games (
                id, name, black_player, white_player, board_size, rules, komi,
                mode, human_color, difficulty, status, result, random_seed,
                root_node_id, current_node_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.name,
                record.black_player,
                record.white_player,
                record.board_size,
                record.rules,
                record.komi,
                record.mode,
                record.human_color,
                record.difficulty,
                record.status,
                record.result,
                record.random_seed,
                tree.root_id,
                tree.current_id,
                record.created_at,
                record.updated_at,
            ),
        )


def _encode_state(state: BoardState) -> str:
    payload = {
        "size": state.size,
        "stones": list(state.stones),
        "to_play": int(state.to_play),
        "ko_point": (None if state.ko_point is None else [state.ko_point.x, state.ko_point.y]),
        "black_captures": state.black_captures,
        "white_captures": state.white_captures,
        "move_number": state.move_number,
        "consecutive_passes": state.consecutive_passes,
        "position_history": sorted(state.position_history),
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _decode_state(raw: str) -> BoardState:
    payload = json.loads(raw)
    ko_raw = payload["ko_point"]
    return BoardState(
        size=int(payload["size"]),
        stones=tuple(int(value) for value in payload["stones"]),
        to_play=Color(int(payload["to_play"])),
        ko_point=None if ko_raw is None else Point(int(ko_raw[0]), int(ko_raw[1])),
        black_captures=int(payload["black_captures"]),
        white_captures=int(payload["white_captures"]),
        move_number=int(payload["move_number"]),
        consecutive_passes=int(payload["consecutive_passes"]),
        position_history=frozenset(str(value) for value in payload["position_history"]),
    )

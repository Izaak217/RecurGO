"""v1.2.0.dev1: read saved objective analysis into a portable report snapshot.

This module never starts an engine, changes a game, or writes to the database.
It deliberately keeps search provenance and budget separate from presentation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from recurgo import __version__
from recurgo.domain.board import BoardState, Color
from recurgo.domain.coordinates import Point, gtp_to_point, point_to_gtp
from recurgo.domain.game_tree import GameTree
from recurgo.domain.recommendations import select_recommended_candidates
from recurgo.domain.review import build_move_reviews
from recurgo.storage import GameRecord, GameRepository

_OBJECTIVE_KEY = re.compile(r"(?:full-game-(\d+)|realtime-(\d+)-[01](?:-human-[^/]+)?)\Z")
_SourceKey = tuple[str, str, str, str, int]


@dataclass(frozen=True, slots=True)
class ReportSource:
    identity: str
    engine_version: str
    model_hash: str
    config_hash: str
    visits: int
    completed_positions: int
    available_positions: int
    latest_at: str


@dataclass(frozen=True, slots=True)
class _Snapshot:
    key: _SourceKey
    node_id: str
    payload: dict[str, Any]
    created_at: str
    winrate_only: bool = False

    @property
    def complete(self) -> bool:
        if self.winrate_only:
            return False
        root = _mapping(self.payload.get("rootInfo"))
        if _probability(root.get("winrate")) is None:
            return False
        during = self.payload.get("isDuringSearch")
        if during is True:
            return False
        return during is False or (
            during is None and _integer(root.get("visits")) >= self.key[4]
        )


def list_report_sources(repository: GameRepository, game_id: str) -> list[ReportSource]:
    """List saved source/budget combinations without relying on a live runtime."""
    groups: dict[_SourceKey, list[_Snapshot]] = {}
    for snapshot in _read_snapshots(repository, game_id):
        groups.setdefault(snapshot.key, []).append(snapshot)
    sources = []
    for key, values in groups.items():
        chosen = _choose_snapshots(values)
        sources.append(
            ReportSource(
                identity=key[0],
                engine_version=key[1],
                model_hash=key[2],
                config_hash=key[3],
                visits=key[4],
                completed_positions=sum(item.complete for item in chosen.values()),
                available_positions=len(chosen),
                latest_at=max(item.created_at for item in values),
            )
        )
    return sorted(sources, key=lambda source: (source.latest_at, source.visits), reverse=True)


def build_report_data(
    repository: GameRepository,
    record: GameRecord,
    tree: GameTree,
    source: ReportSource,
    *,
    language: str = "zh",
) -> dict[str, Any]:
    """Freeze one source and budget for every node, including existing variations."""
    key = (
        source.identity,
        source.engine_version,
        source.model_hash,
        source.config_hash,
        source.visits,
    )
    snapshots = _choose_snapshots(
        [item for item in _read_snapshots(repository, record.id) if item.key == key]
    )
    if not snapshots:
        raise ValueError("所选分析来源已无可导出的记录。 / No saved results for this source.")
    nodes: dict[str, dict[str, Any]] = {}
    review_payloads: dict[str, dict[str, object]] = {}
    for node_id, node in tree.nodes.items():
        snapshot = snapshots.get(node_id)
        analysis = None
        if snapshot is not None:
            legal = _legal_candidates(snapshot.payload, node.state)
            root = _mapping(snapshot.payload.get("rootInfo"))
            black_wr = _probability(root.get("winrate"))
            black_score = _number(root.get("scoreLead", root.get("scoreMean")))
            analysis = {
                "status": (
                    "winrateOnly"
                    if snapshot.winrate_only
                    else "complete"
                    if snapshot.complete
                    else "partial"
                ),
                "blackWinrate": None if black_wr is None else black_wr * 100.0,
                "blackScoreLead": black_score,
                "visits": _integer(root.get("visits")),
                "candidates": [
                    _candidate_data(info, node.state, snapshot.payload)
                    for info in select_recommended_candidates(legal, node.state.to_play)
                ]
                if legal
                else [],
            }
            # The review's top-three membership uses the same complete, ordered
            # search list as the desktop review, not the filtered recommendation UI.
            review_payloads[node_id] = {
                "rootInfo": {"winrate": black_wr, "scoreLead": black_score},
                "moveInfos": legal,
            }
        nodes[node_id] = {
            "id": node_id,
            "parentId": node.parent_id,
            "children": list(node.children),
            "moveNumber": node.state.move_number,
            "move": None
            if node.move is None
            else point_to_gtp(node.move.point, node.state.size),
            "color": None if node.move is None else node.move.color.short_name,
            "toPlay": node.state.to_play.short_name,
            "stones": list(node.state.stones),
            "blackCaptures": node.state.black_captures,
            "whiteCaptures": node.state.white_captures,
            "analysis": analysis,
            "review": None,
        }
    for node_id, node in tree.nodes.items():
        if node.parent_id is None or node.move is None:
            continue
        reviews = build_move_reviews(tree, [node.parent_id, node_id], review_payloads)
        if not reviews:
            continue
        review = reviews[0]
        before = nodes[node.parent_id]["analysis"]
        after = nodes[node_id]["analysis"]
        # Finite input scores can still overflow when the review subtracts them.
        # Normalize derived values at this export boundary, without changing the
        # shared review domain or discarding a separately valid win-rate grade.
        winrate_loss = _number(review.winrate_loss)
        complete = bool(
            before
            and after
            and before["status"] == after["status"] == "complete"
            and before["candidates"]
            and winrate_loss is not None
        )
        nodes[node_id]["review"] = {
            "color": review.color.short_name,
            "move": review.move,
            "bestMove": review.best_move if review.best_move != "—" else None,
            "topThree": list(review.top_three),
            "blackWinrateBefore": _number(review.black_winrate_before),
            "blackWinrateAfter": _number(review.black_winrate_after),
            "winrateLoss": winrate_loss,
            "scoreLoss": _number(review.score_loss),
            "matchesBest": review.matches_best,
            "matchesTopThree": review.matches_top_three,
            "grade": review.grade if complete else None,
            "complete": complete,
        }
    return {
        "schemaVersion": 1,
        "appVersion": __version__,
        "generatedAt": datetime.now(UTC).isoformat(),
        "language": "en" if language == "en" else "zh",
        "game": {
            "name": record.name,
            "blackPlayer": record.black_player,
            "whitePlayer": record.white_player,
            "size": record.board_size,
            "rules": record.rules,
            "komi": _number(record.komi),
            "result": record.result,
        },
        "source": {
            "identity": source.identity,
            "engineVersion": source.engine_version,
            "modelHash": source.model_hash,
            "configHash": source.config_hash,
            "maxVisits": source.visits,
            "latestAt": max(item.created_at for item in snapshots.values()),
            "legacy": source.identity.startswith("legacy-"),
        },
        "rootId": tree.root_id,
        "currentId": tree.current_id,
        "defaultLine": [node.id for node in tree.line_through()],
        "nodes": nodes,
    }


def _read_snapshots(repository: GameRepository, game_id: str) -> list[_Snapshot]:
    snapshots: list[_Snapshot] = []
    rows = repository.connection.execute(
        "SELECT node_id, cache_key, engine_version, model_hash, parameters_json, "
        "result_json, created_at FROM analysis_snapshots WHERE game_id = ?",
        (game_id,),
    ).fetchall()
    for row in rows:
        parameters = _json_mapping(str(row["parameters_json"]))
        payload = _json_mapping(str(row["result_json"]))
        if parameters is None or payload is None:
            continue
        key = _snapshot_key(
            str(row["cache_key"]),
            str(row["engine_version"]),
            str(row["model_hash"]),
            parameters,
        )
        if key is None:
            continue
        snapshots.append(_Snapshot(key, str(row["node_id"]), payload, str(row["created_at"])))
    # Unlike legacy unscoped winrate_points, these points have explicit engine,
    # model, configuration and budget provenance. They can safely fill chart gaps.
    rows = repository.connection.execute(
        "SELECT p.node_id, p.analysis_identity, p.max_visits, p.black_winrate, "
        "p.search_visits, p.updated_at, s.engine_version, s.model_hash, s.config_hash "
        "FROM winrate_points_by_source AS p JOIN analysis_sources AS s "
        "ON s.identity = p.analysis_identity WHERE p.game_id = ? AND p.is_complete = 1",
        (game_id,),
    ).fetchall()
    for row in rows:
        percentage = _number(row["black_winrate"])
        visits = _integer(row["max_visits"])
        if percentage is None or not 0.0 <= percentage <= 100.0 or visits == 0:
            continue
        key = (
            str(row["analysis_identity"]),
            str(row["engine_version"]),
            str(row["model_hash"]),
            str(row["config_hash"]),
            visits,
        )
        snapshots.append(
            _Snapshot(
                key,
                str(row["node_id"]),
                {
                    "rootInfo": {
                        "winrate": percentage / 100.0,
                        "visits": _integer(row["search_visits"]),
                    },
                    "moveInfos": [],
                },
                str(row["updated_at"]),
                winrate_only=True,
            )
        )
    return snapshots


def _snapshot_key(
    cache_key: str,
    engine: str,
    model: str,
    parameters: dict[str, Any],
) -> _SourceKey | None:
    identity = ""
    if cache_key.startswith("source/"):
        pieces = cache_key.split("/", 2)
        if len(pieces) != 3 or not pieces[1]:
            return None
        _, identity, cache_key = pieces
    match = _OBJECTIVE_KEY.fullmatch(cache_key)
    if match is None:
        return None
    try:
        visits = int(match.group(1) or match.group(2))
    except ValueError:
        return None
    declared_visits = _integer(parameters.get("maxVisits"))
    if not visits or declared_visits != visits:
        return None
    purpose = parameters.get("purpose")
    if purpose is not None and purpose not in ("realtime", "full_game"):
        return None
    declared_identity = parameters.get("analysisIdentity")
    if identity and declared_identity not in (None, "", identity):
        return None
    config_hash = str(parameters.get("configSha256") or "")
    if not engine or not model:
        return None
    if not identity:
        # Old records have no trustworthy source key. Keep exact parameter sets
        # separate, even if that means fewer candidate results in one report.
        try:
            description = json.dumps(
                [engine, model, parameters],
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except ValueError:
            return None
        identity = "legacy-" + hashlib.sha256(description.encode("utf-8")).hexdigest()
    return identity, engine, model, config_hash, visits


def _choose_snapshots(values: list[_Snapshot]) -> dict[str, _Snapshot]:
    chosen: dict[str, _Snapshot] = {}
    for item in values:
        previous = chosen.get(item.node_id)
        rank = (int(not item.winrate_only), int(item.complete), item.created_at)
        if previous is None or rank > (
            int(not previous.winrate_only),
            int(previous.complete),
            previous.created_at,
        ):
            chosen[item.node_id] = item
    return chosen


def _legal_candidates(payload: dict[str, Any], state: BoardState) -> list[dict[str, Any]]:
    values = payload.get("moveInfos")
    if not isinstance(values, list):
        return []
    legal: list[dict[str, Any]] = []
    for raw in values:
        if not isinstance(raw, dict):
            continue
        order = _number(raw.get("order"))
        move = raw.get("move")
        if (
            order is None
            or not 0 <= order <= state.size * state.size
            or not order.is_integer()
            or not isinstance(move, str)
        ):
            continue
        try:
            point = _point(move, state.size)
            state.play(point)
        except ValueError:
            continue
        legal.append(
            {
                "move": point_to_gtp(point, state.size),
                "order": int(order),
                "winrate": _probability(raw.get("winrate")),
                "scoreLead": _number(raw.get("scoreLead", raw.get("scoreMean"))),
                "visits": _integer(raw.get("visits")),
                "pv": raw.get("pv"),
            }
        )
    legal.sort(key=lambda info: (info["order"], -info["visits"]))
    # Never promote another move to the first recommendation when the engine's
    # actual order=0 candidate is absent or illegal in this exact board state.
    if not legal or legal[0]["order"] != 0:
        return []
    seen: set[str] = set()
    result = []
    for info in legal:
        if info["move"] not in seen:
            seen.add(info["move"])
            result.append(info)
    return result


def _candidate_data(
    info: dict[str, Any],
    state: BoardState,
    payload: dict[str, Any],
) -> dict[str, Any]:
    move = str(info["move"])
    point = _point(move, state.size)
    black_wr = _probability(info.get("winrate"))
    black_score = _number(info.get("scoreLead"))
    side_wr = (
        None
        if black_wr is None
        else (black_wr if state.to_play is Color.BLACK else 1.0 - black_wr) * 100.0
    )
    side_score = (
        None
        if black_score is None
        else (black_score if state.to_play is Color.BLACK else -black_score)
    )
    policy = payload.get("humanPolicy")
    index = state.size * state.size if point is None else point.y * state.size + point.x
    human_probability = (
        _probability(policy[index])
        if isinstance(policy, list) and index < len(policy)
        else None
    )
    frames, truncated = _variation(state, move, info.get("pv"))
    return {
        "move": move,
        "order": info["order"],
        "x": None if point is None else point.x,
        "y": None if point is None else point.y,
        "winrate": side_wr,
        "scoreLead": side_score,
        "visits": _integer(info.get("visits")),
        "humanPolicy": None if human_probability is None else human_probability * 100.0,
        "pv": frames,
        "pvTruncated": truncated,
    }


def _variation(
    state: BoardState,
    move: str,
    raw_pv: object,
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(raw_pv, list) or not raw_pv:
        return [], False
    frames: list[dict[str, Any]] = []
    current = state
    for index, raw_move in enumerate(raw_pv):
        if not isinstance(raw_move, str):
            return frames, True
        try:
            point = _point(raw_move, current.size)
            normalized = point_to_gtp(point, current.size)
            if index == 0 and normalized != move:
                return [], True
            color = current.to_play
            current = current.play(point)
        except ValueError:
            return frames, True
        frames.append(
            {
                "move": normalized,
                "color": color.short_name,
                "stones": list(current.stones),
                "lastMove": None if point is None else {"x": point.x, "y": point.y},
                "moveNumber": current.move_number,
            }
        )
    return frames, False


def _point(move: str, size: int) -> Point | None:
    if not move.strip():
        raise ValueError("An empty analysis move is not an explicit pass")
    return gtp_to_point(move, size)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_mapping(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value, parse_constant=lambda _value: None)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _probability(value: object) -> float | None:
    number = _number(value)
    return number if number is not None and 0.0 <= number <= 1.0 else None


def _integer(value: object) -> int:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else 0

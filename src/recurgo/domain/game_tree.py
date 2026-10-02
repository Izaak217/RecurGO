"""In-memory game tree supporting main-line navigation and arbitrary variations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from .board import BoardState, Color
from .coordinates import Point


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Move:
    color: Color
    point: Point | None

    @property
    def is_pass(self) -> bool:
        return self.point is None


@dataclass(slots=True)
class GameNode:
    id: str
    parent_id: str | None
    move: Move | None
    state: BoardState
    children: list[str] = field(default_factory=list)
    comment: str = ""
    created_at: str = field(default_factory=_now)


class GameTree:
    def __init__(self, initial_state: BoardState | None = None) -> None:
        state = initial_state or BoardState.new()
        root = GameNode(
            id=str(uuid4()),
            parent_id=None,
            move=None,
            state=state,
        )
        self.nodes: dict[str, GameNode] = {root.id: root}
        self.root_id = root.id
        self.current_id = root.id

    @property
    def root(self) -> GameNode:
        return self.nodes[self.root_id]

    @property
    def current(self) -> GameNode:
        return self.nodes[self.current_id]

    def play(self, point: Point | None) -> tuple[GameNode, bool]:
        parent = self.current
        color = parent.state.to_play
        move = Move(color=color, point=point)
        for child_id in parent.children:
            child = self.nodes[child_id]
            if child.move == move:
                self.current_id = child.id
                return child, False

        state = parent.state.play(point)
        node = GameNode(
            id=str(uuid4()),
            parent_id=parent.id,
            move=move,
            state=state,
        )
        self.nodes[node.id] = node
        parent.children.append(node.id)
        self.current_id = node.id
        return node, True

    def undo(self) -> GameNode:
        current = self.current
        if current.parent_id is None:
            return current
        self.current_id = current.parent_id
        return self.current

    def remove_subtree(self, node_id: str) -> set[str]:
        """Permanently remove a variation while retaining its parent and siblings."""
        if node_id == self.root_id:
            raise ValueError("Cannot remove the game root")
        node = self.nodes[node_id]
        if node.parent_id is None:
            raise ValueError("A variation must have a parent")
        parent = self.nodes[node.parent_id]
        removed: set[str] = set()
        pending = [node_id]
        while pending:
            current_id = pending.pop()
            if current_id in removed:
                continue
            removed.add(current_id)
            pending.extend(self.nodes[current_id].children)
        parent.children.remove(node_id)
        if self.current_id in removed:
            self.current_id = parent.id
        for removed_id in removed:
            del self.nodes[removed_id]
        return removed

    def go_to(self, node_id: str) -> GameNode:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        self.current_id = node_id
        return self.current

    def path_to(self, node_id: str | None = None) -> list[GameNode]:
        current = self.nodes[node_id or self.current_id]
        reversed_path = [current]
        while current.parent_id is not None:
            current = self.nodes[current.parent_id]
            reversed_path.append(current)
        return list(reversed(reversed_path))

    def line_through(self, node_id: str | None = None) -> list[GameNode]:
        """Return a stable review line through a node and its first-child continuation."""
        line = self.path_to(node_id)
        current = line[-1]
        visited = {node.id for node in line}
        while current.children:
            child = self.nodes[current.children[0]]
            if child.id in visited:
                raise ValueError("Game tree contains a cycle")
            line.append(child)
            visited.add(child.id)
            current = child
        return line

    @classmethod
    def restore(
        cls,
        *,
        nodes: list[GameNode],
        root_id: str,
        current_id: str,
    ) -> GameTree:
        tree = cls.__new__(cls)
        tree.nodes = {node.id: node for node in nodes}
        if root_id not in tree.nodes or current_id not in tree.nodes:
            raise ValueError("Persisted game points to a missing node")
        tree.root_id = root_id
        tree.current_id = current_id
        for node in tree.nodes.values():
            node.children.clear()
        for node in tree.nodes.values():
            if node.parent_id is not None:
                tree.nodes[node.parent_id].children.append(node.id)
        return tree

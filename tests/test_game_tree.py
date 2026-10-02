from __future__ import annotations

import pytest

from recurgo.domain import GameTree, Point


def test_variations_are_preserved_and_navigable() -> None:
    tree = GameTree()
    first, first_created = tree.play(Point(3, 3))
    second, second_created = tree.play(Point(15, 15))
    assert first_created and second_created

    tree.undo()
    alternative, alternative_created = tree.play(Point(15, 3))
    assert alternative_created
    assert len(first.children) == 2
    assert tree.current is alternative

    tree.undo()
    assert tree.go_to(first.children[0]) is second
    tree.undo()
    assert tree.go_to(first.children[1]) is alternative


def test_replaying_existing_variation_reuses_node() -> None:
    tree = GameTree()
    existing, created = tree.play(Point(3, 3))
    assert created
    tree.undo()
    selected, created = tree.play(Point(3, 3))
    assert not created
    assert selected.id == existing.id


def test_line_through_keeps_selected_variation_when_reviewing_from_earlier_node() -> None:
    tree = GameTree()
    first, _created = tree.play(Point(3, 3))
    main_reply, _created = tree.play(Point(15, 15))
    tree.go_to(first.id)
    variation, _created = tree.play(Point(15, 3))

    assert [node.id for node in tree.line_through(variation.id)] == [
        tree.root_id,
        first.id,
        variation.id,
    ]
    assert [node.id for node in tree.line_through(first.id)] == [
        tree.root_id,
        first.id,
        main_reply.id,
    ]


def test_remove_subtree_prunes_descendants_and_preserves_siblings() -> None:
    tree = GameTree()
    first, _ = tree.play(Point(3, 3))
    second, _ = tree.play(Point(15, 15))
    third, _ = tree.play(Point(3, 15))
    tree.go_to(first.id)
    sibling, _ = tree.play(Point(15, 3))
    tree.go_to(third.id)
    assert tree.remove_subtree(second.id) == {second.id, third.id}
    assert tree.current_id == first.id
    assert first.children == [sibling.id]
    with pytest.raises(ValueError, match="root"):
        tree.remove_subtree(tree.root_id)

from recurgo.ui.formatting import format_rules_and_komi


def test_chinese_komi_uses_mainland_stone_display_without_changing_value() -> None:
    assert format_rules_and_komi("chinese", 7.5) == "中国规则 · 黑贴3¾子"


def test_territory_rules_keep_point_display() -> None:
    assert format_rules_and_komi("japanese", 6.5) == "日本规则 · 黑贴6.5目"

from __future__ import annotations

from pytestqt.qtbot import QtBot

from recurgo.ui.preferences import AnalysisControls, AppPreferences
from recurgo.ui.preferences_dialog import PreferencesDialog


def test_preferences_validate_unknown_ids_and_volume() -> None:
    preferences = AppPreferences.from_mapping(
        {
            "board_theme": "missing",
            "stone_style": "missing",
            "placement_sound": "missing",
            "capture_sound": "missing",
            "volume": 500,
            "muted": True,
        }
    )

    assert preferences.board_theme == "classic"
    assert preferences.stone_style == "classic"
    assert preferences.placement_sound == "wood"
    assert preferences.capture_sound == "wood"
    assert preferences.volume == 100
    assert preferences.muted is True


def test_analysis_controls_only_restore_explicit_boolean_values() -> None:
    assert AnalysisControls.from_mapping(None) == AnalysisControls()
    assert AnalysisControls.from_mapping({
        "realtime_enabled": "false", "ownership_enabled": 1,
    }) == AnalysisControls()
    controls = AnalysisControls(True, True)
    assert AnalysisControls.from_mapping(controls.to_mapping()) == controls


def test_preferences_dialog_only_offers_builtin_stones_and_sounds(qtbot: QtBot) -> None:
    dialog = PreferencesDialog(
        AppPreferences(
            board_theme="dark",
            stone_style="jade",
            placement_sound="crisp",
            capture_sound="soft",
            volume=64,
        )
    )
    qtbot.addWidget(dialog)

    assert dialog.stone_combo.count() == 4
    assert dialog.placement_combo.count() == 3
    assert dialog.capture_combo.count() == 3
    assert dialog.preferences().stone_style == "jade"
    assert dialog.preferences().placement_sound == "crisp"
    assert dialog.preferences().capture_sound == "soft"
    assert dialog.preferences().volume == 64

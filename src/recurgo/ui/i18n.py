"""Small, explicit bilingual text selection for the desktop interface."""

from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from recurgo.i18n import Language, normalize_language, tr

__all__ = ["Language", "normalize_language", "tr", "localize_dialog_buttons"]


def localize_dialog_buttons(buttons: QDialogButtonBox, language: Language) -> None:
    """Use the app language even when the host Qt locale differs."""
    for standard, chinese, english in (
        (QDialogButtonBox.StandardButton.Ok, "确定", "OK"),
        (QDialogButtonBox.StandardButton.Cancel, "取消", "Cancel"),
        (QDialogButtonBox.StandardButton.Save, "保存", "Save"),
        (QDialogButtonBox.StandardButton.Close, "关闭", "Close"),
        (QDialogButtonBox.StandardButton.Yes, "是", "Yes"),
        (QDialogButtonBox.StandardButton.No, "否", "No"),
    ):
        button = buttons.button(standard)
        if button is not None:
            button.setText(tr(language, chinese, english))

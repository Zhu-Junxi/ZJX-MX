from __future__ import annotations

from PySide6.QtCore import Qt


def shortcut_text_from_key_event(event):
    """Return the app's normalized shortcut label for a Qt key event."""
    key = event.key()
    key_text = _key_text(key)
    if not key_text:
        return None

    modifiers = event.modifiers()
    parts = []
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        parts.append("Meta")

    parts.append(key_text)
    return "+".join(parts)


def _key_text(key):
    special_keys = {
        int(Qt.Key.Key_Delete): "Delete",
        int(Qt.Key.Key_F2): "F2",
        int(Qt.Key.Key_F5): "F5",
        int(Qt.Key.Key_Return): "Return",
        int(Qt.Key.Key_Enter): "Enter",
        int(Qt.Key.Key_Plus): "+",
        int(Qt.Key.Key_Equal): "=",
        int(Qt.Key.Key_Minus): "-",
    }

    if key in special_keys:
        return special_keys[key]

    key_a = int(Qt.Key.Key_A)
    key_z = int(Qt.Key.Key_Z)
    if key_a <= key <= key_z:
        return chr(ord("A") + key - key_a)

    return None

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Slot


class CallbackRelay(QObject):
    """Retained QObject slot wrapper for PySide signal callbacks."""

    def __init__(self, callback: Callable, parent=None):
        super().__init__(parent)
        self.callback = callback

    @Slot()
    def run(self):
        self.callback()

    @Slot(bool)
    def run_checked(self, _checked=False):
        self.callback()

    @Slot(object)
    def run_object(self, value=None):
        self.callback(value)


def connect_owned_slot(sender, signal_name: str, callback: Callable, *, checked=False, argument=False):
    """Connect a signal to a retained QObject slot to avoid dynamic wrapper warnings."""
    relay = CallbackRelay(callback, sender)
    refs = getattr(sender, "_zjx_signal_relays", None)
    if refs is None:
        refs = []
        sender._zjx_signal_relays = refs
    refs.append(relay)

    signal = getattr(sender, signal_name)
    if argument:
        signal.connect(relay.run_object)
    else:
        signal.connect(relay.run_checked if checked else relay.run)
    return relay

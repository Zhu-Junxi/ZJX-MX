from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QToolButton, QWidgetAction

from ui.icons import load_icon
from ui.signal_helpers import connect_owned_slot


def _connect_menu_callback(action: QAction, callback: Callable | None):
    """Attach a menu callback while keeping the Python wrapper alive."""
    if not callback:
        return
    action._zjx_callback = callback
    connect_owned_slot(action, "triggered", callback, checked=True)


@dataclass(frozen=True)
class MenuActionSpec:
    """Declarative action used by app context menus."""

    label: str
    icon_name: str | None = None
    callback: Callable | None = None
    enabled: bool = True
    shortcut: str | None = None


@dataclass(frozen=True)
class QuickMenuAction:
    """Compact icon action for the command strip at the top of a menu."""

    label: str
    icon_name: str
    callback: Callable | None = None
    enabled: bool = True
    shortcut: str | None = None


class AppContextMenu(QMenu):
    """Standard app menu with retained Python-owned QActions.

    Retaining action/widget-action references avoids PySide wrapper churn and
    keeps shortcut text, icon sizing, disabled state, and popup styling uniform.
    """

    def __init__(self, parent=None, *, object_name="ContextMenu"):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setToolTipsVisible(True)
        if hasattr(self, "setIconSize"):
            self.setIconSize(QSize(22, 22))
        self._zjx_action_refs = []

    def addAction(self, *args):
        action = super().addAction(*args)
        if isinstance(action, QAction):
            self._zjx_action_refs.append(action)
        return action

    def addMenu(self, *args):
        result = super().addMenu(*args)
        if isinstance(result, QMenu):
            self._zjx_action_refs.append(result)
            self._zjx_action_refs.append(result.menuAction())
        elif isinstance(result, QAction):
            self._zjx_action_refs.append(result)
        return result

    def addSection(self, *args):
        action = super().addSection(*args)
        self._zjx_action_refs.append(action)
        return action

    def addSeparator(self):
        action = super().addSeparator()
        self._zjx_action_refs.append(action)
        return action

    def add_app_action(
        self,
        label,
        icon_name=None,
        callback=None,
        enabled=True,
        shortcut=None,
    ):
        action = QAction(load_icon(icon_name), label, self) if icon_name else QAction(label, self)
        action.setEnabled(bool(enabled))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutVisibleInContextMenu(True)
        _connect_menu_callback(action, callback)
        super().addAction(action)
        self._zjx_action_refs.append(action)
        return action

    def add_quick_actions(self, actions: Iterable[QuickMenuAction], parent=None):
        return add_quick_action_bar(self, actions, parent)

    def add_separator_if_needed(self):
        add_separator_if_needed(self)

    def add_app_menu(self, icon_name, title):
        submenu = AppContextMenu(self, object_name=self.objectName() or "ContextMenu")
        submenu.setTitle(title)
        submenu.setIcon(load_icon(icon_name))
        super().addMenu(submenu)
        self._zjx_action_refs.append(submenu)
        self._zjx_action_refs.append(submenu.menuAction())
        return submenu


def build_menu(parent, actions: Iterable[MenuActionSpec] = (), quick_actions: Iterable[QuickMenuAction] | None = None):
    """Build a standard app context menu from declarative action specs."""
    menu = AppContextMenu(parent)
    if quick_actions:
        menu.add_quick_actions(quick_actions, parent)
        menu.add_separator_if_needed()

    for spec in actions:
        menu.add_app_action(
            spec.label,
            spec.icon_name,
            spec.callback,
            spec.enabled,
            spec.shortcut,
        )
    return menu


def add_menu_action(menu, label, icon_name=None, callback=None, enabled=True, shortcut=None):
    """Compatibility helper for existing menu construction code."""
    if isinstance(menu, AppContextMenu):
        return menu.add_app_action(label, icon_name, callback, enabled, shortcut)

    if hasattr(menu, "setIconSize"):
        menu.setIconSize(QSize(22, 22))
    if not hasattr(menu, "_zjx_action_refs"):
        menu._zjx_action_refs = []
    action = QAction(load_icon(icon_name), label, menu) if icon_name else QAction(label, menu)
    action.setEnabled(bool(enabled))
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
        action.setShortcutVisibleInContextMenu(True)
    _connect_menu_callback(action, callback)
    menu.addAction(action)
    menu._zjx_action_refs.append(action)
    return action


def add_quick_action_bar(menu, actions: Iterable[QuickMenuAction], parent=None):
    """Add the standard compact command strip to the top of a context menu."""
    action_list = list(actions)
    if not action_list:
        return None

    host = QFrame(parent or menu)
    host.setObjectName("ContextQuickBar")
    layout = QHBoxLayout(host)
    layout.setContentsMargins(6, 5, 6, 5)
    layout.setSpacing(4)

    for spec in action_list:
        button = QToolButton(host)
        button.setObjectName("ContextQuickButton")
        button.setIcon(load_icon(spec.icon_name))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(f"{spec.label} ({spec.shortcut})" if spec.shortcut else spec.label)
        button.setAccessibleName(spec.label)
        button.setEnabled(bool(spec.enabled and spec.callback))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRaise(True)

        if spec.callback and spec.enabled:
            def run_checked(_checked=False, callback=spec.callback, owning_menu=menu):
                callback()
                owning_menu.close()

            button.clicked.connect(run_checked)

        layout.addWidget(button)

    widget_action = QWidgetAction(menu)
    widget_action.setDefaultWidget(host)
    menu.addAction(widget_action)
    if not hasattr(menu, "_zjx_action_refs"):
        menu._zjx_action_refs = []
    menu._zjx_action_refs.append(widget_action)
    return widget_action


def add_separator_if_needed(menu):
    """Add one separator only when the previous action is not already one."""
    actions = menu.actions()
    if actions and not actions[-1].isSeparator():
        menu.addSeparator()

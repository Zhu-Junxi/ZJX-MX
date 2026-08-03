from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.widget_manager import WidgetManager


class FakeWindow:
    def __init__(self, hwnd):
        self.hwnd = hwnd

    def winId(self):
        return self.hwnd


class FakeWidgetWindow(FakeWindow):
    def window_handle_int(self):
        return int(self.hwnd)


def make_manager():
    manager = object.__new__(WidgetManager)
    manager.main_window = FakeWindow(100)
    manager.manager_window = FakeWindow(200)
    manager.widget_windows = {
        "note": FakeWidgetWindow(300),
        "assignments": FakeWidgetWindow(301),
    }
    return manager


class WidgetVisibilityTests(unittest.TestCase):
    def test_non_windows_fallback_is_visible(self):
        manager = make_manager()

        with patch("app.widget_manager.sys.platform", "linux"):
            self.assertEqual(manager.foreground_window_kind(), "desktop")
            self.assertTrue(manager.desktop_widgets_should_be_visible())

    def test_desktop_shell_class_is_visible(self):
        manager = make_manager()
        manager.foreground_window_handle = lambda: 10
        manager.foreground_window_class_name = lambda _hwnd: "WorkerW"

        with patch("app.widget_manager.sys.platform", "win32"):
            self.assertEqual(manager.foreground_window_kind(), "desktop")
            self.assertTrue(manager.desktop_widgets_should_be_visible())

    def test_widget_foreground_is_visible(self):
        manager = make_manager()
        manager.foreground_window_handle = lambda: 300
        manager.foreground_window_class_name = lambda _hwnd: "QtWidget"

        with patch("app.widget_manager.sys.platform", "win32"):
            self.assertEqual(manager.foreground_window_kind(), "own_widget")
            self.assertTrue(manager.desktop_widgets_should_be_visible())

    def test_main_app_foreground_is_hidden(self):
        manager = make_manager()
        manager.foreground_window_handle = lambda: 100
        manager.foreground_window_class_name = lambda _hwnd: "QtMain"

        with patch("app.widget_manager.sys.platform", "win32"):
            self.assertEqual(manager.foreground_window_kind(), "own_app")
            self.assertFalse(manager.desktop_widgets_should_be_visible())

    def test_other_app_foreground_is_hidden(self):
        manager = make_manager()
        manager.foreground_window_handle = lambda: 999
        manager.foreground_window_class_name = lambda _hwnd: "Chrome_WidgetWin_1"

        with patch("app.widget_manager.sys.platform", "win32"):
            self.assertEqual(manager.foreground_window_kind(), "other_app")
            self.assertFalse(manager.desktop_widgets_should_be_visible())


if __name__ == "__main__":
    unittest.main()

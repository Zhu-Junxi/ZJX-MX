from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.file_explorer_dragdrop import (
    classify_payloads,
    drop_target_from_item,
    preview_text,
    resolve_payload_destination,
    would_move_folder_into_itself,
)
from ui.browser_widgets import ResourceTreeWidget


class FakeVault:
    def resource_absolute_path(self, resource):
        return Path(resource["absolute_path"]) if resource.get("absolute_path") else None


class FakeOwner:
    def __init__(self, root):
        self.root = Path(root)
        self.vault = FakeVault()

    def current_top_level_files_dir(self):
        return self.root / "files"

    def current_top_level_folders_dir(self):
        return self.root / "folders"

    def current_top_level_notes_dir(self):
        return self.root / "notes"

    def top_level_destination_for_path(self, source_path, resource_type=None):
        if resource_type == "note":
            return self.current_top_level_notes_dir()
        if resource_type == "local_folder" or Path(source_path).is_dir():
            return self.current_top_level_folders_dir()
        return self.current_top_level_files_dir()

    def move_file_explorer_payloads(self, *_args, **_kwargs):
        return True


class FakeItem:
    def __init__(self, data, parent=None):
        self._data = data
        self._parent = parent

    def data(self, _column, role):
        if role == Qt.ItemDataRole.UserRole:
            return self._data
        return None

    def parent(self):
        return self._parent


class FileExplorerDragDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_preview_text_for_single_link_resource(self):
        title, subtitle = preview_text(
            [
                {
                    "type": "resource",
                    "resource": {
                        "type": "external_link",
                        "title": "Reading list",
                        "url": "https://example.test",
                    },
                }
            ],
            action="Move",
        )

        self.assertEqual(title, "Move link")
        self.assertEqual(subtitle, "Reading list")

    def test_classifies_mixed_payloads(self):
        counts, first_name = classify_payloads(
            [
                {"type": "file_system_entry", "path": "notes.txt"},
                {
                    "type": "resource",
                    "resource": {"type": "local_folder", "title": "Week 1"},
                },
            ]
        )

        self.assertTrue(counts["mixed"])
        self.assertEqual(counts["files"], 1)
        self.assertEqual(counts["folders"], 1)
        self.assertEqual(first_name, "notes.txt")

    def test_preview_text_for_multiple_files(self):
        title, subtitle = preview_text(
            [
                {"type": "file_system_entry", "path": "a.txt"},
                {"type": "file_system_entry", "path": "b.txt"},
            ],
            action="Export",
        )

        self.assertEqual(title, "Export items")
        self.assertEqual(subtitle, "2 files")

    def test_folder_drop_target_uses_plain_folder_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Week 1"
            folder.mkdir()
            owner = FakeOwner(tmp)
            item = FakeItem(
                {
                    "type": "resource",
                    "resource": {
                        "id": "res_folder",
                        "type": "local_folder",
                        "absolute_path": str(folder),
                    },
                }
            )

            target = drop_target_from_item(item, owner)

            self.assertEqual(target["kind"], "folder")
            self.assertEqual(Path(target["folder_path"]), folder)

    def test_background_destination_sends_payloads_to_root_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "source.txt"
            file_path.write_text("hello", encoding="utf-8")
            folder_path = root / "Folder"
            folder_path.mkdir()
            note_path = root / "note.md"
            note_path.write_text("note", encoding="utf-8")
            owner = FakeOwner(root)
            background = drop_target_from_item(None, owner)

            self.assertEqual(
                resolve_payload_destination({"type": "file_system_entry", "path": str(file_path)}, background, owner),
                owner.current_top_level_files_dir(),
            )
            self.assertEqual(
                resolve_payload_destination(
                    {"type": "resource", "resource": {"type": "local_folder", "absolute_path": str(folder_path)}},
                    background,
                    owner,
                ),
                owner.current_top_level_folders_dir(),
            )
            self.assertEqual(
                resolve_payload_destination(
                    {"type": "resource", "resource": {"type": "note", "absolute_path": str(note_path)}},
                    background,
                    owner,
                ),
                owner.current_top_level_notes_dir(),
            )
            self.assertIsNone(
                resolve_payload_destination(
                    {"type": "resource", "resource": {"type": "external_link", "url": "https://example.test"}},
                    background,
                    owner,
                )
            )

    def test_folder_into_itself_or_child_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Folder"
            child = source / "Child"
            child.mkdir(parents=True)
            outside = Path(tmp) / "Outside"
            outside.mkdir()

            self.assertTrue(would_move_folder_into_itself(source, source))
            self.assertTrue(would_move_folder_into_itself(source, child))
            self.assertFalse(would_move_folder_into_itself(source, outside))

    def test_pending_internal_drop_stores_plain_data_only(self):
        tree = ResourceTreeWidget(owner=QWidget())
        payload = {
            "type": "resource",
            "resource": {"id": "res_1", "type": "local_file", "title": "Draft"},
        }
        target = {"kind": "folder", "folder_path": "C:/Temp/Folder", "is_background": False}

        self.assertTrue(tree._queue_internal_drop([payload], target))
        request = tree._pending_internal_drop_request

        self.assertIsInstance(request, dict)
        self.assertIsInstance(request["payloads"], list)
        self.assertIsInstance(request["payloads"][0], dict)
        self.assertIsInstance(request["payloads"][0]["resource"], dict)
        self.assertIsInstance(request["drop_target"], dict)
        self.assertFalse(tree._queue_internal_drop([payload], target))
        tree.clear_active_internal_drag()

    def test_external_payload_from_manual_drag_returns_paths_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "draft.pdf"
            file_path.write_text("draft", encoding="utf-8")
            owner = FakeOwner(root)
            tree = ResourceTreeWidget(owner=owner)
            tree._manual_drag_payloads = [
                {
                    "type": "resource",
                    "resource": {
                        "id": "file_1",
                        "type": "local_file",
                        "title": "Draft",
                        "path": "files/draft.pdf",
                        "absolute_path": str(file_path),
                    },
                },
                {
                    "type": "resource",
                    "resource": {
                        "id": "link_1",
                        "type": "external_link",
                        "title": "Reading",
                        "url": "https://example.test/reading",
                    },
                },
            ]

            paths, urls = tree._external_payload_from_manual_payloads()

            self.assertEqual(paths, [file_path.resolve()])
            self.assertEqual(urls, ["https://example.test/reading"])

    def test_reset_manual_drag_clears_external_state(self):
        tree = ResourceTreeWidget(owner=QWidget())
        tree._manual_drag_start_pos = tree.viewport().rect().center()
        tree._manual_drag_payloads = [{"type": "file_system_entry", "path": "draft.txt"}]
        tree._manual_drag_active = True
        tree._manual_drag_external_started = True
        tree._manual_drag_mode = "export"

        tree._reset_manual_drag()

        self.assertIsNone(tree._manual_drag_start_pos)
        self.assertEqual(tree._manual_drag_payloads, [])
        self.assertFalse(tree._manual_drag_active)
        self.assertFalse(tree._manual_drag_external_started)
        self.assertEqual(tree._manual_drag_mode, "move")

    def test_application_deactivation_exports_active_manual_drag(self):
        tree = ResourceTreeWidget(owner=QWidget())
        tree._manual_drag_payloads = [{"type": "file_system_entry", "path": "draft.txt"}]
        tree._manual_drag_active = True

        with patch.object(tree, "_start_external_drag_for_payloads", return_value=True) as start_drag:
            tree._handle_application_state_changed(Qt.ApplicationState.ApplicationInactive)
            self._app.processEvents()

        start_drag.assert_called_once()
        self.assertEqual(start_drag.call_args.args[0], [{"type": "file_system_entry", "path": "draft.txt"}])
        self.assertEqual(tree._manual_drag_payloads, [])
        self.assertFalse(tree._manual_drag_active)


if __name__ == "__main__":
    unittest.main()

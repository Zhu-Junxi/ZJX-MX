from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.command_history import (
    AssignmentCreateAction,
    AssignmentUpdateAction,
    CanvasSyncAction,
    CommandHistory,
    CompositeAction,
    CourseCreateAction,
    CourseUpdateAction,
    FileContentUpdateAction,
    FileCopyAction,
    FileCreateAction,
    FileDeleteAction,
    FileMoveAction,
    FileRenameAction,
    ResourceAddAction,
    ResourceDeleteAction,
    ResourceLibraryMultiContextAction,
    ResourceUpdateAction,
    SnapshotCommand,
    SnapshotRestoreError,
    UndoableAction,
    UserCreateAction,
    UserDeleteAction,
    UserUpdateAction,
)
from core.vault_manager import VaultManager


class CounterAction(UndoableAction):
    action_type = "counter"

    def __init__(self, label, state, delta):
        super().__init__(label, action_type="counter", affected_item="counter")
        self.state = state
        self.delta = delta

    def do(self):
        self.state["value"] += self.delta

    def undo(self):
        self.state["value"] -= self.delta


class FakeVault:
    def __init__(self):
        self.resources = {}

    def load_resources(self, user_id, course_id, assignment_id=None):
        return list(self.resources.get((user_id, course_id, assignment_id), []))

    def save_resources(self, user_id, course_id, assignment_id, resources):
        self.resources[(user_id, course_id, assignment_id)] = list(resources)

    def add_resource(self, user_id, course_id, assignment_id, resource):
        resource = dict(resource)
        resource["user_id"] = user_id
        resource["course_id"] = course_id
        resource["assignment_id"] = assignment_id
        resources = self.load_resources(user_id, course_id, assignment_id)
        resources.append(resource)
        self.save_resources(user_id, course_id, assignment_id, resources)
        return resource

    def delete_resource(self, resource, delete_physical=False):
        key = (resource["user_id"], resource["course_id"], resource.get("assignment_id"))
        resources = [
            item for item in self.load_resources(*key)
            if item.get("id") != resource.get("id")
        ]
        self.save_resources(*key, resources)


class CommandHistoryTests(unittest.TestCase):
    def test_manager_perform_undo_redo_and_clear_redo_stack(self):
        state = {"value": 0}
        history = CommandHistory()

        first = history.perform(CounterAction("Added one", state, 1))
        self.assertEqual(state["value"], 1)
        self.assertTrue(history.can_undo())
        self.assertFalse(history.can_redo())

        undone = history.undo()
        self.assertIs(undone, first)
        self.assertEqual(state["value"], 0)
        self.assertTrue(history.can_redo())

        history.perform(CounterAction("Added five", state, 5))
        self.assertEqual(state["value"], 5)
        self.assertFalse(history.can_redo())

    def test_history_entries_include_label_status_and_timestamp(self):
        state = {"value": 0}
        history = CommandHistory()

        history.perform(CounterAction("Created folder: Week 3 Notes", state, 1))
        history.undo()
        entries = history.recent_descriptions(limit=2)

        self.assertIn("Created folder: Week 3 Notes", entries[0])
        self.assertIn("[undone]", entries[0])
        self.assertRegex(entries[0], r"\d{2}:\d{2}:\d{2} - ")

    def test_file_rename_action_undo_redo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "old_name.txt"
            destination = Path(temp_dir) / "new_name.txt"
            source.write_text("notes", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileRenameAction(source, destination))
            self.assertEqual(action.action_type, "rename_file")
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "notes")

            history.undo()
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

            history.redo()
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())

    def test_file_rename_conflict_does_not_enter_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "old_name.txt"
            destination = Path(temp_dir) / "new_name.txt"
            source.write_text("old", encoding="utf-8")
            destination.write_text("new", encoding="utf-8")
            history = CommandHistory()

            with self.assertRaises(SnapshotRestoreError):
                history.perform(FileRenameAction(source, destination))

            self.assertTrue(source.exists())
            self.assertTrue(destination.exists())
            self.assertFalse(history.can_undo())

    def test_file_move_action_undo_redo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_parent = Path(temp_dir) / "source"
            destination_parent = Path(temp_dir) / "destination"
            source_parent.mkdir()
            destination_parent.mkdir()
            source = source_parent / "lab.pdf"
            destination = destination_parent / "lab.pdf"
            source.write_text("lab", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileMoveAction(source, destination))
            self.assertEqual(action.action_type, "move_file")
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "lab")

            history.undo()
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

            history.redo()
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())

    def test_file_create_action_undo_redo_preserves_modified_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            history = CommandHistory()

            action = history.perform(FileCreateAction(path, content="initial"))
            self.assertEqual(action.action_type, "create_file")
            self.assertEqual(path.read_text(encoding="utf-8"), "initial")

            path.write_text("edited before undo", encoding="utf-8")
            history.undo()
            self.assertFalse(path.exists())
            self.assertTrue(action.backup_path.exists())

            history.redo()
            self.assertEqual(path.read_text(encoding="utf-8"), "edited before undo")
            self.assertFalse(action.backup_path.exists())

    def test_file_create_folder_action_undo_redo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Week 3 Notes"
            history = CommandHistory()

            action = history.perform(FileCreateAction(folder, is_directory=True))
            self.assertTrue(folder.is_dir())

            (folder / "summary.txt").write_text("summary", encoding="utf-8")
            history.undo()
            self.assertFalse(folder.exists())

            history.redo()
            self.assertEqual((folder / "summary.txt").read_text(encoding="utf-8"), "summary")

    def test_file_content_update_action_undo_redo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Canvas Page.url"
            path.write_text("URL=https://old.example\n", encoding="utf-8")
            history = CommandHistory()

            history.perform(
                FileContentUpdateAction(
                    path,
                    path.read_bytes(),
                    "URL=https://new.example\n",
                )
            )
            self.assertEqual(path.read_text(encoding="utf-8"), "URL=https://new.example\n")

            history.undo()
            self.assertEqual(path.read_text(encoding="utf-8"), "URL=https://old.example\n")

            history.redo()
            self.assertEqual(path.read_text(encoding="utf-8"), "URL=https://new.example\n")

    def test_file_copy_action_undo_redo_file_preserves_imported_edits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.pdf"
            destination = Path(temp_dir) / "vault" / "source.pdf"
            source.write_text("original source", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileCopyAction(source, destination))
            self.assertEqual(destination.read_text(encoding="utf-8"), "original source")

            destination.write_text("edited imported copy", encoding="utf-8")
            source.write_text("changed external source", encoding="utf-8")
            history.undo()
            self.assertFalse(destination.exists())
            self.assertTrue(action.backup_path.exists())

            history.redo()
            self.assertEqual(destination.read_text(encoding="utf-8"), "edited imported copy")

    def test_file_copy_action_undo_redo_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source_folder"
            destination = Path(temp_dir) / "vault" / "source_folder"
            source.mkdir()
            (source / "notes.txt").write_text("notes", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileCopyAction(source, destination))
            self.assertEqual((destination / "notes.txt").read_text(encoding="utf-8"), "notes")

            (destination / "added.txt").write_text("added after import", encoding="utf-8")
            history.undo()
            self.assertFalse(destination.exists())
            self.assertTrue((action.backup_path / "added.txt").exists())

            history.redo()
            self.assertEqual((destination / "added.txt").read_text(encoding="utf-8"), "added after import")

    def test_file_delete_action_undo_redo_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.txt"
            path.write_text("draft", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileDeleteAction(path))
            self.assertEqual(action.action_type, "delete_file")
            self.assertFalse(path.exists())
            self.assertTrue(action.backup_path.exists())

            history.undo()
            self.assertEqual(path.read_text(encoding="utf-8"), "draft")
            self.assertFalse(action.backup_path.exists())

            history.redo()
            self.assertFalse(path.exists())
            self.assertTrue(action.backup_path.exists())

    def test_file_delete_action_undo_redo_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "week_4"
            nested_file = folder / "notes.txt"
            folder.mkdir()
            nested_file.write_text("lecture notes", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileDeleteAction(folder))
            self.assertFalse(folder.exists())
            self.assertTrue((action.backup_path / "notes.txt").exists())

            history.undo()
            self.assertEqual(nested_file.read_text(encoding="utf-8"), "lecture notes")

            history.redo()
            self.assertFalse(folder.exists())
            self.assertTrue((action.backup_path / "notes.txt").exists())

    def test_file_delete_undo_conflict_keeps_backup_and_history_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.txt"
            path.write_text("original", encoding="utf-8")
            history = CommandHistory()

            action = history.perform(FileDeleteAction(path))
            path.write_text("replacement", encoding="utf-8")

            with self.assertRaises(SnapshotRestoreError):
                history.undo()

            self.assertEqual(path.read_text(encoding="utf-8"), "replacement")
            self.assertTrue(action.backup_path.exists())
            self.assertTrue(history.can_undo())
            self.assertFalse(history.can_redo())

    def test_resource_add_action_undo_redo_preserves_resource_id(self):
        vault = FakeVault()
        history = CommandHistory()
        resource = {"type": "local_file", "title": "Lab.pdf", "path": "files/Lab.pdf", "tags": []}

        action = history.perform(ResourceAddAction(vault, "user", "course", None, resource))
        resource_id = action.resource["id"]
        self.assertEqual(vault.load_resources("user", "course", None)[0]["id"], resource_id)

        history.undo()
        self.assertEqual(vault.load_resources("user", "course", None), [])

        history.redo()
        self.assertEqual(vault.load_resources("user", "course", None)[0]["id"], resource_id)

    def test_resource_delete_action_undo_redo_preserves_metadata(self):
        vault = FakeVault()
        resource = {
            "id": "res_existing",
            "user_id": "user",
            "course_id": "course",
            "assignment_id": "assignment",
            "type": "external_link",
            "title": "Canvas Page",
            "url": "https://example.test",
            "tags": ["canvas"],
        }
        vault.save_resources("user", "course", "assignment", [dict(resource)])
        history = CommandHistory()

        history.perform(ResourceDeleteAction(vault, resource))
        self.assertEqual(vault.load_resources("user", "course", "assignment"), [])

        history.undo()
        restored = vault.load_resources("user", "course", "assignment")[0]
        self.assertEqual(restored["id"], "res_existing")
        self.assertEqual(restored["url"], "https://example.test")
        self.assertEqual(restored["tags"], ["canvas"])

        history.redo()
        self.assertEqual(vault.load_resources("user", "course", "assignment"), [])

    def test_resource_update_action_undo_redo_preserves_exact_metadata(self):
        vault = FakeVault()
        before = {
            "id": "res_existing",
            "user_id": "user",
            "course_id": "course",
            "assignment_id": None,
            "type": "external_link",
            "title": "Canvas Page",
            "url": "https://old.example",
            "tags": ["canvas"],
            "updated_at": "2026-01-01T10:00:00",
        }
        after = dict(before)
        after["title"] = "Updated Canvas Page"
        after["url"] = "https://new.example"
        after["updated_at"] = "2026-01-02T10:00:00"
        vault.save_resources("user", "course", None, [dict(before)])
        history = CommandHistory()

        history.perform(ResourceUpdateAction(vault, before, after))
        self.assertEqual(vault.load_resources("user", "course", None)[0], after)

        history.undo()
        self.assertEqual(vault.load_resources("user", "course", None)[0], before)

        history.redo()
        self.assertEqual(vault.load_resources("user", "course", None)[0], after)

    def test_course_create_action_undo_redo_restores_same_course_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry")
            history = CommandHistory()

            action = history.perform(CourseCreateAction(vault, user["id"], "COMP1010", "Programming Fundamentals"))
            course_id = action.course["id"]
            self.assertTrue(vault.course_json_path(user["id"], course_id).exists())

            history.undo()
            self.assertFalse(vault.course_dir(user["id"], course_id).exists())

            history.redo()
            restored = vault.get_course(user["id"], course_id)
            self.assertIsNotNone(restored)
            self.assertEqual(restored["id"], course_id)
            self.assertTrue(vault.resources_json_path(user["id"], course_id, None).exists())

    def test_course_update_action_archives_and_restores_course(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry")
            course = vault.add_course(user["id"], "COMP1010", "Programming Fundamentals")
            history = CommandHistory()

            history.perform(
                CourseUpdateAction(
                    vault,
                    user["id"],
                    course,
                    {
                        "archived": True,
                        "archived_at": "2026-08-01T12:00:00",
                        "archived_source": "manual",
                    },
                )
            )
            archived = vault.get_course(user["id"], course["id"])
            self.assertTrue(archived["archived"])
            self.assertEqual(archived["archived_source"], "manual")

            history.undo()
            restored = vault.get_course(user["id"], course["id"])
            self.assertFalse(restored.get("archived", False))

            history.redo()
            self.assertTrue(vault.get_course(user["id"], course["id"])["archived"])

    def test_assignment_create_action_undo_redo_restores_same_assignment_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry")
            course = vault.add_course(user["id"], "COMP1010", "Programming Fundamentals")
            history = CommandHistory()

            action = history.perform(
                AssignmentCreateAction(
                    vault,
                    user["id"],
                    course["id"],
                    "Lab Report",
                    "2026-06-20",
                    "Not started",
                )
            )
            assignment_id = action.assignment["id"]
            self.assertTrue(vault.assignment_json_path(user["id"], course["id"], assignment_id).exists())

            history.undo()
            self.assertFalse(vault.assignment_dir(user["id"], course["id"], assignment_id).exists())

            history.redo()
            restored = vault.get_assignment(user["id"], course["id"], assignment_id)
            self.assertIsNotNone(restored)
            self.assertEqual(restored["id"], assignment_id)
            self.assertTrue(vault.resources_json_path(user["id"], course["id"], assignment_id).exists())

    def test_user_create_action_undo_redo_restores_same_user_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            history = CommandHistory()

            action = history.perform(UserCreateAction(vault, "Harry", university="USYD"))
            user_id = action.user["id"]
            self.assertTrue(vault.user_profile_path(user_id).exists())

            history.undo()
            self.assertIsNone(vault.get_user(user_id))
            self.assertFalse(vault.user_dir(user_id).exists())

            history.redo()
            restored = vault.get_user(user_id)
            self.assertIsNotNone(restored)
            self.assertEqual(restored["id"], user_id)
            self.assertTrue(vault.user_profile_path(user_id).exists())

    def test_user_update_action_undo_redo_preserves_exact_user_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry", university="USYD")
            history = CommandHistory()

            history.perform(UserUpdateAction(vault, user, {"name": "Harriet", "university": "UNSW"}))
            updated = vault.get_user(user["id"])
            self.assertEqual(updated["name"], "Harriet")
            self.assertEqual(updated["university"], "UNSW")

            history.undo()
            self.assertEqual(vault.get_user(user["id"]), user)

            history.redo()
            self.assertEqual(vault.get_user(user["id"])["name"], "Harriet")

    def test_user_delete_action_undo_redo_restores_user_entry_and_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry", university="USYD")
            (vault.user_dir(user["id"]) / "extra.txt").write_text("kept", encoding="utf-8")
            history = CommandHistory()

            history.perform(UserDeleteAction(vault, user))
            self.assertIsNone(vault.get_user(user["id"]))
            self.assertFalse(vault.user_dir(user["id"]).exists())

            history.undo()
            self.assertEqual(vault.get_user(user["id"])["id"], user["id"])
            self.assertEqual((vault.user_dir(user["id"]) / "extra.txt").read_text(encoding="utf-8"), "kept")

            history.redo()
            self.assertIsNone(vault.get_user(user["id"]))
            self.assertFalse(vault.user_dir(user["id"]).exists())

    def test_assignment_update_action_undo_redo_preserves_exact_assignment_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir))
            user = vault.add_user("Harry")
            course = vault.add_course(user["id"], "COMP1010", "Programming Fundamentals")
            assignment = vault.add_assignment(user["id"], course["id"], "Lab Report", "2026-06-20")
            history = CommandHistory()

            fields = {
                "title": "Updated Lab Report",
                "due_date": "",
                "canvas_due_at": "",
                "due_date_overridden_by_user": True,
                "archive_prompted_due_text": "",
                "archive_prompted_at": "",
            }
            history.perform(AssignmentUpdateAction(vault, user["id"], course["id"], assignment, fields))
            self.assertEqual(vault.get_assignment(user["id"], course["id"], assignment["id"])["title"], "Updated Lab Report")

            history.undo()
            self.assertEqual(vault.get_assignment(user["id"], course["id"], assignment["id"]), assignment)

            history.redo()
            restored = vault.get_assignment(user["id"], course["id"], assignment["id"])
            self.assertEqual(restored["title"], "Updated Lab Report")
            self.assertTrue(restored["due_date_overridden_by_user"])

    def test_composite_action_rolls_back_completed_children_on_do_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            created = Path(temp_dir) / "created.txt"
            conflict = Path(temp_dir) / "conflict.txt"
            conflict.write_text("existing", encoding="utf-8")
            history = CommandHistory()
            action = CompositeAction(
                "Create two files",
                [
                    FileCreateAction(created, content="created"),
                    FileCreateAction(conflict, content="new"),
                ],
            )

            with self.assertRaises(SnapshotRestoreError):
                history.perform(action)

            self.assertFalse(created.exists())
            self.assertFalse(history.can_undo())

    def test_failed_undo_keeps_live_files_and_history_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "context"
            target.mkdir()
            file_path = target / "report.xlsx"
            file_path.write_text("changed", encoding="utf-8")

            command = SnapshotCommand("Edit report", target)
            command.capture_before()
            file_path.write_text("current", encoding="utf-8")
            command.capture_after()

            history = CommandHistory()
            history.push_done(command)
            original_replace = os.replace

            def locked_file_replace(source, destination):
                if Path(destination) == file_path:
                    raise PermissionError("locked")
                return original_replace(source, destination)

            with patch("os.replace", locked_file_replace):
                with self.assertRaises(SnapshotRestoreError):
                    history.undo()

            self.assertEqual(file_path.read_text(encoding="utf-8"), "current")
            self.assertTrue(history.can_undo())
            self.assertFalse(history.can_redo())

    def test_canvas_sync_action_undo_redo_uses_canvas_history_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_dir = Path(temp_dir) / "user"
            user_dir.mkdir()
            profile = user_dir / "profile.json"
            profile.write_text("before", encoding="utf-8")
            command = CanvasSyncAction(user_dir, "Harry")
            command.capture_before()
            profile.write_text("after", encoding="utf-8")
            command.capture_after()
            history = CommandHistory()

            history.push_done(command)
            self.assertEqual(history.undo_stack[-1].action_type, "canvas_sync")

            history.undo()
            self.assertEqual(profile.read_text(encoding="utf-8"), "before")

            history.redo()
            self.assertEqual(profile.read_text(encoding="utf-8"), "after")

    def test_resource_library_multi_context_action_undo_redo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "course_a"
            second = Path(temp_dir) / "course_b"
            first.mkdir()
            second.mkdir()
            (first / "resources.json").write_text("before-a", encoding="utf-8")
            (second / "resources.json").write_text("before-b", encoding="utf-8")
            command = ResourceLibraryMultiContextAction("Move library resources", [first, second])
            command.capture_before()
            (first / "resources.json").write_text("after-a", encoding="utf-8")
            (second / "resources.json").write_text("after-b", encoding="utf-8")
            command.capture_after()
            history = CommandHistory()

            history.push_done(command)
            self.assertEqual(history.undo_stack[-1].action_type, "resource_library_multi_context")

            history.undo()
            self.assertEqual((first / "resources.json").read_text(encoding="utf-8"), "before-a")
            self.assertEqual((second / "resources.json").read_text(encoding="utf-8"), "before-b")

            history.redo()
            self.assertEqual((first / "resources.json").read_text(encoding="utf-8"), "after-a")
            self.assertEqual((second / "resources.json").read_text(encoding="utf-8"), "after-b")

    def test_redo_delete_restores_missing_target_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "assignment"
            target.mkdir()
            (target / "assignment.json").write_text("{}", encoding="utf-8")

            command = SnapshotCommand("Delete assignment", target)
            command.capture_before()
            shutil.rmtree(target)
            command.capture_after()

            history = CommandHistory()
            history.push_done(command)

            history.undo()
            self.assertTrue(target.exists())
            self.assertTrue((target / "assignment.json").exists())

            history.redo()
            self.assertFalse(target.exists())

    def test_same_size_content_change_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "context"
            target.mkdir()
            file_path = target / "note.txt"
            file_path.write_text("abc", encoding="utf-8")

            command = SnapshotCommand("Edit note", target)
            command.capture_before()
            file_path.write_text("xyz", encoding="utf-8")
            command.capture_after()

            self.assertTrue(command.has_changes())


if __name__ == "__main__":
    unittest.main()

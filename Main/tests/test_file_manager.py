from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.file_manager import FileManager, InvalidFileOperationError, ResourceScope
from core.url_shortcuts import read_url_shortcut, write_url_shortcut
from core.vault_manager import VaultManager


class FileManagerTests(unittest.TestCase):
    def make_backend(self, root: Path):
        vault = VaultManager(root / "vault")
        user = vault.add_user("Harry", "USYD")
        course = vault.add_course(user["id"], "INFO1110", "Programming")
        scope = ResourceScope(user["id"], course["id"])
        return vault, FileManager(vault), scope

    def test_create_folder_and_list_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, manager, scope = self.make_backend(Path(tmp))

            result = manager.create_folder(scope, "Week 1 Notes")
            children = manager.list_children(scope)

            self.assertTrue(result.ok)
            self.assertEqual(result.resource["type"], "local_folder")
            self.assertTrue((vault.context_dir(**scope.as_kwargs()) / result.resource["path"]).is_dir())
            self.assertEqual([item.id for item in children], [result.resource["id"]])

    def test_import_file_uses_unique_name_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, manager, scope = self.make_backend(root)
            source = root / "report.txt"
            source.write_text("draft", encoding="utf-8")
            (vault.context_files_dir(**scope.as_kwargs()) / "report.txt").write_text("existing", encoding="utf-8")

            result = manager.import_file(source, scope)

            self.assertTrue(result.ok)
            self.assertEqual(result.resource["title"], "report_2.txt")
            self.assertEqual(result.new_path.read_text(encoding="utf-8"), "draft")

    def test_import_url_file_creates_link_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, manager, scope = self.make_backend(root)
            source = root / "Reading.url"
            write_url_shortcut(
                source,
                "example.test/reading",
                title="Reading",
                resource_type="external_link",
                tags=["weekly"],
            )

            result = manager.import_file(source, scope)
            imported = vault.resource_absolute_path(result.resource)

            self.assertEqual(result.resource["url"], "https://example.test/reading")
            self.assertEqual(result.resource["tags"], ["weekly"])
            self.assertEqual(read_url_shortcut(imported)["title"], "Reading")

    def test_import_folder_copy_move_rename_delete_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, manager, scope = self.make_backend(root)
            source = root / "source_folder"
            source.mkdir()
            (source / "notes.txt").write_text("hello", encoding="utf-8")

            imported = manager.import_folder(source, scope)
            created_folder = manager.create_folder(scope, "Archive")
            moved = manager.move_resource(imported.resource["id"], manager.resolve_path(created_folder.resource["id"], scope), scope)
            self.assertTrue(moved.new_path.exists())
            renamed = manager.rename_resource(imported.resource["id"], "renamed_folder", scope)
            copied = manager.copy_resource(imported.resource["id"], scope=scope)
            deleted = manager.delete_resource(imported.resource["id"], scope=scope)

            self.assertEqual(renamed.resource["title"], "renamed_folder")
            self.assertTrue(vault.resource_absolute_path(copied.resource).exists())
            self.assertFalse(deleted.old_path.exists())
            self.assertIsNone(manager.metadata.get(imported.resource["id"], scope))

    def test_update_metadata_and_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manager, scope = self.make_backend(root)
            source = root / "brief.pdf"
            source.write_text("pdf", encoding="utf-8")
            imported = manager.import_file(source, scope)

            updated = manager.update_metadata(imported.resource["id"], {"tags": ["exam"], "title": "Exam Brief"}, scope)
            results = manager.search_resources("exam", {"type": "local_file"})

            self.assertEqual(updated.resource["tags"], ["exam"])
            self.assertEqual(results[0].id, imported.resource["id"])
            self.assertEqual(results[0].name, "Exam Brief")

    def test_metadata_only_link_copy_and_move_preserve_root_container_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, manager, scope = self.make_backend(Path(tmp))
            resource = vault.add_resource(
                scope.user_id,
                scope.course_id,
                scope.assignment_id,
                {
                    "type": "external_link",
                    "title": "Reading",
                    "url": "https://example.test/reading",
                    "container_path": "folders/week_1",
                    "tags": [],
                },
            )

            moved = manager.move_resource(resource["id"], None, scope)
            copied = manager.copy_resource(resource["id"], None, scope)

            self.assertNotIn("container_path", moved.resource)
            self.assertNotIn("container_path", copied.resource)

    def test_missing_file_metadata_is_reconciled_on_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, manager, scope = self.make_backend(root)
            source = root / "draft.txt"
            source.write_text("draft", encoding="utf-8")
            imported = manager.import_file(source, scope)
            vault.resource_absolute_path(imported.resource).unlink()

            resources = manager.list_resources(scope, sync=True)

            self.assertEqual(resources, [])
            self.assertEqual(vault.load_resources(**scope.as_kwargs()), [])

    def test_rejects_destination_outside_context_without_creating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manager, scope = self.make_backend(root)
            source = root / "draft.txt"
            source.write_text("draft", encoding="utf-8")
            outside = root / "outside" / "nested"

            with self.assertRaises(InvalidFileOperationError):
                manager.import_file(source, scope, destination_parent=outside)

            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()

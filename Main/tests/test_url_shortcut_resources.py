from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.resource_actions import ResourceActionsMixin
from core.url_shortcuts import read_url_shortcut, write_url_shortcut
from core.vault_manager import VaultManager


class ResourceImporter(ResourceActionsMixin):
    def __init__(self, vault, user_id, course_id, assignment_id=None):
        self.vault = vault
        self.current_user_id = user_id
        self.current_course_id = course_id
        self.current_assignment_id = assignment_id


class UrlShortcutResourceTests(unittest.TestCase):
    def make_vault_context(self, root):
        vault = VaultManager(root)
        user = vault.add_user("Harry")
        course = vault.add_course(user["id"], "TEST1000", "Testing")
        return vault, user["id"], course["id"]

    def test_reads_generated_url_shortcut_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Reading.url"
            path.write_text(
                "[InternetShortcut]\n"
                "URL=https://example.test/reading\n"
                "\n"
                "[ZJX LMS Resource]\n"
                "Title: Week 1 Reading\n"
                "Type: external_link\n"
                "Tags: weekly, reading\n",
                encoding="utf-8",
            )

            shortcut = read_url_shortcut(path)

            self.assertEqual(shortcut["url"], "https://example.test/reading")
            self.assertEqual(shortcut["title"], "Week 1 Reading")
            self.assertEqual(shortcut["type"], "external_link")
            self.assertEqual(shortcut["tags"], ["weekly", "reading"])

    def test_vault_sync_discovers_url_files_as_link_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, user_id, course_id = self.make_vault_context(tmp)
            shortcut_path = vault.context_files_dir(user_id, course_id) / "Canvas Page.url"
            write_url_shortcut(
                shortcut_path,
                "https://canvas.example.test/courses/1",
                title="Canvas Page",
                resource_type="canvas",
            )

            resources = vault.sync_context_resource_metadata(user_id, course_id)

            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]["type"], "canvas")
            self.assertEqual(resources[0]["title"], "Canvas Page")
            self.assertEqual(resources[0]["url"], "https://canvas.example.test/courses/1")
            self.assertEqual(resources[0]["path"], str(Path("files") / "Canvas Page.url"))

    def test_vault_sync_materializes_metadata_only_links_as_url_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, user_id, course_id = self.make_vault_context(tmp)
            vault.add_resource(
                user_id,
                course_id,
                None,
                {
                    "type": "external_link",
                    "title": "Reading",
                    "url": "https://example.test/reading",
                    "tags": ["weekly"],
                },
            )

            resources = vault.sync_context_resource_metadata(user_id, course_id)
            resource = resources[0]
            shortcut_path = vault.resource_absolute_path(resource)

            self.assertEqual(resource["type"], "external_link")
            self.assertEqual(resource["url"], "https://example.test/reading")
            self.assertTrue(shortcut_path.exists())
            self.assertEqual(read_url_shortcut(shortcut_path)["title"], "Reading")

    def test_file_import_converts_valid_url_file_to_link_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault, user_id, course_id = self.make_vault_context(tmp)
            source = Path(tmp) / "Shared Doc.url"
            write_url_shortcut(
                source,
                "https://docs.google.com/document/example",
                title="Shared Doc",
                resource_type="google_drive",
                tags=["google", "docs"],
            )
            importer = ResourceImporter(vault, user_id, course_id)

            resource = importer.create_file_resource_from_source(source)
            imported_path = vault.resource_absolute_path(resource)

            self.assertEqual(resource["type"], "google_drive")
            self.assertEqual(resource["title"], "Shared Doc")
            self.assertEqual(resource["url"], "https://docs.google.com/document/example")
            self.assertTrue(imported_path.exists())
            self.assertEqual(read_url_shortcut(imported_path)["url"], resource["url"])


if __name__ == "__main__":
    unittest.main()

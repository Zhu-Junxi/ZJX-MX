from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vault_manager import VaultManager


class VaultDeleteResourceTests(unittest.TestCase):
    def create_file_resource(self, root):
        vault = VaultManager(root / "vault")
        user = vault.add_user("Harry", "USYD")
        course = vault.add_course(user["id"], "INFO1110", "Programming")
        context = vault.context_dir(user["id"], course["id"])
        file_path = vault.context_files_dir(user["id"], course["id"]) / "draft.txt"
        file_path.write_text("draft", encoding="utf-8")
        resource = vault.add_resource(
            user["id"],
            course["id"],
            None,
            {
                "type": "local_file",
                "title": "draft.txt",
                "path": str(file_path.relative_to(context)),
                "tags": [],
            },
        )
        return vault, resource, file_path

    def test_failed_physical_delete_keeps_resource_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault, resource, file_path = self.create_file_resource(Path(temp_dir))

            with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    vault.delete_resource(resource, delete_physical=True)

            resources = vault.load_resources(resource["user_id"], resource["course_id"], None)
            self.assertTrue(file_path.exists())
            self.assertEqual([item["id"] for item in resources], [resource["id"]])

    def test_successful_physical_delete_removes_resource_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault, resource, file_path = self.create_file_resource(Path(temp_dir))

            vault.delete_resource(resource, delete_physical=True)

            resources = vault.load_resources(resource["user_id"], resource["course_id"], None)
            self.assertFalse(file_path.exists())
            self.assertEqual(resources, [])


if __name__ == "__main__":
    unittest.main()

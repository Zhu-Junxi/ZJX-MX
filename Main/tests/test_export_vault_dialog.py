from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vault_manager import VaultManager
from ui.dialogs import ExportVaultDialog


class ExportVaultDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_export_options_reflect_selected_general_and_assignment_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = VaultManager(root / "vault")
            user = vault.add_user("Harry", "USYD")
            course = vault.add_course(user["id"], "INFO1110", "Selected Course")
            first_assignment = vault.add_assignment(user["id"], course["id"], "Essay 1")
            second_assignment = vault.add_assignment(user["id"], course["id"], "Essay 2")

            general_context = vault.context_dir(user["id"], course["id"])
            general_path = vault.context_files_dir(user["id"], course["id"]) / "general.txt"
            general_path.write_text("general", encoding="utf-8")
            vault.add_resource(
                user["id"],
                course["id"],
                None,
                {
                    "type": "local_file",
                    "title": "general.txt",
                    "path": str(general_path.relative_to(general_context)),
                    "tags": [],
                },
            )

            for assignment, filename in ((first_assignment, "essay1.txt"), (second_assignment, "essay2.txt")):
                assignment_context = vault.context_dir(user["id"], course["id"], assignment["id"])
                assignment_path = vault.context_files_dir(user["id"], course["id"], assignment["id"]) / filename
                assignment_path.write_text(filename, encoding="utf-8")
                vault.add_resource(
                    user["id"],
                    course["id"],
                    assignment["id"],
                    {
                        "type": "local_file",
                        "title": filename,
                        "path": str(assignment_path.relative_to(assignment_context)),
                        "tags": [],
                    },
                )

            dialog = ExportVaultDialog(vault=vault)
            self.addCleanup(dialog.close)

            user_item = dialog.tree.topLevelItem(0)
            course_item = self.find_child_by_type(user_item, "course")
            general_item = self.find_child_by_type(course_item, "general")
            assignment_items = self.find_children_by_type(course_item, "assignment")

            general_item.setCheckState(0, Qt.CheckState.Unchecked)
            assignment_items[1].setCheckState(0, Qt.CheckState.Unchecked)
            QApplication.processEvents()

            options = dialog.export_options()

            self.assertEqual(options.selected_user_ids, {user["id"]})
            self.assertEqual(options.selected_course_ids_by_user, {user["id"]: {course["id"]}})
            self.assertEqual(options.selected_general_course_ids_by_user, {})
            self.assertEqual(
                options.selected_assignment_ids_by_course,
                {user["id"]: {course["id"]: {first_assignment["id"]}}},
            )

    def find_child_by_type(self, item, node_type):
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == node_type:
                return child
        raise AssertionError(f"Could not find child item of type {node_type!r}")

    def find_children_by_type(self, item, node_type):
        matches = []
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == node_type:
                matches.append(child)
        return matches


if __name__ == "__main__":
    unittest.main()

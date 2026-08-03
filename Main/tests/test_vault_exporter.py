from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vault_manager import VaultManager
from services.vault_exporter import ExportOptions, VaultExporter


class VaultExporterTests(unittest.TestCase):
    def test_exports_human_readable_zip_with_files_notes_links_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = VaultManager(root / "vault")
            user = vault.add_user("Harry", "USYD")
            course, _ = vault.add_or_update_canvas_course(
                user["id"],
                {
                    "id": 123,
                    "course_code": "PMGT1863",
                    "name": "Project Communications",
                },
            )
            assignment, _ = vault.add_or_update_canvas_assignment(
                user["id"],
                course["id"],
                {
                    "id": 456,
                    "name": "Final Report",
                    "html_url": "https://canvas.example.test/assignments/456",
                },
            )

            general_context = vault.context_dir(user["id"], course["id"])
            file_path = vault.context_files_dir(user["id"], course["id"]) / "brief.txt"
            file_path.write_text("hello export", encoding="utf-8")
            vault.add_resource(
                user["id"],
                course["id"],
                None,
                {
                    "type": "local_file",
                    "title": "Brief Notes.txt",
                    "path": str(file_path.relative_to(general_context)),
                    "tags": [],
                },
            )

            folder_path = vault.context_folders_dir(user["id"], course["id"]) / "Week 1"
            folder_path.mkdir(parents=True, exist_ok=True)
            (folder_path / "slides.pdf").write_text("slides", encoding="utf-8")
            vault.add_resource(
                user["id"],
                course["id"],
                None,
                {
                    "type": "local_folder",
                    "title": "Week 1",
                    "path": str(folder_path.relative_to(general_context)),
                    "tags": [],
                },
            )

            vault.add_resource(
                user["id"],
                course["id"],
                None,
                {
                    "type": "google_drive",
                    "title": "Shared Doc",
                    "url": "https://docs.google.com/document/example",
                    "container_path": str(folder_path.relative_to(general_context)),
                    "tags": ["google"],
                },
            )

            assignment_context = vault.context_dir(user["id"], course["id"], assignment["id"])
            note_path = vault.context_notes_dir(user["id"], course["id"], assignment["id"]) / "final.md"
            note_path.write_text("# Final", encoding="utf-8")
            vault.add_resource(
                user["id"],
                course["id"],
                assignment["id"],
                {
                    "type": "note",
                    "title": "Final Notes",
                    "path": str(note_path.relative_to(assignment_context)),
                    "tags": [],
                },
            )

            vault.add_resource(
                user["id"],
                course["id"],
                assignment["id"],
                {
                    "type": "local_file",
                    "title": "Missing File.pdf",
                    "path": "files/missing.pdf",
                    "tags": [],
                },
            )

            export_dir = root / "exports"
            export_dir.mkdir()
            result = VaultExporter(vault).export_to_zip(
                export_dir,
                export_date=datetime(2026, 5, 19, 12, 0, 0),
            )

            self.assertEqual(result.file_count, 2)
            self.assertEqual(result.folder_count, 1)
            self.assertEqual(result.link_count, 1)
            self.assertEqual(result.missing_count, 1)
            self.assertEqual(result.zip_path.name, "ZJX-LMS [EXPORTED] (May-19-2026).zip")

            with zipfile.ZipFile(result.zip_path) as archive:
                names = set(archive.namelist())

            expected_paths = {
                "ZJX-LMS [EXPORTED] (May-19-2026)/Harry/PMGT1863 - Project Communications/General Course Resources/Brief Notes.txt",
                "ZJX-LMS [EXPORTED] (May-19-2026)/Harry/PMGT1863 - Project Communications/General Course Resources/Week 1/slides.pdf",
                "ZJX-LMS [EXPORTED] (May-19-2026)/Harry/PMGT1863 - Project Communications/General Course Resources/Week 1/Shared Doc.url",
                "ZJX-LMS [EXPORTED] (May-19-2026)/Harry/PMGT1863 - Project Communications/Assignments/Final Report/Final Notes.md",
                "ZJX-LMS [EXPORTED] (May-19-2026)/ZJX-LMS Export Manifest.txt",
            }
            self.assertTrue(expected_paths.issubset(names))

    def test_filtered_export_only_includes_selected_user_courses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = VaultManager(root / "vault")
            harry = vault.add_user("Harry", "USYD")
            nancy = vault.add_user("Nancy", "USYD")

            selected_course = vault.add_course(harry["id"], "INFO1110", "Selected Course")
            skipped_course = vault.add_course(harry["id"], "DATA1001", "Skipped Course")
            other_user_course = vault.add_course(nancy["id"], "MATH1001", "Other User Course")

            for user, course, content in (
                (harry, selected_course, "selected"),
                (harry, skipped_course, "skipped"),
                (nancy, other_user_course, "other"),
            ):
                context = vault.context_dir(user["id"], course["id"])
                path = vault.context_files_dir(user["id"], course["id"]) / f"{content}.txt"
                path.write_text(content, encoding="utf-8")
                vault.add_resource(
                    user["id"],
                    course["id"],
                    None,
                    {
                        "type": "local_file",
                        "title": f"{content}.txt",
                        "path": str(path.relative_to(context)),
                        "tags": [],
                    },
                )

            export_dir = root / "exports"
            export_dir.mkdir()
            progress_updates = []
            result = VaultExporter(vault).export_to_zip(
                ExportOptions(
                    destination_dir=export_dir,
                    selected_user_ids={harry["id"]},
                    selected_course_ids_by_user={harry["id"]: {selected_course["id"]}},
                    export_date=datetime(2026, 5, 20, 12, 0, 0),
                ),
                progress_callback=lambda message, value: progress_updates.append((message, value)),
            )

            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.resource_count, 1)
            self.assertTrue(progress_updates)
            self.assertEqual(progress_updates[-1][1], 100)

            with zipfile.ZipFile(result.zip_path) as archive:
                joined_names = "\n".join(archive.namelist())

            self.assertIn("Harry/INFO1110 - Selected Course/General Course Resources/selected.txt", joined_names)
            self.assertNotIn("DATA1001 - Skipped Course", joined_names)
            self.assertNotIn("Nancy", joined_names)

    def test_fine_grained_export_can_include_general_resources_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = VaultManager(root / "vault")
            user = vault.add_user("Harry", "USYD")
            course = vault.add_course(user["id"], "INFO1110", "Selected Course")
            assignment = vault.add_assignment(user["id"], course["id"], "Essay 1")

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

            assignment_context = vault.context_dir(user["id"], course["id"], assignment["id"])
            assignment_path = vault.context_files_dir(user["id"], course["id"], assignment["id"]) / "essay.txt"
            assignment_path.write_text("essay", encoding="utf-8")
            vault.add_resource(
                user["id"],
                course["id"],
                assignment["id"],
                {
                    "type": "local_file",
                    "title": "essay.txt",
                    "path": str(assignment_path.relative_to(assignment_context)),
                    "tags": [],
                },
            )

            export_dir = root / "exports"
            export_dir.mkdir()
            result = VaultExporter(vault).export_to_zip(
                ExportOptions(
                    destination_dir=export_dir,
                    selected_user_ids={user["id"]},
                    selected_course_ids_by_user={user["id"]: {course["id"]}},
                    selected_general_course_ids_by_user={user["id"]: {course["id"]}},
                    selected_assignment_ids_by_course={},
                    export_date=datetime(2026, 5, 21, 12, 0, 0),
                )
            )

            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.resource_count, 1)

            with zipfile.ZipFile(result.zip_path) as archive:
                joined_names = "\n".join(archive.namelist())

            self.assertIn("Harry/INFO1110 - Selected Course/General Course Resources/general.txt", joined_names)
            self.assertNotIn("Assignments/Essay 1", joined_names)

    def test_fine_grained_export_can_limit_assignments_within_selected_course(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = VaultManager(root / "vault")
            user = vault.add_user("Harry", "USYD")
            course = vault.add_course(user["id"], "INFO1110", "Selected Course")
            first_assignment = vault.add_assignment(user["id"], course["id"], "Essay 1")
            second_assignment = vault.add_assignment(user["id"], course["id"], "Essay 2")

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

            export_dir = root / "exports"
            export_dir.mkdir()
            result = VaultExporter(vault).export_to_zip(
                ExportOptions(
                    destination_dir=export_dir,
                    selected_user_ids={user["id"]},
                    selected_course_ids_by_user={user["id"]: {course["id"]}},
                    selected_general_course_ids_by_user={},
                    selected_assignment_ids_by_course={
                        user["id"]: {course["id"]: {first_assignment["id"]}}
                    },
                    export_date=datetime(2026, 5, 22, 12, 0, 0),
                )
            )

            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.resource_count, 1)

            with zipfile.ZipFile(result.zip_path) as archive:
                joined_names = "\n".join(archive.namelist())

            self.assertIn("Assignments/Essay 1/essay1.txt", joined_names)
            self.assertNotIn("General Course Resources", joined_names)
            self.assertNotIn("Assignments/Essay 2", joined_names)


if __name__ == "__main__":
    unittest.main()

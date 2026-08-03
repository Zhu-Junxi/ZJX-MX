from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


LINK_RESOURCE_TYPES = {"external_link", "youtube", "google_drive", "canvas"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


@dataclass
class ExportResult:
    zip_path: Path
    resource_count: int = 0
    file_count: int = 0
    folder_count: int = 0
    link_count: int = 0
    missing_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExportOptions:
    destination_dir: Path
    selected_user_ids: set[str] | None = None
    selected_course_ids_by_user: dict[str, set[str]] | None = None
    selected_general_course_ids_by_user: dict[str, set[str]] | None = None
    selected_assignment_ids_by_course: dict[str, dict[str, set[str]]] | None = None
    export_date: datetime | None = None


class VaultExporter:
    """Create a portable, human-readable zip archive from a ZJX LMS vault."""

    def __init__(self, vault):
        self.vault = vault
        self.result = ExportResult(zip_path=Path())

    def export_to_zip(
        self,
        destination_dir: Path | ExportOptions,
        export_date: datetime | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> ExportResult:
        if isinstance(destination_dir, ExportOptions):
            options = destination_dir
        else:
            options = ExportOptions(destination_dir=Path(destination_dir), export_date=export_date)

        destination_dir = Path(options.destination_dir)
        if not destination_dir.exists() or not destination_dir.is_dir():
            raise ValueError("Export destination must be an existing folder.")

        export_date = options.export_date or export_date or datetime.now()
        archive_name = f"ZJX-LMS [EXPORTED] ({export_date.strftime('%B-%d-%Y')}).zip"
        zip_path = self._unique_destination_path(destination_dir / archive_name)
        self.result = ExportResult(zip_path=zip_path)
        self._progress_callback = progress_callback
        self._selected_user_ids = (
            {str(item) for item in options.selected_user_ids}
            if options.selected_user_ids is not None
            else None
        )
        self._selected_course_ids_by_user = (
            {
                str(user_id): {str(course_id) for course_id in course_ids}
                for user_id, course_ids in options.selected_course_ids_by_user.items()
            }
            if options.selected_course_ids_by_user is not None
            else None
        )
        self._selected_general_course_ids_by_user = (
            {
                str(user_id): {str(course_id) for course_id in course_ids}
                for user_id, course_ids in options.selected_general_course_ids_by_user.items()
            }
            if options.selected_general_course_ids_by_user is not None
            else None
        )
        self._selected_assignment_ids_by_course = (
            {
                str(user_id): {
                    str(course_id): {str(assignment_id) for assignment_id in assignment_ids}
                    for course_id, assignment_ids in course_map.items()
                }
                for user_id, course_map in options.selected_assignment_ids_by_course.items()
            }
            if options.selected_assignment_ids_by_course is not None
            else None
        )
        self._export_work_total = max(1, self._count_selected_contexts())
        self._export_work_done = 0
        self._emit_progress("Preparing vault export...\n\nReading selected vault sections.", 0)

        with tempfile.TemporaryDirectory(prefix="zjx_lms_export_") as temp_root:
            staging_root = Path(temp_root) / zip_path.stem
            staging_root.mkdir(parents=True, exist_ok=True)
            self._export_vault_tree(staging_root)
            self._emit_progress("Writing export manifest...\n\nRecording copied files, links, and warnings.", 94)
            self._write_manifest(staging_root, export_date)
            self._emit_progress("Creating zip archive...\n\nCompressing the readable export folder.", 97)
            self._zip_staging_tree(staging_root, zip_path)

        self._emit_progress("Export complete.\n\nYour portable archive is ready.", 100)
        return self.result

    def _export_vault_tree(self, staging_root: Path):
        users = self._selected_users()
        self.result.resource_count = self._count_selected_resources(users)

        for user in users:
            user_dir = self._unique_child_path(
                staging_root,
                self._display_name(user.get("name"), fallback=user.get("id") or "User"),
                is_dir=True,
            )
            user_dir.mkdir(parents=True, exist_ok=True)

            courses = self._selected_courses(user.get("id"))
            for course in courses:
                course_label = self._course_display_name(course)
                include_general = self._course_general_selected(user.get("id"), course.get("id"))
                assignments = self._selected_assignments(user.get("id"), course.get("id"))
                if not include_general and not assignments:
                    continue
                course_dir = self._unique_child_path(user_dir, self._course_display_name(course), is_dir=True)
                course_dir.mkdir(parents=True, exist_ok=True)

                if include_general:
                    self._emit_progress(
                        f"Exporting selected vault content...\n\n{course_label} / General Course Resources",
                        self._progress_value(),
                    )
                    self._export_context(
                        destination=course_dir / "General Course Resources",
                        user_id=user.get("id"),
                        course_id=course.get("id"),
                        assignment_id=None,
                    )
                    self._export_work_done += 1

                assignments_dir = course_dir / "Assignments"
                for assignment in assignments:
                    assignment_label = self._display_name(
                        assignment.get("title"), fallback=assignment.get("id") or "Assignment"
                    )
                    self._emit_progress(
                        f"Exporting selected vault content...\n\n{course_label} / {assignment_label}",
                        self._progress_value(),
                    )
                    assignment_dir = self._unique_child_path(
                        assignments_dir,
                        assignment_label,
                        is_dir=True,
                    )
                    self._export_context(
                        destination=assignment_dir,
                        user_id=user.get("id"),
                        course_id=course.get("id"),
                        assignment_id=assignment.get("id"),
                    )
                    self._export_work_done += 1

    def _export_context(self, destination: Path, user_id: str, course_id: str, assignment_id: str | None):
        destination.mkdir(parents=True, exist_ok=True)
        resources = list(self.vault.load_resources(user_id, course_id, assignment_id))
        folder_resource_paths = self._folder_resource_paths(resources)

        for resource in sorted(resources, key=self._resource_sort_key):
            resource_type = resource.get("type")

            if resource_type in LINK_RESOURCE_TYPES:
                self._export_link_resource(destination, resource)
                continue

            if resource_type not in {"local_file", "local_folder", "note"}:
                self.result.warnings.append(
                    f"Skipped unsupported resource type '{resource_type}' for {resource.get('title', 'Untitled')}."
                )
                continue

            source_path = self.vault.resource_absolute_path(resource)
            if not source_path or not source_path.exists():
                self.result.missing_count += 1
                self.result.warnings.append(
                    f"Missing local resource: {resource.get('title', 'Untitled')} ({resource.get('path') or 'no path'})."
                )
                continue

            if self._is_nested_inside_folder_resource(resource, source_path, folder_resource_paths):
                continue

            self._copy_local_resource(destination, resource, source_path)

    def _copy_local_resource(self, context_destination: Path, resource: dict, source_path: Path):
        relative_destination = self._resource_relative_export_path(resource, source_path)
        export_path = self._unique_nested_path(context_destination, relative_destination, is_dir=source_path.is_dir())

        if source_path.is_dir():
            shutil.copytree(source_path, export_path)
            self.result.folder_count += 1
            return

        export_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, export_path)
        self.result.file_count += 1

    def _export_link_resource(self, context_destination: Path, resource: dict):
        container = self._safe_relative_parts(resource.get("container_path"))
        if not container and resource.get("path"):
            parent_parts = list(Path(resource.get("path", "")).parent.parts)
            if parent_parts and parent_parts[0] in {"files", "folders", "notes"}:
                parent_parts = parent_parts[1:]
            container = self._safe_relative_parts(str(Path(*parent_parts)) if parent_parts else None)
        target_dir = context_destination.joinpath(*container) if container else context_destination
        target_dir.mkdir(parents=True, exist_ok=True)

        title = self._display_name(resource.get("title"), fallback=resource.get("id") or "Link")
        suffix = ".url" if resource.get("url", "").lower().startswith(("http://", "https://")) else ".txt"
        target_path = self._unique_child_path(target_dir, f"{title}{suffix}", is_dir=False)

        if suffix == ".url":
            body = f"[InternetShortcut]\nURL={resource.get('url', '')}\n"
        else:
            body = f"URL: {resource.get('url', '')}\n"

        details = [
            "",
            "[ZJX LMS Resource]",
            f"Title: {resource.get('title', 'Untitled')}",
            f"Type: {resource.get('type', 'link')}",
            f"Tags: {', '.join(resource.get('tags', [])) if resource.get('tags') else ''}",
            f"Created: {resource.get('created_at', '')}",
            f"Updated: {resource.get('updated_at', '')}",
        ]
        target_path.write_text(body + "\n".join(details) + "\n", encoding="utf-8")
        self.result.link_count += 1

    def _write_manifest(self, staging_root: Path, export_date: datetime):
        lines = [
            "ZJX LMS Export Manifest",
            "",
            f"Exported at: {export_date.isoformat(timespec='seconds')}",
            f"Source vault: {self.vault.root_path}",
            f"Resources in metadata: {self.result.resource_count}",
            f"Files copied: {self.result.file_count}",
            f"Folders copied: {self.result.folder_count}",
            f"Links exported: {self.result.link_count}",
            f"Missing resources: {self.result.missing_count}",
            "",
            "Notes:",
            "- This archive is a portable human-readable export, not a restore bundle.",
            "- The source vault was not modified.",
        ]

        lines.extend(self._selection_summary_lines())

        if self.result.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning}" for warning in self.result.warnings)

        manifest_path = staging_root / "ZJX-LMS Export Manifest.txt"
        manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _zip_staging_tree(self, staging_root: Path, zip_path: Path):
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging_root.rglob("*")):
                archive.write(path, path.relative_to(staging_root.parent))

    def _selected_users(self) -> list[dict]:
        users = sorted(self.vault.get_users(), key=lambda item: item.get("name", "").lower())
        if self._selected_user_ids is None:
            return users
        return [user for user in users if str(user.get("id")) in self._selected_user_ids]

    def _selected_courses(self, user_id: str) -> list[dict]:
        courses = sorted(
            self.vault.get_courses(user_id),
            key=lambda item: (item.get("code", "").lower(), item.get("name", "").lower()),
        )
        if self._selected_course_ids_by_user is None:
            selected_courses = courses
        else:
            selected_ids = self._selected_course_ids_by_user.get(str(user_id), set())
            selected_courses = [course for course in courses if str(course.get("id")) in selected_ids]
        if not self._has_fine_grained_selection():
            return selected_courses
        return [course for course in selected_courses if self._course_has_selected_contexts(user_id, course.get("id"))]

    def _count_selected_contexts(self) -> int:
        count = 0
        for user in self._selected_users():
            for course in self._selected_courses(user.get("id")):
                if self._course_general_selected(user.get("id"), course.get("id")):
                    count += 1
                count += len(self._selected_assignments(user.get("id"), course.get("id")))
        return count

    def _count_selected_resources(self, users: list[dict]) -> int:
        count = 0
        for user in users:
            for course in self._selected_courses(user.get("id")):
                if self._course_general_selected(user.get("id"), course.get("id")):
                    count += len(self.vault.load_resources(user.get("id"), course.get("id"), assignment_id=None))
                for assignment in self._selected_assignments(user.get("id"), course.get("id")):
                    count += len(self.vault.load_resources(user.get("id"), course.get("id"), assignment.get("id")))
        return count

    def _progress_value(self) -> int:
        return min(93, 5 + int(self._export_work_done / max(1, self._export_work_total) * 88))

    def _emit_progress(self, message: str, value: int):
        callback = getattr(self, "_progress_callback", None)
        if callback:
            callback(message, value)

    def _folder_resource_paths(self, resources: list[dict]) -> list[Path]:
        paths = []
        for resource in resources:
            if resource.get("type") != "local_folder":
                continue
            path = self.vault.resource_absolute_path(resource)
            if path and path.exists() and path.is_dir():
                paths.append(path.resolve())
        return paths

    def _is_nested_inside_folder_resource(self, resource: dict, source_path: Path, folder_paths: list[Path]) -> bool:
        if resource.get("type") == "local_folder":
            return False
        try:
            resolved_source = source_path.resolve()
        except FileNotFoundError:
            return False

        for folder_path in folder_paths:
            if resolved_source == folder_path:
                continue
            try:
                resolved_source.relative_to(folder_path)
                return True
            except ValueError:
                continue
        return False

    def _resource_relative_export_path(self, resource: dict, source_path: Path) -> Path:
        relative_path = Path(resource.get("path") or source_path.name)
        parts = list(relative_path.parts)
        if parts and parts[0].lower() in {"files", "folders", "notes"}:
            parts = parts[1:]

        if not parts:
            parts = [resource.get("title") or source_path.name]

        safe_parts = [self._safe_name(part, fallback="Untitled") for part in parts]

        title = resource.get("title")
        if title and safe_parts:
            leaf = Path(safe_parts[-1])
            suffix = leaf.suffix if source_path.is_file() else ""
            title_name = self._safe_name(title, fallback=leaf.stem or "Untitled")
            if suffix and not Path(title_name).suffix:
                title_name = f"{title_name}{suffix}"
            safe_parts[-1] = title_name

        return Path(*safe_parts)

    def _safe_relative_parts(self, relative_path: str | None) -> list[str]:
        if not relative_path:
            return []
        parts = Path(relative_path).parts
        if parts and parts[0].lower() in {"files", "folders", "notes"}:
            parts = parts[1:]
        return [self._safe_name(part, fallback="Folder") for part in parts]

    def _course_display_name(self, course: dict) -> str:
        code = self._display_name(course.get("code"), fallback=course.get("id") or "Course")
        name = self._display_name(course.get("name"), fallback="")
        if name and name.lower() != code.lower():
            return f"{code} - {name}"
        return code

    def _display_name(self, value, fallback: str) -> str:
        return self._safe_name(str(value or "").strip(), fallback=fallback)

    def _safe_name(self, value: str, fallback: str = "Untitled") -> str:
        cleaned = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in str(value or ""))
        cleaned = " ".join(cleaned.split()).strip(" .")
        cleaned = cleaned or fallback
        if cleaned.upper() in WINDOWS_RESERVED_NAMES:
            cleaned = f"{cleaned}_"
        return cleaned[:140].rstrip(" .") or fallback

    def _unique_destination_path(self, path: Path) -> Path:
        candidate = path
        counter = 2
        while candidate.exists():
            candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
            counter += 1
        return candidate

    def _unique_child_path(self, parent: Path, name: str, is_dir: bool) -> Path:
        safe_name = self._safe_name(name, fallback="Untitled")
        base = parent / safe_name
        if is_dir:
            stem = safe_name
            suffix = ""
        else:
            parsed = Path(safe_name)
            stem = parsed.stem
            suffix = parsed.suffix

        candidate = base
        counter = 2
        while candidate.exists():
            candidate = parent / f"{stem} ({counter}){suffix}"
            counter += 1
        return candidate

    def _unique_nested_path(self, parent: Path, relative_path: Path, is_dir: bool) -> Path:
        parts = list(relative_path.parts)
        if not parts:
            return self._unique_child_path(parent, "Untitled", is_dir=is_dir)

        current = parent
        for part in parts[:-1]:
            current = current / self._safe_name(part, fallback="Folder")
        current.mkdir(parents=True, exist_ok=True)
        return self._unique_child_path(current, parts[-1], is_dir=is_dir)

    def _resource_sort_key(self, resource: dict):
        order = {"local_folder": 0, "local_file": 1, "note": 2}
        return (order.get(resource.get("type"), 3), resource.get("title", "").lower())

    def _has_fine_grained_selection(self) -> bool:
        return self._selected_general_course_ids_by_user is not None or self._selected_assignment_ids_by_course is not None

    def _course_general_selected(self, user_id: str, course_id: str) -> bool:
        if self._selected_general_course_ids_by_user is None:
            return True
        return str(course_id) in self._selected_general_course_ids_by_user.get(str(user_id), set())

    def _selected_assignments(self, user_id: str, course_id: str) -> list[dict]:
        assignments = sorted(
            self.vault.get_assignments(user_id, course_id),
            key=lambda item: item.get("title", "").lower(),
        )
        if self._selected_assignment_ids_by_course is None:
            return assignments
        selected_ids = self._selected_assignment_ids_by_course.get(str(user_id), {}).get(str(course_id), set())
        return [assignment for assignment in assignments if str(assignment.get("id")) in selected_ids]

    def _course_has_selected_contexts(self, user_id: str, course_id: str) -> bool:
        return self._course_general_selected(user_id, course_id) or bool(self._selected_assignments(user_id, course_id))

    def _selection_summary_lines(self) -> list[str]:
        users = self._selected_users()
        selected_courses = []
        general_count = 0
        assignment_count = 0

        for user in users:
            user_id = user.get("id")
            for course in self._selected_courses(user_id):
                course_id = course.get("id")
                include_general = self._course_general_selected(user_id, course_id)
                assignments = self._selected_assignments(user_id, course_id)
                selected_courses.append((user, course, include_general, assignments))
                general_count += int(include_general)
                assignment_count += len(assignments)

        lines = [
            "",
            "Selection Summary:",
            f"- Users selected: {len(users)}",
            f"- Courses selected: {len(selected_courses)}",
            f"- General course sections selected: {general_count}",
            f"- Assignments selected: {assignment_count}",
        ]

        if not selected_courses:
            return lines

        lines.append("")
        lines.append("Selected Scope:")
        for user, course, include_general, assignments in selected_courses:
            contexts = []
            if include_general:
                contexts.append("General Course Resources")
            contexts.extend(
                self._display_name(assignment.get("title"), fallback=assignment.get("id") or "Assignment")
                for assignment in assignments
            )
            user_name = self._display_name(user.get("name"), fallback=user.get("id") or "User")
            course_name = self._course_display_name(course)
            lines.append(f"- {user_name} / {course_name}: {', '.join(contexts)}")
        return lines

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from core.detail_text import make_wrap_friendly_text
from core.models import resource_type_display
from ui.icons import icon_for_resource_type, load_icon


class ResourceTreeMixin:
    """Main file explorer tree population and notes/resources sections."""

    def show_files_section(self):
        self.resource_tree.clear()

        if hasattr(self, "browser_context_label"):
            self.browser_context_label.setText(
                make_wrap_friendly_text(self.current_context_label())
            )

        if not self.current_user_id or not self.current_course_id:
            self.show_preview_details_page(
                "No Course Selected",
                "",
                "No file selected.",
                "Status: Select a user and course before managing files.",
            )
            return

        resources = self.current_context_resources()

        if self.resource_view_mode == "type":
            self.populate_resources_by_type(resources)
        else:
            self.populate_resources_naturally(resources)

        if not resources:
            empty = QTreeWidgetItem(["No resources yet."])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": "empty"})
            self.resource_tree.addTopLevelItem(empty)

        self.restore_resource_tree_state(self.pending_resource_tree_state)
        self.show_preview_details_page(
            "Files & Resources",
            "",
            "No file selected.",
            "Status: No resource selected.",
        )

    def populate_resources_naturally(self, resources):
        if not resources:
            return

        root_node = self.resource_tree.invisibleRootItem()

        resource_path_map = self.build_resource_path_map(resources)
        metadata_container_map = self.build_metadata_container_map(resources)
        folder_resources = [
            resource for resource in resources
            if resource.get("type") == "local_folder" and resource.get("path")
        ]

        for resource in sorted(resources, key=self.resource_natural_sort_key):
            if resource.get("container_path"):
                continue

            if self.resource_is_inside_another_folder_resource(resource, folder_resources):
                continue

            self.add_resource_tree_item(
                root_node,
                resource,
                include_folder_contents=True,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

    def populate_resources_by_type(self, resources):
        grouped = {}
        resource_path_map = self.build_resource_path_map(resources)
        metadata_container_map = self.build_metadata_container_map(resources)

        for resource in resources:
            resource_type = resource.get("type", "unknown")
            grouped.setdefault(resource_type, []).append(resource)

        for resource_type in ["local_folder", "local_file", "note", "external_link", "youtube", "google_drive", "canvas"]:
            items = grouped.get(resource_type, [])
            if not items:
                continue

            group_node = QTreeWidgetItem([resource_type_display(resource_type)])
            group_node.setIcon(0, icon_for_resource_type(resource_type))
            group_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "resource_type": resource_type})
            self.resource_tree.addTopLevelItem(group_node)

            for resource in sorted(items, key=lambda item: item.get("title", "").lower()):
                self.add_resource_tree_item(
                    group_node,
                    resource,
                    include_folder_contents=True,
                    resource_path_map=resource_path_map,
                    metadata_container_map=metadata_container_map,
                )

    def build_resource_path_map(self, resources):
        path_map = {}

        for resource in resources:
            if not resource.get("path"):
                continue

            path = self.vault.resource_absolute_path(resource)

            if path:
                try:
                    path_map[str(path.resolve())] = resource
                except FileNotFoundError:
                    path_map[str(path)] = resource

        return path_map

    def build_metadata_container_map(self, resources):
        """Map metadata-only resources to the physical folder they visually live in."""
        container_map = {}

        for resource in resources:
            if resource.get("path"):
                continue

            container_path = resource.get("container_path")

            if not container_path:
                continue

            container_map.setdefault(container_path, []).append(resource)

        return container_map

    def resource_is_inside_another_folder_resource(self, resource, folder_resources):
        if not resource.get("path"):
            return False

        resource_path = self.vault.resource_absolute_path(resource)

        if not resource_path:
            return False

        try:
            resource_resolved = resource_path.resolve()
        except FileNotFoundError:
            resource_resolved = resource_path

        for folder_resource in folder_resources:
            if folder_resource.get("id") == resource.get("id"):
                continue

            folder_path = self.vault.resource_absolute_path(folder_resource)

            if not folder_path:
                continue

            try:
                folder_resolved = folder_path.resolve()
                resource_resolved.relative_to(folder_resolved)
                return True
            except (ValueError, FileNotFoundError):
                continue

        return False

    def resource_natural_sort_key(self, resource):
        resource_type = resource.get("type", "")
        title = resource.get("title", "").lower()

        order = {
            "local_folder": 0,
            "local_file": 1,
            "note": 2,
            "external_link": 3,
            "youtube": 4,
            "google_drive": 5,
            "canvas": 6,
        }
        return (order.get(resource_type, 99), title)

    def add_resource_tree_item(self, parent_node, resource, include_folder_contents=False, resource_path_map=None, metadata_container_map=None):
        resource_type = resource.get("type", "unknown")
        title = resource.get("title", "Untitled")
        child = QTreeWidgetItem([title])
        child.setIcon(0, icon_for_resource_type(resource_type))
        child.setData(0, Qt.ItemDataRole.UserRole, {"type": "resource", "resource": resource})
        flags = child.flags() | Qt.ItemFlag.ItemIsDragEnabled
        if resource_type == "local_folder":
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        child.setFlags(flags)
        parent_node.addChild(child)

        if include_folder_contents and resource_type == "local_folder":
            folder_path = self.vault.resource_absolute_path(resource)
            self.add_folder_contents_to_tree(
                child,
                folder_path,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

        return child

    def add_folder_contents_to_tree(self, parent_node, folder_path, resource_path_map=None, metadata_container_map=None):
        folder_path = Path(folder_path) if folder_path else None
        resource_path_map = resource_path_map or {}
        metadata_container_map = metadata_container_map or {}

        if not folder_path or not folder_path.exists() or not folder_path.is_dir():
            missing = QTreeWidgetItem(["Folder missing"])
            missing.setIcon(0, load_icon("warning"))
            missing.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder_missing"})
            parent_node.addChild(missing)
            return

        try:
            children = sorted(folder_path.iterdir(), key=lambda path: (path.is_file(), path.name.lower()))
        except PermissionError:
            denied = QTreeWidgetItem(["Permission denied"])
            denied.setIcon(0, load_icon("warning"))
            denied.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder_permission_denied"})
            parent_node.addChild(denied)
            return

        folder_relative_path = self.make_relative_to_current_context(folder_path)
        metadata_children = sorted(
            metadata_container_map.get(folder_relative_path, []),
            key=lambda resource: resource.get("title", "").lower(),
        )

        if not children and not metadata_children:
            empty = QTreeWidgetItem(["Empty folder"])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": "empty_folder"})
            parent_node.addChild(empty)
            return

        for child_path in children:
            try:
                resolved_key = str(child_path.resolve())
            except FileNotFoundError:
                resolved_key = str(child_path)

            resource = resource_path_map.get(resolved_key)

            if resource:
                self.add_resource_tree_item(
                    parent_node,
                    resource,
                    include_folder_contents=child_path.is_dir(),
                    resource_path_map=resource_path_map,
                    metadata_container_map=metadata_container_map,
                )
                continue

            item = QTreeWidgetItem([child_path.name])
            item.setIcon(0, load_icon("folder" if child_path.is_dir() else "file"))
            item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "file_system_entry",
                "path": str(child_path),
            })
            flags = item.flags() | Qt.ItemFlag.ItemIsDragEnabled
            if child_path.is_dir():
                flags |= Qt.ItemFlag.ItemIsDropEnabled
            item.setFlags(flags)
            parent_node.addChild(item)

            if child_path.is_dir() and not child_path.is_symlink():
                self.add_folder_contents_to_tree(
                    item,
                    child_path,
                    resource_path_map=resource_path_map,
                    metadata_container_map=metadata_container_map,
                )

        for metadata_resource in metadata_children:
            self.add_resource_tree_item(
                parent_node,
                metadata_resource,
                include_folder_contents=False,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

    def show_notes_section(self):
        self.resource_tree.clear()

        if not self.current_user_id or not self.current_course_id:
            self.show_text_page("No Course Selected", "Select a course first.", "Notes are attached to the current course or assignment.")
            return

        resources = self.current_context_resources()
        notes = [resource for resource in resources if resource.get("type") == "note"]

        note_group = QTreeWidgetItem(["Notes"])
        note_group.setIcon(0, load_icon("note"))
        note_group.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "resource_type": "note"})
        self.resource_tree.addTopLevelItem(note_group)

        for note in notes:
            child = QTreeWidgetItem([note.get('title', 'Untitled Note')])
            child.setIcon(0, load_icon("note"))
            child.setData(0, Qt.ItemDataRole.UserRole, {"type": "resource", "resource": note})
            note_group.addChild(child)

        if not notes:
            empty = QTreeWidgetItem(["No notes yet."])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": "empty"})
            self.resource_tree.addTopLevelItem(empty)

        self.restore_resource_tree_state(self.pending_resource_tree_state)
        self.show_text_page(
            "Notes",
            "Current note resources",
            """
This section filters note resources for the current course/assignment scope.
            """,
        )

    def current_context_resources(self):
        backend = getattr(self, "file_manager", None)
        if backend is not None and hasattr(self, "current_resource_scope"):
            return backend.metadata.list(self.current_resource_scope(), sync=True)
        return self.vault.load_resources(self.current_user_id, self.current_course_id, self.current_assignment_id)

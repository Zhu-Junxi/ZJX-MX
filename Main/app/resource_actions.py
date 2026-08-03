from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtCore import Qt, QUrl, QItemSelectionModel
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.file_operations import is_transient_file_lock, move_path, remove_path
from core.file_types import TEXT_PREVIEW_SUFFIXES
from core.file_manager import FileManager, ResourceScope
from core.helpers import format_size, normalise_url, slugify, unique_folder_path, unique_path
from core.models import resource_type_display
from core.url_shortcuts import LINK_RESOURCE_TYPES, read_url_shortcut, shortcut_filename, url_shortcut_body, write_url_shortcut
from services.file_preview import can_preview_with_handler, preview_kind, structured_preview_html
from services.google_suite import GOOGLE_TITLES, open_google_creator
from services.microsoft_suite import MICROSOFT_TITLES, MicrosoftSuiteError, create_microsoft_file
from ui.dialogs import TextEditorWindow
from ui.file_explorer_dragdrop import drop_target_from_item, resolve_payload_destination, would_move_folder_into_itself
from ui.icons import load_icon
from ui.resource_library_window import ResourceLibraryWindow
from ui.context_menus import AppContextMenu, QuickMenuAction, add_menu_action, add_quick_action_bar, add_separator_if_needed
from ui.themed_forms import FormField, ThemedFormDialog, ThemedMessageDialog
from services.command_history import (
    CompositeAction,
    FileContentUpdateAction,
    FileCopyAction,
    FileCreateAction,
    FileDeleteAction,
    FileMoveAction,
    FileRenameAction,
    ResourceAddAction,
    ResourceDeleteAction,
    ResourceUpdateAction,
)


class ResourceActionsMixin:
    """Resource import, creation, deletion, and library commands."""

    def release_file_explorer_handles(self):
        if hasattr(self, "release_current_preview_handles"):
            self.release_current_preview_handles()
        library_window = getattr(self, "library_window", None)
        if library_window is not None and hasattr(library_window, "release_library_preview_handles"):
            library_window.release_library_preview_handles()

    def delete_vault_path(self, path):
        """Delete an unmanaged file/folder after clearing app-held previews."""
        path = Path(path)
        if not path.exists():
            return

        self.release_file_explorer_handles()
        remove_path(path)

    def show_file_operation_failed(self, title, error):
        message = "The file operation could not be completed."
        if is_transient_file_lock(error):
            message = "This file is currently open or being used. Close it, then try again."
        if hasattr(self, "show_user_warning"):
            self.show_user_warning(title, message, error=error)
        else:
            QMessageBox.warning(self, title, message)

    def current_context_dir(self):
        return self.vault.context_dir(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def current_top_level_files_dir(self):
        return self.vault.context_files_dir(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def current_top_level_folders_dir(self):
        return self.vault.context_folders_dir(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def current_top_level_notes_dir(self):
        return self.vault.context_notes_dir(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def make_relative_to_current_context(self, path):
        return str(Path(path).relative_to(self.current_context_dir()))

    def current_resource_scope(self):
        return ResourceScope(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def file_backend(self):
        backend = getattr(self, "file_manager", None)
        if backend is None:
            backend = FileManager(self.vault)
            self.file_manager = backend
        return backend

    def create_url_shortcut_resource(self, title, url, resource_type="external_link", tags=None, destination_parent=None):
        result = self.file_backend().add_external_link(
            self.current_resource_scope(),
            title,
            url,
            metadata={"type": resource_type, "tags": list(tags or [])},
            parent=destination_parent,
        )
        return result.resource

    def add_url_shortcut_resource_action(self, title, url, resource_type="external_link", tags=None, destination_parent=None, description=None):
        title = (title or "Link").strip()
        url = normalise_url(url)
        tags = list(tags or [])
        if resource_type not in LINK_RESOURCE_TYPES:
            resource_type = "external_link"

        destination_parent = Path(destination_parent) if destination_parent else self.current_top_level_files_dir()
        destination_parent.mkdir(parents=True, exist_ok=True)
        destination = unique_path(destination_parent, shortcut_filename(title))
        resource = {
            "type": resource_type,
            "title": title,
            "url": url,
            "path": self.make_relative_to_current_context(destination),
            "tags": tags,
        }
        shortcut_content = url_shortcut_body(
            url,
            title=title,
            resource_type=resource_type,
            tags=tags,
            fallback_title=destination.stem,
        )
        action = CompositeAction(
            description or f"Added {resource_type_display(resource_type)} link: {title}",
            [
                FileCreateAction(
                    destination,
                    content=shortcut_content,
                    description=f"Created link shortcut: {destination.name}",
                ),
                ResourceAddAction(
                    self.vault,
                    self.current_user_id,
                    self.current_course_id,
                    self.current_assignment_id,
                    resource,
                    description=f"Added resource: {title}",
                ),
            ],
            action_type="add_link_resource",
            affected_item=str(destination),
        )
        self.command_history.perform(action)
        self.update_history_panel()
        return resource

    def reserved_unique_path(self, directory, filename, reserved_paths=None, *, folder=False):
        directory = Path(directory)
        reserved = {Path(path).resolve() for path in (reserved_paths or set())}

        if folder:
            base_name = slugify(filename)
            candidate = unique_folder_path(directory, filename)
            counter = 2
            while candidate.resolve() in reserved:
                candidate = directory / f"{base_name}_{counter}"
                counter += 1
            return candidate

        original = Path(filename)
        candidate = unique_path(directory, filename)
        counter = 2
        while candidate.resolve() in reserved:
            candidate = directory / f"{original.stem}_{counter}{original.suffix}"
            counter += 1
        return candidate

    def build_file_resource_import_actions(self, source, destination_parent=None, reserved_paths=None):
        source = Path(source)
        if not source.is_file():
            raise ValueError("Source is not a file")

        target_parent = Path(destination_parent) if destination_parent else self.current_top_level_files_dir()
        target_parent.mkdir(parents=True, exist_ok=True)

        shortcut = read_url_shortcut(source)
        if shortcut:
            title = shortcut["title"]
            resource_type = shortcut["type"]
            tags = shortcut["tags"]
            url = shortcut["url"]
            destination = self.reserved_unique_path(target_parent, shortcut_filename(title), reserved_paths)
            resource = {
                "type": resource_type,
                "title": title,
                "url": url,
                "path": self.make_relative_to_current_context(destination),
                "tags": tags,
            }
            return [
                FileCreateAction(
                    destination,
                    content=url_shortcut_body(
                        url,
                        title=title,
                        resource_type=resource_type,
                        tags=tags,
                        fallback_title=destination.stem,
                    ),
                    description=f"Created link shortcut: {destination.name}",
                ),
                ResourceAddAction(
                    self.vault,
                    self.current_user_id,
                    self.current_course_id,
                    self.current_assignment_id,
                    resource,
                    description=f"Added resource: {title}",
                ),
            ], destination

        destination = self.reserved_unique_path(target_parent, source.name, reserved_paths)
        resource = {
            "type": "local_file",
            "title": destination.name,
            "path": self.make_relative_to_current_context(destination),
            "tags": [],
        }
        return [
            FileCopyAction(source, destination, description=f"Imported file: {source.name}"),
            ResourceAddAction(
                self.vault,
                self.current_user_id,
                self.current_course_id,
                self.current_assignment_id,
                resource,
                description=f"Added resource: {destination.name}",
            ),
        ], destination

    def build_folder_resource_import_actions(self, source, destination_parent=None, reserved_paths=None):
        source = Path(source)
        if not source.is_dir():
            raise ValueError("Source is not a folder")

        target_parent = Path(destination_parent) if destination_parent else self.current_top_level_folders_dir()
        target_parent.mkdir(parents=True, exist_ok=True)
        destination = self.reserved_unique_path(target_parent, source.name, reserved_paths, folder=True)
        resource = {
            "type": "local_folder",
            "title": source.name,
            "path": self.make_relative_to_current_context(destination),
            "tags": [],
        }
        return [
            FileCopyAction(source, destination, description=f"Imported folder: {source.name}"),
            ResourceAddAction(
                self.vault,
                self.current_user_id,
                self.current_course_id,
                self.current_assignment_id,
                resource,
                description=f"Added resource: {source.name}",
            ),
        ], destination

    def build_resource_delete_action(self, resource, *, delete_physical=False):
        actions = []
        path = self.vault.resource_absolute_path(resource)
        if delete_physical and path and Path(path).exists():
            path = Path(path)
            item_kind = "folder" if path.is_dir() else "file"
            actions.append(
                FileDeleteAction(
                    path,
                    description=f"Deleted {item_kind}: {path.name}",
                )
            )

        actions.append(
            ResourceDeleteAction(
                self.vault,
                resource,
                description=f"Deleted resource: {resource.get('title', 'resource')}",
            )
        )

        return CompositeAction(
            f"Deleted resource: {resource.get('title', 'resource')}",
            actions,
            action_type="delete_resource",
            affected_item=str(resource.get("id", "")),
        )

    def create_file_resource_from_source(self, source, destination_parent=None):
        result = self.file_backend().import_file(
            source,
            self.current_resource_scope(),
            destination_parent=destination_parent,
        )
        return result.resource

    def create_folder_resource_from_source(self, source, destination_parent=None):
        result = self.file_backend().import_folder(
            source,
            self.current_resource_scope(),
            destination_parent=destination_parent,
        )
        return result.resource


    def add_local_file_dialog(self, destination_parent=None):
        if not self.ensure_course_context():
            return

        file_paths, _ = QFileDialog.getOpenFileNames(self, "Add Local File")
        if not file_paths:
            return

        try:
            actions = []
            reserved_paths = set()
            for file_path in file_paths:
                item_actions, destination = self.build_file_resource_import_actions(
                    file_path,
                    destination_parent=destination_parent,
                    reserved_paths=reserved_paths,
                )
                actions.extend(item_actions)
                reserved_paths.add(destination)

            action = CompositeAction(
                f"Added {len(file_paths)} local file(s)",
                actions,
                action_type="import_files",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception:
            raise


    def import_folder_dialog(self, destination_parent=None):
        if not self.ensure_course_context():
            return

        folder = QFileDialog.getExistingDirectory(self, "Import Folder")
        if not folder:
            return

        try:
            source = Path(folder)
            item_actions, destination = self.build_folder_resource_import_actions(
                source,
                destination_parent=destination_parent,
            )
            action = CompositeAction(
                f"Imported folder: {source.name}",
                item_actions,
                action_type="import_folder",
                affected_item=str(destination),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception:
            raise


    def create_folder_dialog(self, destination_parent=None):
        if not self.ensure_course_context():
            return

        values = ThemedFormDialog.ask(
            self,
            title="Create Folder",
            subtitle="Create a new folder in the current course or assignment scope.",
            fields=[
                FormField("folder_name", "Folder name", placeholder="e.g. Week 4 Resources", required=True),
            ],
            accept_text="Create Folder",
        )
        if not values:
            return

        folder_name = values["folder_name"].strip()
        try:
            destination_parent = Path(destination_parent) if destination_parent else self.current_top_level_folders_dir()
            destination_parent.mkdir(parents=True, exist_ok=True)

            destination = unique_folder_path(destination_parent, folder_name.strip())

            resource = {
                "type": "local_folder",
                "title": folder_name.strip(),
                "path": self.make_relative_to_current_context(destination),
                "tags": [],
            }

            action = CompositeAction(
                f"Created folder: {folder_name.strip()}",
                [
                    FileCreateAction(destination, is_directory=True, description=f"Created folder: {destination.name}"),
                    ResourceAddAction(
                        self.vault,
                        self.current_user_id,
                        self.current_course_id,
                        self.current_assignment_id,
                        resource,
                        description=f"Added resource: {folder_name.strip()}",
                    ),
                ],
                action_type="create_folder",
                affected_item=str(destination),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception:
            raise


    def create_text_file_dialog(self, destination_parent=None):
        if not self.ensure_course_context():
            return

        values = ThemedFormDialog.ask(
            self,
            title="Create New File",
            subtitle="Create a lightweight file directly inside the selected folder or current scope. Use the extension field for formats such as txt, md, csv, or json.",
            fields=[
                FormField("file_name", "File name", placeholder="e.g. tutorial-notes", required=True),
                FormField("extension", "File extension", default="txt", placeholder="txt"),
                FormField("content", "Initial content", kind="textarea", placeholder="Optional starting text..."),
            ],
            accept_text="Create File",
        )
        if not values:
            return

        file_name = values["file_name"].strip()
        extension = (values.get("extension") or "txt").strip().lstrip(".") or "txt"
        if not Path(file_name).suffix:
            file_name = f"{file_name}.{extension}"

        try:
            destination_parent = Path(destination_parent) if destination_parent else self.current_top_level_files_dir()
            destination_parent.mkdir(parents=True, exist_ok=True)
            destination = unique_path(destination_parent, file_name)

            resource = {
                "type": "local_file",
                "title": destination.name,
                "path": self.make_relative_to_current_context(destination),
                "tags": [],
            }
            action = CompositeAction(
                f"Created file: {destination.name}",
                [
                    FileCreateAction(
                        destination,
                        content=values.get("content", ""),
                        description=f"Created file: {destination.name}",
                    ),
                    ResourceAddAction(
                        self.vault,
                        self.current_user_id,
                        self.current_course_id,
                        self.current_assignment_id,
                        resource,
                        description=f"Added resource: {destination.name}",
                    ),
                ],
                action_type="create_file",
                affected_item=str(destination),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception:
            raise

    def create_microsoft_suite_file(self, kind, destination_parent=None):
        if not self.ensure_course_context():
            return

        display_name = MICROSOFT_TITLES.get(kind, "Microsoft file")
        values = ThemedFormDialog.ask(
            self,
            title=f"Create {display_name}",
            subtitle="Create a real local Microsoft Office file in the selected folder or current assignment folder.",
            fields=[
                FormField("file_name", "File name", default=display_name, required=True),
            ],
            accept_text="Create File",
        )
        if not values:
            return

        file_name = values["file_name"].strip()
        try:
            destination_parent = Path(destination_parent) if destination_parent else self.current_top_level_files_dir()
            destination_parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="zjx_lms_ms_create_") as temp_dir:
                generated_path = create_microsoft_file(temp_dir, file_name, kind)
                destination = unique_path(destination_parent, generated_path.name)
                resource = {
                    "type": "local_file",
                    "title": destination.name,
                    "path": self.make_relative_to_current_context(destination),
                    "tags": ["microsoft", kind],
                }
                action = CompositeAction(
                    f"Created {display_name}: {destination.name}",
                    [
                        FileCopyAction(
                            generated_path,
                            destination,
                            description=f"Created file: {destination.name}",
                        ),
                        ResourceAddAction(
                            self.vault,
                            self.current_user_id,
                            self.current_course_id,
                            self.current_assignment_id,
                            resource,
                            description=f"Added resource: {destination.name}",
                        ),
                    ],
                    action_type="create_microsoft_file",
                    affected_item=str(destination),
                )
                self.command_history.perform(action)
                self.update_history_panel()
            self.change_section("Files")
        except MicrosoftSuiteError as exc:
            ThemedMessageDialog.show(
                self,
                title="Could not create Microsoft file",
                subtitle="The Microsoft suite helper could not finish the file creation.",
                body=str(exc),
                accept_text="Got it",
            )
        except Exception:
            raise

    def create_google_suite_link(self, kind):
        if not self.ensure_course_context():
            return

        display_name = GOOGLE_TITLES.get(kind, "Google file")
        starter_url = open_google_creator(kind)

        values = ThemedFormDialog.ask(
            self,
            title=f"Save {display_name} Link",
            subtitle="A new Google file tab has opened. After Google creates the document, paste its final share link here to save it in this assignment.",
            fields=[
                FormField("title", "Resource title", default=f"New {display_name}", required=True),
                FormField("url", "Google Drive link", default=starter_url, placeholder="Paste the final Google file URL here", required=True),
            ],
            accept_text="Save Link",
        )
        if not values:
            return

        title = values["title"].strip()
        url = values["url"].strip()
        try:
            self.add_url_shortcut_resource_action(
                title,
                url,
                resource_type="google_drive",
                tags=["google", kind],
                description=f"Added {display_name} link: {title}",
            )
            self.change_section("Files")
        except Exception:
            raise

    def show_context_feature_later(self, feature_name):
        ThemedMessageDialog.show(
            self,
            title=f"{feature_name} is planned",
            subtitle="This option is now placed in the menu structure for discoverability.",
            body="The current build keeps this as a safe placeholder instead of creating invalid Office or cloud placeholder files. It can be connected to real Microsoft/Google document creation in a later integration pass.",
            accept_text="Got it",
        )

    def selected_tree_item_path_for_location(self):
        selected_item = self.resource_tree.currentItem()
        data = selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else None
        if not data:
            return None

        if data.get("type") == "file_system_entry":
            path = Path(data.get("path", ""))
            return path if path.exists() else None

        if data.get("type") == "resource":
            resource = data.get("resource", {}) or {}
            if resource.get("path"):
                path = self.vault.resource_absolute_path(resource)
                return path if path and path.exists() else None

        return None

    def show_selected_tree_item_in_file_location(self):
        path = self.selected_tree_item_path_for_location()
        if not path:
            self.open_current_scope_folder()
            return

        path = Path(path)
        folder = path if path.is_dir() else path.parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


    def add_note_dialog(self):
        if not self.ensure_course_context():
            return

        values = ThemedFormDialog.ask(
            self,
            title="Add Note",
            subtitle="Create the note title and content in one themed dialog.",
            fields=[
                FormField("title", "Note title", placeholder="e.g. Tutorial questions", required=True),
                FormField("content", "Note content", kind="textarea", placeholder="Write your note here..."),
            ],
            accept_text="Create Note",
        )
        if not values:
            return

        title = values["title"].strip()
        content = values["content"]

        try:
            filename = slugify(title.strip()) + ".md"
            destination = unique_path(self.current_top_level_notes_dir(), filename)

            resource = {
                "type": "note",
                "title": title.strip(),
                "path": self.make_relative_to_current_context(destination),
                "tags": [],
            }
            action = CompositeAction(
                f"Added note: {title.strip()}",
                [
                    FileCreateAction(
                        destination,
                        content=content,
                        description=f"Created note: {destination.name}",
                    ),
                    ResourceAddAction(
                        self.vault,
                        self.current_user_id,
                        self.current_course_id,
                        self.current_assignment_id,
                        resource,
                        description=f"Added resource: {title.strip()}",
                    ),
                ],
                action_type="add_note",
                affected_item=str(destination),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception:
            raise


    def add_external_resource_dialog(self, resource_type):
        if not self.ensure_course_context():
            return

        display_name = resource_type_display(resource_type)
        values = ThemedFormDialog.ask(
            self,
            title=f"Add {display_name}",
            subtitle="Save the resource title and link in one step.",
            fields=[
                FormField("title", "Resource title", required=True),
                FormField("url", "URL", placeholder="https://...", required=True),
            ],
            accept_text=f"Add {display_name}",
        )
        if not values:
            return

        title = values["title"].strip()
        url = values["url"].strip()

        try:
            self.add_url_shortcut_resource_action(
                title,
                url,
                resource_type=resource_type,
                tags=[],
                description=f"Added {display_name}: {title}",
            )
            self.change_section("Files")
        except Exception:
            raise


    def delete_selected_resource(self):
        selected_item = self.resource_tree.currentItem()
        if not selected_item:
            return

        data = selected_item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "resource":
            return

        resource = data["resource"]
        reply = QMessageBox.question(
            self,
            "Delete Resource",
            "Delete this resource?\n\nYes = delete metadata and physical file/folder if it is inside the vault.\nNo = delete metadata only.\nCancel = do nothing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        delete_physical = reply == QMessageBox.StandardButton.Yes

        if not delete_physical:
            try:
                action = ResourceDeleteAction(
                    self.vault,
                    resource,
                    description=f"Deleted resource: {resource.get('title', 'resource')}",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                self.change_section(self.current_section)
            except Exception as error:
                self.show_file_operation_failed("Delete Failed", error)
            return

        try:
            self.release_file_explorer_handles()
            action = self.build_resource_delete_action(resource, delete_physical=True)
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section(self.current_section)
        except Exception as error:
            self.show_file_operation_failed("Delete Failed", error)

    def delete_resource_from_library(self, resource):
        if not resource:
            return False

        reply = QMessageBox.question(
            self,
            "Delete Resource",
            "Delete this resource?\n\nYes = delete metadata and physical file/folder if it is inside the vault.\nNo = delete metadata only.\nCancel = do nothing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return False

        delete_physical = reply == QMessageBox.StandardButton.Yes

        if not delete_physical:
            try:
                action = ResourceDeleteAction(
                    self.vault,
                    resource,
                    description=f"Deleted resource: {resource.get('title', 'resource')}",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                self.refresh_after_resource_change(resource)
                return True
            except Exception as error:
                self.show_file_operation_failed("Delete Failed", error)
                return False

        try:
            self.release_file_explorer_handles()
            action = self.build_resource_delete_action(resource, delete_physical=True)
            self.command_history.perform(action)
            self.update_history_panel()
            self.refresh_after_resource_change(resource)
            return True
        except Exception as error:
            self.show_file_operation_failed("Delete Failed", error)
            return False

    def delete_resources_from_library(self, resources):
        resources = [resource for resource in resources if resource]

        if not resources:
            return False

        reply = QMessageBox.question(
            self,
            "Delete Resources",
            f"Delete {len(resources)} selected resource(s)?\n\nThis will delete metadata and physical files/folders when they are inside the vault.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        try:
            self.release_file_explorer_handles()
            actions = []
            for resource in resources:
                actions.append(self.build_resource_delete_action(resource, delete_physical=True))

            action = CompositeAction(
                f"Deleted {len(resources)} resource(s)",
                actions,
                action_type="delete_resources",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.refresh_after_resource_change()
            return True
        except Exception as error:
            self.show_file_operation_failed("Delete Failed", error)
            return False


    def open_current_scope_folder(self):
        if not self.ensure_course_context():
            return

        context = self.vault.context_dir(self.current_user_id, self.current_course_id, self.current_assignment_id)
        context.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(context)))

    def open_resource_library(self):
        self.update_sidebar_active_state("Resource Library")
        self.library_window = ResourceLibraryWindow(self)
        self.library_window.show()

    def get_current_tree_target_folder(self):
        selected_items = self.resource_tree.selectedItems()

        if not selected_items:
            return None

        item = selected_items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return None

        if data.get("type") == "resource":
            resource = data.get("resource")

            if resource and resource.get("type") == "local_folder":
                return self.vault.resource_absolute_path(resource)

        if data.get("type") == "file_system_entry":
            path = Path(data.get("path"))

            if path.is_dir():
                return path

            return path.parent

        return None
    
    def get_selected_resource_items(self):
        selected_items = []

        for item in self.resource_tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if not data:
                continue

            if data.get("type") in ["resource", "file_system_entry"]:
                selected_items.append(item)

        return selected_items


    def get_selected_resources(self):
        resources = []

        for item in self.get_selected_resource_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get("type") == "resource":
                resources.append(data.get("resource"))

        return resources
    def select_all_resources(self):
        if self.current_section != "Files":
            return

        self.resource_tree.selectAll()

    def clipboard_entry_from_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            resource = data.get("resource")
            if not resource:
                return None
            return {"type": "resource", "resource_id": resource.get("id"), "resource": dict(resource)}

        if item_type == "file_system_entry":
            path = data.get("path")
            if not path:
                return None
            return {"type": "file_system_entry", "path": path}

        return None

    def copy_resource_entries(self, entries):
        entries = [entry for entry in entries if entry]
        if not entries:
            return

        self.resource_clipboard = {"mode": "copy", "entries": entries}
        self.show_text_page("Copied", self.current_context_label(), f"Copied {len(entries)} item(s). Select a folder and press Ctrl+V to paste.")

    def cut_resource_entries(self, entries):
        entries = [entry for entry in entries if entry]
        if not entries:
            return

        self.resource_clipboard = {"mode": "cut", "entries": entries}
        self.show_text_page("Cut", self.current_context_label(), f"Cut {len(entries)} item(s). Select a destination folder and press Ctrl+V to move.")

    def copy_selected_resources(self):
        entries = []
        for item in self.get_selected_resource_items():
            entry = self.clipboard_entry_from_item(item)
            if entry:
                entries.append(entry)

        self.copy_resource_entries(entries)

    def cut_selected_resources(self):
        entries = []
        for item in self.get_selected_resource_items():
            entry = self.clipboard_entry_from_item(item)
            if entry:
                entries.append(entry)

        self.cut_resource_entries(entries)


    def paste_resources(self):
        if self.current_section != "Files":
            return

        self.paste_resources_to_folder(self.get_current_tree_target_folder())

    def paste_resources_to_folder(self, destination_parent=None):
        if self.current_section != "Files":
            return

        mode = self.resource_clipboard.get("mode")
        entries = self.resource_clipboard.get("entries", [])

        if not mode or not entries:
            return

        self.release_file_explorer_handles()

        if mode == "copy":
            copied = 0
            failed = []
            actions = []
            reserved_paths = set()

            for entry in entries:
                try:
                    item_actions, destination = self.build_clipboard_copy_actions(
                        entry,
                        destination_parent=destination_parent,
                        reserved_paths=reserved_paths,
                    )
                    if item_actions:
                        actions.extend(item_actions)
                        copied += 1
                    if destination:
                        reserved_paths.add(destination)
                except Exception as error:
                    failed.append(str(error))

            if actions:
                action = CompositeAction(
                    "Paste copied item(s)",
                    actions,
                    action_type="paste_copied_items",
                )
                self.command_history.perform(action)
                self.update_history_panel()

            self.refresh_resource_tree_preserving_state()

            if failed:
                self.show_user_warning(
                    "Paste Partially Failed",
                    f"{len(failed)} item(s) could not be pasted.",
                    context={"failures": failed[:10]},
                )
            elif copied:
                self.show_text_page("Copied", self.current_context_label(), f"Copied {copied} item(s).")
            return

        moved = 0
        failed = []
        actions = []
        reserved_paths = set()

        for entry in entries:
            try:
                entry_destination = self.destination_for_clipboard_entry(entry, destination_parent)
                if entry.get("type") == "resource":
                    resource = self.current_resource_by_id(entry.get("resource_id"), entry.get("resource"))
                    if not resource:
                        continue
                    item_actions, destination = self.build_resource_move_actions(
                        resource,
                        entry_destination,
                        reserved_paths=reserved_paths,
                    )
                else:
                    source_path = Path(entry.get("path", ""))
                    if not source_path.exists():
                        continue
                    if not entry_destination:
                        entry_destination = self.destination_for_clipboard_entry(entry, None)
                    item_actions, destination = self.build_file_system_entry_move_actions(
                        source_path,
                        entry_destination,
                        create_resource=self.is_top_level_context_destination(entry_destination),
                        reserved_paths=reserved_paths,
                    )

                if item_actions:
                    actions.extend(item_actions)
                    moved += 1
                if destination:
                    reserved_paths.add(destination)
            except Exception as error:
                failed.append(str(error))

        if actions:
            action = CompositeAction(
                "Move cut item(s)",
                actions,
                action_type="move_cut_items",
            )
            self.command_history.perform(action)
            self.update_history_panel()

        self.resource_clipboard = {"mode": None, "entries": []}
        self.refresh_resource_tree_preserving_state()

        if failed:
            self.show_user_warning(
                "Paste Partially Failed",
                f"{len(failed)} item(s) could not be pasted.",
                context={"failures": failed[:10]},
            )
        elif moved:
            self.show_text_page("Moved", self.current_context_label(), f"Moved {moved} item(s).")


    def delete_selected_resources(self):
        items = self.get_selected_resource_items()

        if not items:
            return

        reply = QMessageBox.question(
            self,
            "Delete Items",
            f"Delete {len(items)} selected item(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.release_file_explorer_handles()
            actions = []
            for item in items:
                data = item.data(0, Qt.ItemDataRole.UserRole) or {}

                if data.get("type") == "resource":
                    resource = data.get("resource")
                    if resource:
                        actions.append(self.build_resource_delete_action(resource, delete_physical=True))

                elif data.get("type") == "file_system_entry":
                    path = Path(data.get("path", ""))
                    if path.exists():
                        actions.append(
                            FileDeleteAction(
                                path,
                                description=f"Deleted {'folder' if path.is_dir() else 'file'}: {path.name}",
                            )
                        )

            if not actions:
                return

            action = CompositeAction(
                f"Deleted {len(actions)} item(s)",
                actions,
                action_type="delete_items",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section(self.current_section)

        except Exception as error:
            self.show_file_operation_failed("Delete Failed", error)

    def open_selected_resource(self):
        items = self.get_selected_resource_items()

        if not items:
            return

        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return

        if data.get("type") == "resource":
            self.open_resource(data.get("resource"))

        elif data.get("type") == "file_system_entry":
            path = Path(data.get("path"))

            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


    def rename_selected_resource(self):
        items = self.get_selected_resource_items()

        if len(items) != 1:
            QMessageBox.information(
                self,
                "Rename",
                "Select exactly one item to rename."
            )
            return

        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return

        if data.get("type") == "resource":
            self.edit_resource(data.get("resource"))

        elif data.get("type") == "file_system_entry":
            self.rename_file_system_entry(Path(data.get("path")))


    # =========================================================
    # CLICK HANDLERS
    # =========================================================

    def show_list_item_detail(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        data_type = data.get("type")
        if data_type == "create_user":
            self.show_text_page(
                "Create New User",
                "Onboarding",
                "Double-click this item to create a local user profile. The Canvas token is stored for later API integration only.",
            )
        elif data_type == "user":
            self.show_user_detail(data["user"])
        elif data_type == "course":
            self.show_course_dashboard_page(data["course"], preview_mode=True)
        elif data_type == "dashboard_overview":
            self.show_global_dashboard_page()
        elif data_type == "global_assignment":
            course = data.get("course")
            if course:
                self.set_current_course(course["id"])
            self.show_assignment_dashboard_page(data["assignment"], general=False, preview_mode=True)
        elif data_type == "course_sync_action":
            action = data.get("action")
            if action == "sync_now":
                self.show_text_page(
                    "Sync Canvas Data",
                    "Manual sync",
                    "Use the Sync Canvas button above the Courses list to import Canvas courses, assignments, and announcements. Finished and blacklisted courses are hidden from the active list.",
                )
            elif action == "blacklist":
                self.show_setting_detail("canvas_blacklist")
            elif action == "favourites":
                self.show_setting_detail("canvas_favourites")
        elif data_type == "empty_courses":
            self.show_text_page(
                "No Active Courses",
                "Courses",
                "Use + Add Course for a manual course, Sync Canvas to import Canvas courses, or Blacklist to review courses hidden from this list.",
            )
        elif data_type == "assignment_general":
            self.show_assignment_dashboard_page(assignment=None, general=True, preview_mode=True)
        elif data_type == "assignment":
            self.show_assignment_dashboard_page(data["assignment"], general=False, preview_mode=True)
        elif data_type == "empty_assignments":
            self.show_text_page(
                "No Active Assignments",
                self.current_context_label(),
                "Completed assignments are hidden from this list. Overdue assignments stay active until you archive them.",
            )
        elif data_type == "setting":
            self.show_setting_detail(data.get("action"))
        elif data_type == "help_topic":
            self.show_help_topic(data.get("topic", "shortcuts"))

    def show_resource_tree_item_detail(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        data_type = data.get("type")
        if data_type == "resource":
            self.preview_resource(data["resource"])
        elif data_type == "file_system_entry":
            self.preview_file_system_entry(Path(data["path"]))
        elif data_type == "scope_info":
            self.show_text_page(
                "Current Scope",
                self.current_context_label(),
                """
This tells you where new resources will be saved.

Resources belong to:
User → Course → Assignment / General Course Resources

This avoids the giant messy file dump problem.
                """,
            )
        elif data_type == "group":
            resource_type = data.get("resource_type")
            self.show_text_page(
                resource_type_display(resource_type),
                "Resource group",
                f"""
This group contains resources of type:

{resource_type_display(resource_type)}
                """,
            )

    def open_list_item(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        data_type = data.get("type")
        if data_type == "create_user":
            self.show_create_user_dialog(required=False)
        elif data_type == "user":
            self.set_current_user(data["user"]["id"])
            self.change_section("Dashboard")
        elif data_type == "course":
            self.set_current_course(data["course"]["id"])
            self.change_section("Assignments")
        elif data_type == "course_sync_action":
            action = data.get("action")
            if action == "sync_now":
                self.sync_canvas_data_for_user(self.get_current_user())
            elif action == "blacklist":
                self.manage_canvas_course_preferences("blacklist")
            elif action == "favourites":
                self.manage_canvas_course_preferences("favourites")
        elif data_type == "empty_courses":
            return
        elif data_type == "assignment_general":
            self.set_current_assignment(None)
            self.change_section("Files")
        elif data_type == "assignment":
            self.set_current_assignment(data["assignment"]["id"])
            self.change_section("Files")
        elif data_type == "dashboard_overview":
            self.show_global_dashboard_page()
        elif data_type == "global_assignment":
            course = data.get("course")
            assignment = data.get("assignment")
            if course and assignment:
                self.open_course_assignment_from_card(assignment, course)
        elif data_type == "setting":
            self.run_setting_action(data.get("action"))
        elif data_type == "help_topic":
            self.show_help_topic(data.get("topic", "shortcuts"))

    def open_resource_tree_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "resource":
            self.open_resource(data["resource"])
        elif data.get("type") == "file_system_entry":
            QDesktopServices.openUrl(QUrl.fromLocalFile(data["path"]))

    # =========================================================
    # RESOURCE PREVIEW
    # =========================================================

    def preview_resource(self, resource):
        resource_type = resource.get("type")
        title = resource.get("title", "Untitled Resource")
        subtitle = resource_type_display(resource_type)

        if resource_type in ["local_file", "note"]:
            path = self.vault.resource_absolute_path(resource)

            if not path or not path.exists():
                self.show_text_page(title, subtitle, self.resource_details_text(resource) + "\n\nFile does not exist.")
                return

            self.preview_local_path(title, subtitle, path, self.resource_details_text(resource))
            return

        if resource_type == "local_folder":
            path = self.vault.resource_absolute_path(resource)
            if path and path.exists():
                try:
                    item_count = len(list(path.iterdir()))
                except PermissionError:
                    item_count = "Permission denied"
            else:
                item_count = "Folder missing"

            self.show_text_page(
                title,
                subtitle,
                self.resource_details_text(resource) + f"\n\nFolder item count:\n{item_count}",
            )
            return

        self.show_text_page(
            title,
            subtitle,
            self.resource_details_text(resource) + "\n\nExternal resources are stored as metadata links.",
        )

    def preview_file_system_entry(self, path):
        path = Path(path)

        if not path.exists():
            self.show_text_page(
                "Missing File",
                str(path),
                "This file or folder no longer exists inside the imported folder.",
            )
            return

        if path.is_dir():
            try:
                child_count = len(list(path.iterdir()))
            except PermissionError:
                child_count = "Permission denied"

            self.show_text_page(
                path.name,
                "Folder inside imported folder",
                self.file_system_entry_details_text(path)
                + f"\n\n==================== PREVIEW ====================\n\nFolder overview\n\nItems inside: {child_count}",
            )
            return

        details = self.file_system_entry_details_text(path)
        self.preview_local_path(path.name, "File inside imported folder", path, details)

    def preview_local_path(self, title, subtitle, path, details):
        kind = preview_kind(path)

        if kind == "image":
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.show_image_page(title, subtitle, pixmap, details)
                return

        if kind in {"text", "office", "archive"}:
            content = structured_preview_html(path) if can_preview_with_handler(path) else self.read_text_preview(path)
            self.show_text_page(
                title,
                subtitle,
                details + "\n\n==================== PREVIEW ====================\n\n" + (content or "Preview is empty."),
            )
            return

        if kind == "pdf":
            self.show_pdf_page(title, subtitle, path, details)
            return

        if kind in {"video", "audio"}:
            self.show_media_page(title, subtitle, path, details, kind)
            return

        self.show_text_page(
            title,
            subtitle,
            details + "\n\nPreview is not available for this file type.\n\nUse Open to view it in the default application.",
        )

    def file_system_entry_details_text(self, path):
        path = Path(path)
        details = [
            "File System Entry Details",
            "",
            f"Name: {path.name}",
            f"Location: {path}",
            f"Type: {'Folder' if path.is_dir() else 'File'}",
        ]

        if path.exists() and path.is_file():
            details.append(f"Size: {format_size(path.stat().st_size)}")
            details.append(
                f"Last modified: {datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return "\n".join(details)

    def read_text_preview(self, path, max_chars=30000):
        path = Path(path)
        suffix = path.suffix.lower()

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as error:
            return f"Could not read file preview:\n{error}"

        if suffix == ".json":
            try:
                data = json.loads(text)
                text = json.dumps(data, indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        if suffix == ".csv":
            lines = text.splitlines()
            text = "\n".join(lines[:40])
            if len(lines) > 40:
                text += f"\n\n... showing first 40 lines out of {len(lines)}"

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n... preview truncated"

        return text

    def resource_scope_text(self, resource):
        user = self.vault.get_user(resource["user_id"])
        course = self.vault.get_course(resource["user_id"], resource["course_id"])
        assignment = None

        if resource.get("assignment_id"):
            assignment = self.vault.get_assignment(resource["user_id"], resource["course_id"], resource["assignment_id"])

        user_name = user["name"] if user else resource.get("user_id")
        course_name = f"{course['code']} - {course['name']}" if course else resource.get("course_id")
        assignment_name = assignment["title"] if assignment else "General Course Resources"
        return f"{user_name} / {course_name} / {assignment_name}"

    def resource_details_text(self, resource):
        resource_type = resource.get("type")
        details = [
            "Resource Details",
            "",
            f"Title: {resource.get('title', 'Untitled')}",
            f"Type: {resource_type_display(resource_type)}",
            f"Created: {resource.get('created_at', 'Unknown')}",
            f"Updated: {resource.get('updated_at', 'Unknown')}",
        ]

        if resource.get("tags"):
            details.append(f"Tags: {', '.join(resource.get('tags'))}")

        if resource.get("path"):
            absolute_path = self.vault.resource_absolute_path(resource)
            details.append("")
            details.append(f"Relative path: {resource.get('path')}")
            details.append(f"Absolute path: {absolute_path}")

            if absolute_path and absolute_path.exists() and absolute_path.is_file():
                details.append(f"Size: {format_size(absolute_path.stat().st_size)}")
                modified = datetime.fromtimestamp(absolute_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                details.append(f"Last modified: {modified}")

        if resource.get("url"):
            details.append("")
            details.append(f"URL: {resource.get('url')}")

        return "\n".join(details)

    # =========================================================
    # SETTINGS DETAIL / ACTIONS
    def open_resource(self, resource):
        resource_type = resource.get("type")

        if resource_type in ["local_file", "local_folder", "note"]:
            path = self.vault.resource_absolute_path(resource)
            if not path or not path.exists():
                QMessageBox.warning(self, "Missing Resource", "The local file or folder no longer exists.")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return

        url = resource.get("url")
        if not url:
            QMessageBox.warning(self, "Missing URL", "This external resource has no URL.")
            return

        QDesktopServices.openUrl(QUrl(normalise_url(url)))

    # =========================================================
    # CONTEXT MENUS
    # =========================================================

    def add_menu_action(self, menu, label, icon_name=None, callback=None, enabled=True, shortcut=None):
        return add_menu_action(menu, label, icon_name, callback, enabled, shortcut)


    def open_item_list_context_menu(self, position):
        menu = AppContextMenu(self)

        context_item = self.item_list.itemAt(position)
        if context_item:
            self.item_list.setCurrentItem(context_item)

        if self.current_section == "Users":
            selected_item = self.item_list.currentItem()
            selected_data = selected_item.data(Qt.ItemDataRole.UserRole) if selected_item else None

            menu.addSection("Users")
            self.add_menu_action(menu, "Add User", "plus", self.add_user_dialog)

            if selected_data and selected_data.get("type") == "user":
                selected_user = selected_data.get("user")
                menu.addSeparator()
                menu.addSection("Selected User")
                self.add_menu_action(
                    menu,
                    "Open Dashboard",
                    "check",
                    lambda checked=False, user=selected_user: self.select_user_and_open_courses(user),
                )
                self.add_menu_action(
                    menu,
                    "Edit User",
                    "edit",
                    lambda checked=False, user=selected_user: self.edit_user_dialog(user),
                )
                self.add_menu_action(
                    menu,
                    "Sync Canvas",
                    "sync",
                    lambda checked=False, user=selected_user: self.sync_canvas_data_for_user(user),
                )
                self.add_menu_action(
                    menu,
                    "Delete User",
                    "delete",
                    lambda checked=False, user=selected_user: self.delete_user_dialog(user),
                )
        elif self.current_section == "Courses":
            selected_item = self.item_list.currentItem()
            selected_data = selected_item.data(Qt.ItemDataRole.UserRole) if selected_item else None

            menu.addSection("Courses")
            self.add_menu_action(menu, "Add Course", "plus", self.add_course_dialog)
            self.add_menu_action(
                menu,
                "Sync Canvas",
                "sync",
                lambda checked=False: self.sync_canvas_data_for_user(self.get_current_user()),
            )
            self.add_menu_action(
                menu,
                "Manage Skipped",
                "ban",
                lambda checked=False: self.manage_canvas_course_preferences("blacklist"),
            )
            self.add_menu_action(
                menu,
                "Manage Pinned",
                "star",
                lambda checked=False: self.manage_canvas_course_preferences("favourites"),
            )

            if selected_data and selected_data.get("type") == "course":
                menu.addSeparator()
                menu.addSection("Selected Course")
                selected_course = selected_data.get("course")
                if selected_course and selected_course.get("source") == "canvas":
                    self.add_menu_action(
                        menu,
                        "Toggle Pin",
                        "star",
                        lambda checked=False, course=selected_course: self.toggle_single_canvas_course_preference(course, "favourites"),
                    )
                    self.add_menu_action(
                        menu,
                        "Toggle Skip",
                        "ban",
                        lambda checked=False, course=selected_course: self.toggle_single_canvas_course_preference(course, "blacklist"),
                    )
                self.add_menu_action(
                    menu,
                    "Archive Course",
                    "archive",
                    lambda checked=False, course=selected_course: self.archive_course_dialog(course),
                )
                self.add_menu_action(
                    menu,
                    "Delete Course",
                    "delete",
                    lambda checked=False, course=selected_data.get("course"): self.delete_course_dialog(course),
                )

        elif self.current_section == "Assignments":
            selected_item = self.item_list.currentItem()
            selected_data = selected_item.data(Qt.ItemDataRole.UserRole) if selected_item else None

            menu.addSection("Assignments")
            self.add_menu_action(menu, "Add Assignment", "plus", self.add_assignment_dialog)

            if selected_data and selected_data.get("type") == "assignment":
                menu.addSeparator()
                menu.addSection("Selected Assignment")
                selected_assignment = selected_data.get("assignment")
                completed = self.assignment_is_completed(selected_assignment) if hasattr(self, "assignment_is_completed") else bool(selected_assignment.get("completed"))
                complete_label = "Mark Active" if completed else "Mark Finished"
                self.add_menu_action(
                    menu,
                    complete_label,
                    "check",
                    lambda checked=False, assignment=selected_assignment, value=not completed: self.set_assignment_completed_from_dashboard(assignment, value),
                )
                self.add_menu_action(
                    menu,
                    "Edit Assignment",
                    "edit",
                    lambda checked=False, assignment=selected_assignment: self.edit_assignment_dialog(assignment),
                )
                self.add_menu_action(
                    menu,
                    "Delete Assignment",
                    "delete",
                    lambda checked=False, assignment=selected_assignment: self.delete_assignment_dialog(assignment),
                )
        elif self.current_section == "Settings":
            menu.addSection("Vault")
            self.add_menu_action(menu, "Change Vault", "settings", self.choose_vault_folder)
            self.add_menu_action(menu, "Open Vault", "folder", self.open_vault_folder)
            self.add_menu_action(menu, "Reset Vault", "refresh", self.reset_vault_folder)
            menu.addSeparator()
            menu.addSection("Tools")
            self.add_menu_action(menu, "Open Library", "library", self.open_resource_library)
            menu.addSeparator()
            menu.addSection("Interface")
            self.add_menu_action(
                menu,
                "Toggle History",
                "settings",
                lambda checked=False: self.set_history_panel_visible(not self.history_panel_visible),
            )

        if menu.actions():
            menu.exec(self.item_list.mapToGlobal(position))

    def open_resource_tree_context_menu(self, position):
        if self.current_section != "Files":
            return

        clicked_item = self.resource_tree.itemAt(position)
        if clicked_item:
            if clicked_item.isSelected():
                # Preserve multi-selection when opening the context menu on an
                # already-selected item.
                self.resource_tree.selectionModel().setCurrentIndex(
                    self.resource_tree.indexFromItem(clicked_item),
                    QItemSelectionModel.SelectionFlag.NoUpdate,
                )
            else:
                self.resource_tree.clearSelection()
                clicked_item.setSelected(True)
                self.resource_tree.setCurrentItem(clicked_item)
        else:
            self.resource_tree.clearSelection()
            self.resource_tree.setCurrentItem(None)

        menu = AppContextMenu(self)

        selected_items = self.get_selected_resource_items() if clicked_item else []
        selected_count = len(selected_items)
        selected_item = clicked_item if clicked_item and clicked_item in selected_items else (selected_items[0] if selected_items else None)
        selected_data = selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else None
        target_folder = self.target_folder_path_from_item(selected_item)
        selected_clipboard_entries = []
        for item in selected_items:
            entry = self.clipboard_entry_from_item(item)
            if entry:
                selected_clipboard_entries.append(entry)
        clipboard_has_entries = bool(self.resource_clipboard.get("mode") and self.resource_clipboard.get("entries"))

        def data_local_path(data):
            if not data:
                return None
            if data.get("type") == "file_system_entry":
                path = Path(data.get("path", ""))
                return path if path.exists() else None
            if data.get("type") == "resource":
                resource = data.get("resource", {}) or {}
                if resource.get("path"):
                    path = self.vault.resource_absolute_path(resource)
                    return path if path and Path(path).exists() else None
            return None

        selected_local_path = data_local_path(selected_data)
        selected_is_single = selected_count == 1
        selected_is_manageable = bool(selected_is_single and selected_data and selected_data.get("type") in {"resource", "file_system_entry"})
        selected_is_text_editable = bool(selected_is_single and selected_data and self.is_tree_item_text_editable(selected_data))
        has_selection = selected_count > 0

        # Windows 11-style quick command strip: high-frequency operations only.
        quick_actions = [
            QuickMenuAction("Cut", "cut", lambda entries=selected_clipboard_entries: self.cut_resource_entries(entries), has_selection, "Ctrl+X"),
            QuickMenuAction("Copy", "copy", lambda entries=selected_clipboard_entries: self.copy_resource_entries(entries), has_selection, "Ctrl+C"),
            QuickMenuAction("Rename / Edit", "edit", self.edit_selected_tree_item, selected_is_manageable, "F2"),
            QuickMenuAction("Delete", "delete", self.delete_selected_resources if selected_count > 1 else self.delete_selected_tree_item, has_selection, "Del"),
            QuickMenuAction("Refresh", "refresh", self.manual_refresh_file_explorer, True, "F5"),
        ]
        add_quick_action_bar(menu, quick_actions, self)
        add_separator_if_needed(menu)

        # Main list actions: keep creation obvious and keep grouped suites below.
        if clipboard_has_entries:
            self.add_menu_action(
                menu,
                "Paste",
                "paste",
                lambda destination=target_folder: self.paste_resources_to_folder(destination),
                True,
                "Ctrl+V",
            )

        self.add_menu_action(
            menu,
            "New File",
            "file",
            lambda: self.create_text_file_dialog(destination_parent=target_folder),
        )
        self.add_menu_action(
            menu,
            "New Folder",
            "folder",
            lambda: self.create_folder_dialog(destination_parent=target_folder),
        )

        local_menu = menu.add_app_menu("folder", "Local")
        self.add_menu_action(local_menu, "Add Local File", "file", lambda: self.add_local_file_dialog(destination_parent=target_folder))
        self.add_menu_action(local_menu, "Add Local Folder", "folder", lambda: self.import_folder_dialog(destination_parent=target_folder))

        microsoft_menu = menu.add_app_menu("file", "Microsoft Suite")
        self.add_menu_action(microsoft_menu, "New Microsoft Document", "file", lambda: self.create_microsoft_suite_file("document", destination_parent=target_folder))
        self.add_menu_action(microsoft_menu, "New Microsoft PowerPoint", "file", lambda: self.create_microsoft_suite_file("powerpoint", destination_parent=target_folder))
        self.add_menu_action(microsoft_menu, "New Microsoft Excel", "file", lambda: self.create_microsoft_suite_file("excel", destination_parent=target_folder))

        google_menu = menu.add_app_menu("cloud", "Google Suite")
        self.add_menu_action(google_menu, "New Google Docs", "cloud", lambda: self.create_google_suite_link("docs"))
        self.add_menu_action(google_menu, "New Google Slides", "cloud", lambda: self.create_google_suite_link("slides"))
        self.add_menu_action(google_menu, "New Google Sheets", "cloud", lambda: self.create_google_suite_link("sheets"))

        external_menu = menu.add_app_menu("link", "External Links")
        self.add_menu_action(external_menu, "Canvas Link", "canvas", lambda: self.add_external_resource_dialog("canvas"))
        self.add_menu_action(external_menu, "YouTube Link", "video", lambda: self.add_external_resource_dialog("youtube"))
        self.add_menu_action(external_menu, "Google Drive Link", "cloud", lambda: self.add_external_resource_dialog("google_drive"))
        self.add_menu_action(external_menu, "Other Link", "link", lambda: self.add_external_resource_dialog("external_link"))

        view_menu = menu.add_app_menu("open", "View")
        if selected_local_path:
            self.add_menu_action(view_menu, "Open File Location", "folder", self.show_selected_tree_item_in_file_location)
        self.add_menu_action(view_menu, "Open Assignment Folder", "folder", self.open_current_scope_folder)

        if selected_count > 1:
            add_separator_if_needed(menu)
            self.add_menu_action(menu, f"Move {selected_count} Items To Root", "move", self.move_selected_item_to_scope_root)
            self.add_menu_action(menu, f"Delete {selected_count} Items", "delete", self.delete_selected_resources)
        elif selected_is_manageable:
            add_separator_if_needed(menu)
            if selected_is_text_editable:
                self.add_menu_action(menu, "Edit Text", "edit", self.edit_selected_text_item)
            self.add_menu_action(menu, "Move To Root", "move", self.move_selected_item_to_scope_root)

        menu.exec(self.resource_tree.mapToGlobal(position))


    # =========================================================
    # RESOURCE REFRESH / CLIPBOARD OPERATIONS
    # =========================================================
    def manual_refresh_file_explorer(self):
        if self.current_section != "Files":
            return

        self.refresh_resource_tree_preserving_state()

    def refresh_resource_tree_preserving_state(self):
        """Refresh the resource tree without disrupting expanded/selected state."""
        if self.current_section != "Files":
            return

        if self.current_user_id and self.current_course_id:
            self.vault.sync_context_resource_metadata(
                self.current_user_id,
                self.current_course_id,
                self.current_assignment_id,
            )

        self.pending_resource_tree_state = self.capture_resource_tree_state()

        self.show_files_section()

        self.pending_resource_tree_state = None

    def current_resource_by_id(self, resource_id, resource_hint=None):
        """Fetch the latest copy of a resource from metadata before acting on it."""
        if resource_hint:
            user_id = resource_hint.get("user_id", self.current_user_id)
            course_id = resource_hint.get("course_id", self.current_course_id)
            assignment_id = resource_hint.get("assignment_id", self.current_assignment_id)
        else:
            user_id = self.current_user_id
            course_id = self.current_course_id
            assignment_id = self.current_assignment_id

        for resource in self.vault.load_resources(user_id, course_id, assignment_id):
            if resource.get("id") == resource_id:
                return resource

        return dict(resource_hint) if resource_hint else None

    def destination_for_clipboard_entry(self, entry, destination_parent):
        """Return a sensible destination folder for paste/move operations."""
        if destination_parent:
            return Path(destination_parent)

        entry_type = entry.get("type")

        if entry_type == "resource":
            resource = entry.get("resource", {})
            resource_type = resource.get("type")

            if resource_type == "note":
                return self.current_top_level_notes_dir()

            if resource_type == "local_folder":
                return self.current_top_level_folders_dir()

            if resource_type == "local_file" or (resource_type in LINK_RESOURCE_TYPES and resource.get("path")):
                return self.current_top_level_files_dir()

            # Metadata-only resources have no physical destination at root.
            return None

        source_path = Path(entry.get("path", ""))

        if source_path.is_dir():
            return self.current_top_level_folders_dir()

        return self.current_top_level_files_dir()

    def make_relative_to_resource_context(self, resource, path):
        """Return a path relative to the resource's own context.

        This matters when actions are triggered from Resource Library, because
        the selected resource may belong to a different user/course/assignment
        than the currently open Files tab.
        """
        context_dir = self.vault.context_dir(
            resource.get("user_id"),
            resource.get("course_id"),
            resource.get("assignment_id"),
        )
        return str(Path(path).relative_to(context_dir))

    def set_metadata_resource_container(self, resource, destination_parent):
        """Move an external/metadata resource into a folder visually via metadata."""
        if destination_parent:
            resource["container_path"] = self.make_relative_to_resource_context(resource, destination_parent)
        else:
            resource.pop("container_path", None)

        resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.vault.update_resource(resource)
        return True

    def copy_clipboard_entry_to_folder(self, entry, destination_parent):
        destination_parent = self.destination_for_clipboard_entry(entry, destination_parent)

        if entry.get("type") == "resource":
            resource = self.current_resource_by_id(entry.get("resource_id"), entry.get("resource"))

            if not resource:
                return False

            try:
                self.file_backend().copy_resource(
                    resource["id"],
                    new_parent=destination_parent,
                    scope=ResourceScope.from_resource(resource),
                )
                return True
            except Exception as error:
                self.show_user_warning(
                    "Copy Failed",
                    "The item could not be copied.",
                    error=error,
                    context={"resource": resource.get("title")},
                )
                return False

        source_path = Path(entry.get("path", ""))

        if not source_path.exists():
            return False

        if not destination_parent:
            destination_parent = self.destination_for_clipboard_entry(entry, None)

        if source_path.is_dir():
            destination = unique_folder_path(destination_parent, source_path.name)
            shutil.copytree(source_path, destination)
            resource_type = "local_folder"
        else:
            destination = unique_path(destination_parent, source_path.name)
            shutil.copy2(source_path, destination)
            resource_type = "local_file"

        if self.is_top_level_context_destination(destination_parent):
            self.vault.add_resource(
                self.current_user_id,
                self.current_course_id,
                self.current_assignment_id,
                {
                    "type": resource_type,
                    "title": destination.name,
                    "path": self.make_relative_to_current_context(destination),
                    "tags": [],
                },
            )

        return True

    def build_clipboard_copy_actions(self, entry, destination_parent=None, reserved_paths=None):
        destination_parent = self.destination_for_clipboard_entry(entry, destination_parent)

        if entry.get("type") == "resource":
            resource = self.current_resource_by_id(entry.get("resource_id"), entry.get("resource"))

            if not resource:
                return [], None

            resource_type = resource.get("type")

            if resource_type in LINK_RESOURCE_TYPES and not resource.get("path"):
                copied = dict(resource)
                copied.pop("id", None)
                copied.pop("created_at", None)
                copied.pop("updated_at", None)
                copied["title"] = f"{resource.get('title', 'Untitled')} copy"

                if destination_parent:
                    copied["container_path"] = self.make_relative_to_current_context(destination_parent)
                else:
                    copied.pop("container_path", None)

                return [
                    ResourceAddAction(
                        self.vault,
                        self.current_user_id,
                        self.current_course_id,
                        self.current_assignment_id,
                        copied,
                        description=f"Copied resource: {copied['title']}",
                    )
                ], None

            source_path = self.vault.resource_absolute_path(resource)

            if not source_path or not source_path.exists():
                return [], None

            if not destination_parent:
                destination_parent = self.destination_for_clipboard_entry(entry, None)

            destination = self.reserved_unique_path(
                destination_parent,
                source_path.name,
                reserved_paths,
                folder=source_path.is_dir(),
            )

            copied = dict(resource)
            copied.pop("id", None)
            copied.pop("created_at", None)
            copied.pop("updated_at", None)
            copied["title"] = destination.name
            copied["path"] = self.make_relative_to_current_context(destination)
            copied.pop("container_path", None)

            return [
                FileCopyAction(
                    source_path,
                    destination,
                    description=f"Copied {'folder' if source_path.is_dir() else 'file'}: {source_path.name}",
                ),
                ResourceAddAction(
                    self.vault,
                    self.current_user_id,
                    self.current_course_id,
                    self.current_assignment_id,
                    copied,
                    description=f"Added resource: {destination.name}",
                ),
            ], destination

        source_path = Path(entry.get("path", ""))

        if not source_path.exists():
            return [], None

        if not destination_parent:
            destination_parent = self.destination_for_clipboard_entry(entry, None)

        destination = self.reserved_unique_path(
            destination_parent,
            source_path.name,
            reserved_paths,
            folder=source_path.is_dir(),
        )
        actions = [
            FileCopyAction(
                source_path,
                destination,
                description=f"Copied {'folder' if source_path.is_dir() else 'file'}: {source_path.name}",
            )
        ]

        if self.is_top_level_context_destination(destination_parent):
            resource_type = "local_folder" if source_path.is_dir() else "local_file"
            actions.append(
                ResourceAddAction(
                    self.vault,
                    self.current_user_id,
                    self.current_course_id,
                    self.current_assignment_id,
                    {
                        "type": resource_type,
                        "title": destination.name,
                        "path": self.make_relative_to_current_context(destination),
                        "tags": [],
                    },
                    description=f"Added resource: {destination.name}",
                )
            )

        return actions, destination

    def build_resource_move_actions(self, resource, destination_parent, *, create_resource=False, reserved_paths=None):
        resource_type = resource.get("type")

        if resource_type in LINK_RESOURCE_TYPES and not resource.get("path"):
            before_resource = dict(resource)
            after_resource = dict(resource)
            if destination_parent:
                after_resource["container_path"] = self.make_relative_to_resource_context(resource, destination_parent)
            else:
                after_resource.pop("container_path", None)
            after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
            return [
                ResourceUpdateAction(
                    self.vault,
                    before_resource,
                    after_resource,
                    description=f"Moved resource: {resource.get('title', 'resource')}",
                )
            ], None

        source_path = self.vault.resource_absolute_path(resource)
        if not source_path or not Path(source_path).exists():
            return [], None

        source_path = Path(source_path)
        if not destination_parent:
            destination_parent = self.top_level_destination_for_path(source_path, resource_type)
        destination_parent = Path(destination_parent)

        if would_move_folder_into_itself(source_path, destination_parent):
            raise ValueError("You cannot move a folder into itself or one of its own subfolders.")
        if source_path.parent.resolve() == destination_parent.resolve():
            return [], source_path

        destination = self.reserved_unique_path(
            destination_parent,
            source_path.name,
            reserved_paths,
            folder=source_path.is_dir(),
        )
        before_resource = dict(resource)
        after_resource = dict(resource)
        after_resource["path"] = self.make_relative_to_resource_context(resource, destination)
        after_resource.pop("container_path", None)
        after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")

        return [
            FileMoveAction(
                source_path,
                destination,
                description=f"Moved {'folder' if source_path.is_dir() else 'file'}: {source_path.name}",
            ),
            ResourceUpdateAction(
                self.vault,
                before_resource,
                after_resource,
                description=f"Updated resource: {resource.get('title', source_path.name)}",
            ),
        ], destination

    def build_file_system_entry_move_actions(self, source_path, destination_parent, *, create_resource=False, reserved_paths=None):
        source_path = Path(source_path)
        if not source_path.exists():
            return [], None
        destination_parent = Path(destination_parent)

        if would_move_folder_into_itself(source_path, destination_parent):
            raise ValueError("You cannot move a folder into itself or one of its own subfolders.")
        if source_path.parent.resolve() == destination_parent.resolve():
            return [], source_path

        destination = self.reserved_unique_path(
            destination_parent,
            source_path.name,
            reserved_paths,
            folder=source_path.is_dir(),
        )
        actions = [
            FileMoveAction(
                source_path,
                destination,
                description=f"Moved {'folder' if source_path.is_dir() else 'file'}: {source_path.name}",
            )
        ]

        if create_resource:
            resource_type = "local_folder" if source_path.is_dir() else "local_file"
            actions.append(
                ResourceAddAction(
                    self.vault,
                    self.current_user_id,
                    self.current_course_id,
                    self.current_assignment_id,
                    {
                        "type": resource_type,
                        "title": destination.name,
                        "path": self.make_relative_to_current_context(destination),
                        "tags": [],
                    },
                    description=f"Added resource: {destination.name}",
                )
            )

        return actions, destination

    def move_clipboard_entry_to_folder(self, entry, destination_parent):
        destination_parent = self.destination_for_clipboard_entry(entry, destination_parent)

        if entry.get("type") == "resource":
            resource = self.current_resource_by_id(entry.get("resource_id"), entry.get("resource"))
            if not resource:
                return False
            return self.move_resource_to_folder(resource, destination_parent)

        source_path = Path(entry.get("path", ""))

        if not source_path.exists():
            return False

        if not destination_parent:
            destination_parent = self.destination_for_clipboard_entry(entry, None)

        return self.move_file_system_entry_to_folder(
            source_path,
            destination_parent,
            create_resource=self.is_top_level_context_destination(destination_parent),
        )

    # =========================================================
    # INTERNAL RESOURCE ORGANISATION
    # =========================================================

    def target_folder_path_from_item(self, item):
        """Return the nearest physical folder path that can accept drops.

        If the selected item is a file inside an imported folder, we walk upward
        to its parent folder item so context-menu actions still feel natural.
        """
        cursor = item

        while cursor:
            data = cursor.data(0, Qt.ItemDataRole.UserRole) or {}
            item_type = data.get("type")

            if item_type == "resource":
                resource = data.get("resource", {})
                if resource.get("type") == "local_folder":
                    path = self.vault.resource_absolute_path(resource)
                    if path and path.exists() and path.is_dir():
                        return path

            if item_type == "file_system_entry":
                path = Path(data.get("path", ""))
                if path.exists() and path.is_dir():
                    return path

            cursor = cursor.parent()

        return None

    def top_level_destination_for_path(self, source_path, resource_type=None):
        source_path = Path(source_path)

        if resource_type == "note":
            return self.current_top_level_notes_dir()

        if source_path.is_dir() or resource_type == "local_folder":
            return self.current_top_level_folders_dir()

        return self.current_top_level_files_dir()

    def safe_move_path(self, source_path, destination_parent):
        source_path = Path(source_path)
        destination_parent = Path(destination_parent)
        destination_parent.mkdir(parents=True, exist_ok=True)

        if not source_path.exists():
            raise ValueError("Source item no longer exists.")

        if would_move_folder_into_itself(source_path, destination_parent):
            raise ValueError("You cannot move a folder into itself or one of its own subfolders.")

        if source_path.parent.resolve() == destination_parent.resolve():
            return source_path

        self.release_file_explorer_handles()

        if source_path.is_dir():
            destination = unique_folder_path(destination_parent, source_path.name)
        else:
            destination = unique_path(destination_parent, source_path.name)

        move_path(source_path, destination)
        return destination

    def update_resource_path_after_move(self, resource, new_path):
        resource["path"] = self.make_relative_to_resource_context(resource, new_path)
        resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.vault.update_resource(resource)
        return resource

    def move_resource_to_folder(self, resource, destination_parent):
        try:
            if not destination_parent and not (
                resource.get("type") in LINK_RESOURCE_TYPES and not resource.get("path")
            ):
                source_path = self.vault.resource_absolute_path(resource)
                if not source_path:
                    return False
                destination_parent = self.top_level_destination_for_path(source_path, resource.get("type"))

            self.file_backend().move_resource(
                resource["id"],
                destination_parent,
                scope=ResourceScope.from_resource(resource),
            )
            return True
        except Exception as error:
            self.show_user_warning(
                "Move Failed",
                "The item could not be moved.",
                error=error,
                context={"resource": resource.get("title"), "source_path": source_path},
            )
            return False

    def move_file_system_entry_to_folder(self, source_path, destination_parent, create_resource=False):
        source_path = Path(source_path)

        try:
            new_path = self.safe_move_path(source_path, destination_parent)
        except Exception as error:
            self.show_user_warning(
                "Move Failed",
                "The item could not be moved.",
                error=error,
                context={"source_path": source_path, "destination_parent": destination_parent},
            )
            return False

        if create_resource:
            resource_type = "local_folder" if new_path.is_dir() else "local_file"
            resource = {
                "type": resource_type,
                "title": new_path.name,
                "path": self.make_relative_to_current_context(new_path),
                "tags": [],
            }
            self.vault.add_resource(
                self.current_user_id,
                self.current_course_id,
                self.current_assignment_id,
                resource,
            )

        return True


    def handle_internal_resource_drop(self, source_items, target_item):
        if not source_items:
            return False

        if not isinstance(source_items, (list, tuple)):
            source_items = [source_items]

        payloads = []
        for source_item in source_items:
            if not source_item or target_item is source_item:
                continue
            source_data = source_item.data(0, Qt.ItemDataRole.UserRole) or {}
            if source_data.get("type") in {"resource", "file_system_entry"}:
                payloads.append(dict(source_data))

        return self.handle_internal_resource_payload_drop(
            payloads,
            drop_target_from_item(target_item, self),
            refresh=True,
        )

    def handle_internal_resource_payload_drop(self, payloads, drop_target=None, refresh=False):
        payloads = [dict(payload) for payload in (payloads or []) if payload and payload.get("type") in {"resource", "file_system_entry"}]
        if not payloads:
            return False

        if not isinstance(drop_target, dict):
            drop_target = drop_target_from_item(drop_target, self)
        moved_count = 0
        state = self.capture_resource_tree_state()
        failures = []
        actions = []
        reserved_paths = set()

        try:
            self.release_file_explorer_handles()
            for source_data in payloads:
                source_type = source_data.get("type")
                item_destination = resolve_payload_destination(source_data, drop_target, self)

                if source_type == "resource":
                    resource = source_data.get("resource", {})
                    resource = self.current_resource_by_id(resource.get("id"), resource) or resource
                    item_actions, destination = self.build_resource_move_actions(
                        resource,
                        item_destination,
                        reserved_paths=reserved_paths,
                    )
                else:
                    item_actions, destination = self.build_file_system_entry_move_actions(
                        Path(source_data.get("path", "")),
                        item_destination,
                        create_resource=self.is_top_level_context_destination(item_destination),
                        reserved_paths=reserved_paths,
                    )

                moved = bool(item_actions) or destination is not None
                if item_actions:
                    actions.extend(item_actions)
                if moved:
                    moved_count += 1
                if destination:
                    reserved_paths.add(destination)
                if not moved:
                    failures.append(source_data)

            if actions and not failures:
                action = CompositeAction(
                    f"Moved {moved_count} item(s)",
                    actions,
                    action_type="move_items",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                if refresh:
                    self.refresh_files_tree_after_move(state)
                return True

            if failures and moved_count:
                QMessageBox.warning(
                    self,
                    "Move Incomplete",
                    "Some items could not be moved. The Files view will refresh so you can check the current state.",
                )
                if refresh:
                    self.refresh_files_tree_after_move(state)
                return True
            if moved_count and not failures:
                if refresh:
                    self.refresh_files_tree_after_move(state)
                return True
            return False

        except Exception as error:
            self.show_user_warning(
                "Move Failed",
                "The selected item(s) could not be moved.",
                error=error,
            )
            return False

    def move_file_explorer_payloads(self, payloads, drop_target=None, refresh=False):
        return self.handle_internal_resource_payload_drop(payloads, drop_target, refresh=refresh)

    def refresh_files_tree_after_move(self, state=None):
        try:
            self.pending_resource_tree_state = state
            self.show_files_section()
        finally:
            self.pending_resource_tree_state = None

    def is_top_level_context_destination(self, destination_parent):
        if not destination_parent:
            return False
        destination_parent = Path(destination_parent).resolve()
        top_level_dirs = [
            self.current_top_level_files_dir().resolve(),
            self.current_top_level_folders_dir().resolve(),
            self.current_top_level_notes_dir().resolve(),
        ]

        return destination_parent in top_level_dirs

    def is_text_editable_path(self, path):
        path = Path(path)
        return path.exists() and path.is_file() and path.suffix.lower() in TEXT_PREVIEW_SUFFIXES

    def path_from_tree_item_data(self, data):
        if not data:
            return None

        item_type = data.get("type")
        if item_type == "resource":
            resource = data.get("resource", {})
            if resource.get("type") in {"local_file", "note"}:
                return self.vault.resource_absolute_path(resource)
            return None

        if item_type == "file_system_entry":
            return Path(data.get("path", ""))

        return None

    def is_tree_item_text_editable(self, data):
        path = self.path_from_tree_item_data(data)
        return bool(path and self.is_text_editable_path(path))

    def edit_selected_text_item(self):
        selected_item = self.resource_tree.currentItem()
        if not selected_item:
            return

        data = selected_item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            self.open_text_editor_for_resource(data.get("resource", {}))
            return

        if item_type == "file_system_entry":
            self.open_text_editor_for_path(Path(data.get("path", "")))

    def open_text_editor_for_resource(self, resource):
        path = self.vault.resource_absolute_path(resource)
        if not path or not self.is_text_editable_path(path):
            QMessageBox.information(self, "Text Editor", "This resource is not a supported editable text file.")
            return

        def save_callback(file_path, content):
            try:
                path = Path(file_path)
                before_resource = dict(resource)
                after_resource = dict(resource)
                after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
                action = CompositeAction(
                    f"Edited file: {path.name}",
                    [
                        FileContentUpdateAction(
                            path,
                            path.read_bytes(),
                            content,
                            description=f"Edited file: {path.name}",
                        ),
                        ResourceUpdateAction(
                            self.vault,
                            before_resource,
                            after_resource,
                            description=f"Updated resource: {before_resource.get('title', path.name)}",
                        ),
                    ],
                    action_type="edit_file",
                    affected_item=str(before_resource.get("id", "")),
                )
                self.command_history.perform(action)
                self.update_history_panel()
                resource.update(after_resource)
                self.refresh_after_resource_change(after_resource)
                self.preview_resource(after_resource)
                return True
            except Exception:
                raise

        self.open_text_editor(path, save_callback)

    def open_text_editor_for_path(self, path, context=None):
        path = Path(path)
        if not self.is_text_editable_path(path):
            QMessageBox.information(self, "Text Editor", "This item is not a supported editable text file.")
            return

        def save_callback(file_path, content):
            try:
                path = Path(file_path)
                action = FileContentUpdateAction(
                    path,
                    path.read_bytes(),
                    content,
                    description=f"Edited file: {path.name}",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                if self.current_section == "Files":
                    self.refresh_resource_tree_preserving_state()
                if self.library_window and hasattr(self.library_window, "refresh_tree"):
                    self.library_window.refresh_tree()
                self.preview_file_system_entry(file_path)
                return True
            except Exception:
                raise

        self.open_text_editor(path, save_callback)

    def open_text_editor(self, path, save_callback):
        editor = TextEditorWindow(path, save_callback, parent=self)
        self.editor_windows.append(editor)
        editor.destroyed.connect(
            lambda *_args, window=editor: self.editor_windows.remove(window)
            if window in self.editor_windows else None
        )
        editor.show()

    def edit_selected_tree_item(self):
        selected_item = self.resource_tree.currentItem()

        if not selected_item:
            return

        data = selected_item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            self.edit_resource(data.get("resource", {}))
        elif item_type == "file_system_entry":
            self.rename_file_system_entry(Path(data.get("path", "")))

    def edit_resource(self, resource):
        resource_type = resource.get("type")

        if resource_type in LINK_RESOURCE_TYPES:
            self.edit_external_resource(resource)
        elif resource_type == "note":
            self.edit_note_resource(resource)
        elif resource_type in {"local_file", "local_folder"}:
            self.rename_local_resource(resource)


    def edit_external_resource(self, resource):
        values = ThemedFormDialog.ask(
            self,
            title="Edit Resource",
            subtitle="Update the display title and destination URL in one step.",
            fields=[
                FormField("title", "Title", default=resource.get("title", ""), required=True),
                FormField("url", "URL", default=resource.get("url", ""), required=True),
            ],
            accept_text="Save Resource",
        )
        if not values:
            return

        title = values["title"].strip()
        url = normalise_url(values["url"].strip())
        before_resource = dict(resource)
        after_resource = dict(resource)
        after_resource["title"] = title
        after_resource["url"] = url
        after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")

        try:
            actions = []
            path = self.vault.resource_absolute_path(resource)
            if path and Path(path).exists() and resource.get("type") in LINK_RESOURCE_TYPES:
                after_shortcut = url_shortcut_body(
                    after_resource["url"],
                    title=after_resource["title"],
                    resource_type=after_resource.get("type", "external_link"),
                    tags=after_resource.get("tags", []),
                    fallback_title=Path(path).stem,
                )
                actions.append(
                    FileContentUpdateAction(
                        path,
                        Path(path).read_bytes(),
                        after_shortcut,
                        description=f"Edited shortcut: {Path(path).name}",
                    )
                )

            actions.append(
                ResourceUpdateAction(
                    self.vault,
                    before_resource,
                    after_resource,
                    description=f"Edited resource: {before_resource.get('title', 'resource')}",
                )
            )
            action = CompositeAction(
                f"Edited resource: {before_resource.get('title', 'resource')}",
                actions,
                action_type="edit_resource",
                affected_item=str(before_resource.get("id", "")),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            resource.update(after_resource)
            self.refresh_after_resource_change(after_resource)
        except Exception:
            raise


    def edit_note_resource(self, resource):
        path = self.vault.resource_absolute_path(resource)

        existing_content = ""
        if path and path.exists() and path.is_file():
            existing_content = path.read_text(encoding="utf-8", errors="replace")

        values = ThemedFormDialog.ask(
            self,
            title="Edit Note",
            subtitle="Change the note title and body without moving through multiple popups.",
            fields=[
                FormField("title", "Title", default=resource.get("title", ""), required=True),
                FormField("content", "Content", kind="textarea", default=existing_content),
            ],
            accept_text="Save Note",
        )
        if not values:
            return

        title = values["title"].strip()
        content = values["content"]
        before_resource = dict(resource)
        after_resource = dict(resource)
        after_resource["title"] = title
        after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")

        try:
            actions = []
            if path and path.exists() and path.is_file():
                actions.append(
                    FileContentUpdateAction(
                        path,
                        Path(path).read_bytes(),
                        content,
                        description=f"Edited note body: {Path(path).name}",
                    )
                )

            actions.append(
                ResourceUpdateAction(
                    self.vault,
                    before_resource,
                    after_resource,
                    description=f"Edited note: {before_resource.get('title', '')}",
                )
            )
            action = CompositeAction(
                f"Edited note: {before_resource.get('title', '')}",
                actions,
                action_type="edit_note",
                affected_item=str(before_resource.get("id", "")),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            resource.update(after_resource)
            self.refresh_after_resource_change(after_resource)
        except Exception:
            raise


    def rename_local_resource(self, resource):
        path = self.vault.resource_absolute_path(resource)

        if not path or not path.exists():
            QMessageBox.warning(self, "Missing Resource", "The local file or folder no longer exists.")
            return

        values = ThemedFormDialog.ask(
            self,
            title="Rename Resource",
            subtitle="Update the local file or folder name.",
            fields=[
                FormField("name", "New name", default=path.name, required=True),
            ],
            accept_text="Rename",
        )
        if not values:
            return

        new_name = values["name"].strip()
        if path.is_file() and "." not in Path(new_name).name and path.suffix:
            new_name += path.suffix

        new_path = path.with_name(new_name)
        if new_path.exists():
            QMessageBox.warning(self, "Rename Failed", "A file or folder with that name already exists.")
            return

        try:
            self.release_file_explorer_handles()
            before_resource = dict(resource)
            after_resource = dict(resource)
            after_resource["title"] = new_path.name
            after_resource["path"] = self.make_relative_to_resource_context(resource, new_path)
            after_resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
            action = CompositeAction(
                f"Renamed resource: {path.name} -> {new_path.name}",
                [
                    FileRenameAction(
                        path,
                        new_path,
                        description=f"Renamed file: {path.name} -> {new_path.name}",
                    ),
                    ResourceUpdateAction(
                        self.vault,
                        before_resource,
                        after_resource,
                        description=f"Updated resource: {before_resource.get('title', 'resource')}",
                    ),
                ],
                action_type="rename_resource",
                affected_item=str(before_resource.get("id", "")),
            )
            self.command_history.perform(action)
            self.update_history_panel()
            resource.update(after_resource)
            self.refresh_after_resource_change(after_resource)
        except Exception as error:
            self.show_file_operation_failed("Rename Failed", error)


    def rename_file_system_entry(self, path):
        path = Path(path)

        if not path.exists():
            QMessageBox.warning(self, "Missing Item", "This file or folder no longer exists.")
            return

        values = ThemedFormDialog.ask(
            self,
            title="Rename Item",
            subtitle="Update this file or folder name.",
            fields=[
                FormField("name", "New name", default=path.name, required=True),
            ],
            accept_text="Rename",
        )
        if not values:
            return

        new_name = values["name"].strip()
        if path.is_file() and "." not in Path(new_name).name and path.suffix:
            new_name += path.suffix

        new_path = path.with_name(new_name)
        if new_path.exists():
            QMessageBox.warning(self, "Rename Failed", "A file or folder with that name already exists.")
            return

        try:
            self.release_file_explorer_handles()
            action = FileRenameAction(
                path,
                new_path,
                description=f"Renamed file: {path.name} -> {new_path.name}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception as error:
            self.show_file_operation_failed("Rename Failed", error)


    def move_selected_item_to_scope_root(self):
        items = self.get_selected_resource_items()
        if not items and self.resource_tree.currentItem():
            items = [self.resource_tree.currentItem()]

        if not items:
            return

        moved_count = 0
        actions = []
        reserved_paths = set()

        try:
            self.release_file_explorer_handles()
            for selected_item in items:
                data = selected_item.data(0, Qt.ItemDataRole.UserRole) or {}
                item_type = data.get("type")

                if item_type == "resource":
                    resource = data.get("resource", {})
                    source_path = self.vault.resource_absolute_path(resource)

                    if resource.get("type") in LINK_RESOURCE_TYPES and not resource.get("path"):
                        destination_parent = None
                    else:
                        destination_parent = self.top_level_destination_for_path(source_path, resource.get("type"))

                    item_actions, destination = self.build_resource_move_actions(
                        resource,
                        destination_parent,
                        reserved_paths=reserved_paths,
                    )
                    if item_actions:
                        actions.extend(item_actions)
                        moved_count += 1
                    if destination:
                        reserved_paths.add(destination)

                elif item_type == "file_system_entry":
                    source_path = Path(data.get("path", ""))
                    destination_parent = self.top_level_destination_for_path(source_path)
                    item_actions, destination = self.build_file_system_entry_move_actions(
                        source_path,
                        destination_parent,
                        create_resource=True,
                        reserved_paths=reserved_paths,
                    )
                    if item_actions:
                        actions.extend(item_actions)
                        moved_count += 1
                    if destination:
                        reserved_paths.add(destination)

            if moved_count:
                action = CompositeAction(
                    "Move selected items to scope root" if len(items) > 1 else "Move item to scope root",
                    actions,
                    action_type="move_items_to_root",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                self.change_section("Files")
        except Exception:
            raise

    def delete_selected_tree_item(self):
        items = self.get_selected_resource_items()
        if len(items) > 1:
            self.delete_selected_resources()
            return

        selected_item = self.resource_tree.currentItem() or (items[0] if items else None)

        if not selected_item:
            return

        data = selected_item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            self.delete_selected_resource()
        elif item_type == "file_system_entry":
            self.delete_file_system_entry(Path(data.get("path", "")))


    def delete_file_system_entry(self, path):
        path = Path(path)
        if not path.exists():
            return

        reply = QMessageBox.question(
            self,
            "Delete Item",
            f"Delete this item permanently from the vault?\\n\\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.release_file_explorer_handles()
            item_kind = "folder" if path.is_dir() else "file"
            action = FileDeleteAction(path, description=f"Deleted {item_kind}: {path.name}")
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Files")
        except Exception as error:
            self.show_file_operation_failed("Delete Failed", error)

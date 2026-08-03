# ZJX LMS Codebase Notes

This project is intentionally split into small layers before Canvas API integration starts.

## Main layers

- `main.py` starts the Qt application.
- `app/main_window.py` owns application state, navigation, top-level section routing, and shared UI layout.
- `app/actions.py` is the compatibility composition point for command mixins, global shortcuts, and undo/redo history.
- `app/settings.py` wraps persistent local settings such as vault path and current user/course context.
- `app/ui_content.py` stores static Settings and Help section copy/metadata.
- `app/styles.py` stores the global Qt stylesheet. The `build_app_stylesheet(theme, accent, zoom_percent)` entrypoint appends named component override sections for context menus, trees, assignment rows, and preview readability.
- `app/settings_views.py` owns Settings list/detail rendering.
- `app/resource_tree.py` owns the main file explorer tree population and Notes/Files resource sections.
- `app/text_preview_views.py` owns reusable Preview/Details cards and right-panel text/image display helpers.
- `app/dashboard_views.py` owns global, course, assignment, announcement, and todo dashboard views.
- `app/settings_actions.py` owns Settings/theme/zoom/preference commands.
- `app/canvas_actions.py` owns Canvas sync and Canvas course preference commands.
- `app/entity_actions.py` owns user, course, and assignment CRUD commands.
- `app/resource_actions.py` owns resource import/create/delete/library commands, resource previews, resource context menus, clipboard/move/drop handling, and text edit/rename operations.
- `core/vault_manager.py` is the storage and metadata layer. Keep it UI-free.
- `core/helpers.py`, `core/file_types.py`, and `core/detail_text.py` contain reusable pure helpers.
- `services/command_history.py` contains undo/redo snapshot support.
- `ui/browser_widgets.py` contains custom list/tree widgets and delegates.
- `ui/components.py` contains small reusable UI builders for shared cards, labels, buttons, metric cards, and section headers.
- `ui/context_menus.py` is the single context-menu API. All new menus should use `AppContextMenu`, `MenuActionSpec`, `QuickMenuAction`, or `add_menu_action()` from this module.
- `ui/dialogs.py` contains standalone dialogs/windows.
- `ui/resource_library_window.py` contains the global resource browser window.

## Design rule before Canvas API work

Keep Canvas API access outside the UI widgets. The recommended next layer is:

```text
services/canvas_client.py       # raw Canvas HTTP/API wrapper
services/canvas_sync.py         # converts Canvas objects into VaultManager data
```

The UI should call a sync service, not Canvas endpoints directly.

## Canvas API integration layer

The first Canvas implementation is intentionally separated from the UI:

- `services/canvas_client.py` owns Canvas REST access, token auth, pagination, and connection errors.
- `core/validation.py` owns input validation for users, Canvas URLs/tokens, manual courses, and due dates.
- `core/vault_manager.py` persists Canvas-imported data with stable IDs:
  - Courses use `canvas_<canvas_course_id>`.
  - Assignments use `canvas_<canvas_assignment_id>`.
- `app/canvas_actions.py` coordinates the manual sync action from the UI.

Canvas sync currently imports current courses and their assignments. Existing Canvas records are updated on re-sync instead of duplicated. Manual records remain separate.

## Canvas API v2 notes

Canvas sync now imports three course-level data types:

- current Canvas courses;
- assignments for each imported course;
- announcements for each imported course.

The sync action shows a pre-sync explanation and a progress dialog so users can see what the app is doing instead of assuming the UI has frozen.

Assignments can be marked as finished from the course dashboard. Finished assignments are hidden from the active course dashboard and remain accessible in the Resource Library under `Archived Assignments`.

The main window now chooses an initial size from the available screen geometry and keeps the middle/right panels resizable, rather than assuming a fixed 1500 px desktop width.

## Canvas sync preferences

Canvas sync preferences are stored on each user profile:

- `canvas_blacklisted_course_ids`: Canvas course IDs skipped during sync and hidden from the active Courses list.
- `canvas_favourite_course_ids`: Canvas course IDs pinned to the top of the Courses list.

The Canvas API client still fetches the live course list first, then `CanvasActionsMixin.sync_canvas_data_for_user()` filters out blacklisted courses before saving course, assignment, and announcement metadata. Auto sync is app-level QSettings state and is intentionally off by default so startup remains fast.

## v6.0 UI Theme and Library Editing Pass

- Appearance is now driven by `AppSettings` and `build_app_stylesheet(theme, accent, zoom_percent)`.
- The sidebar has a compact Help + theme-toggle row.
- Settings includes Theme Mode, Follow System Theme, and Accent Colour controls.
- Context menus should be built through `ui.context_menus` so icons, shortcuts, disabled states, quick action bars, retained `QAction` wrappers, and theme styling remain uniform.
- Resource Library supports open, text edit, rename/edit, move-to-root, delete, expand/collapse, and archived filtering for existing items.

## Private beta release metadata and assets

- `app/app_info.py` centralises the release name/version displayed in the app and Settings.
- `assets/app_icon.ico`, `assets/app_icon.png`, and `assets/app_icon.svg` provide the application icon assets for packaging.
- `ui/icons.py` resolves assets through `sys._MEIPASS` when running from a bundled build, and through the project folder during development.
- `ZJX-LMS.spec`, `scripts/build_beta.ps1`, and `PACKAGING.md` define the repeatable Windows private-beta PyInstaller build path.

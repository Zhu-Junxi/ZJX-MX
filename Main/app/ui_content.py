"""Centralised copy and navigation metadata for static UI sections."""

SETTINGS_SECTIONS = [
    {
        "header": "Vault Storage",
        "description": "Where user profiles, Canvas data, and resources are stored.",
        "actions": [
            {
                "label": "Current Vault",
                "action": "current_vault",
                "icon": "vault",
                "subtitle": "View the active local storage folder",
                "meta": "Read-only path check",
            },
            {
                "label": "Change Vault Folder",
                "action": "change_vault",
                "icon": "settings",
                "subtitle": "Move the app to a different storage folder",
                "meta": "Choose a folder from your computer",
            },
            {
                "label": "Open Vault Folder",
                "action": "open_vault",
                "icon": "folder",
                "subtitle": "Open the vault in your system file explorer",
                "meta": "Useful for backups and inspection",
            },
            {
                "label": "Backup Vault Folder",
                "action": "backup_vault",
                "icon": "copy",
                "subtitle": "Copy the current vault to a timestamped backup folder",
                "meta": "Recommended before beta testing",
            },
            {
                "label": "Reset Vault Folder",
                "action": "reset_vault",
                "icon": "refresh",
                "subtitle": "Return storage to the default ZJX-LMS folder",
                "meta": "Default: ~/ZJX-LMS",
            },
        ],
    },
    {
        "header": "Appearance",
        "description": "Control theme, accent colour, and system theme behaviour.",
        "actions": [
            {
                "label": "Theme Mode",
                "action": "theme_mode",
                "icon": "moon",
                "subtitle": "Toggle between dark and light mode",
                "meta": "Quick toggle is also beside Help",
            },
            {
                "label": "Follow System Theme",
                "action": "follow_system_theme",
                "icon": "system",
                "subtitle": "Use your operating system dark/light preference",
                "meta": "Turn off to force a manual theme",
            },
            {
                "label": "Font Style",
                "action": "font_style",
                "icon": "edit",
                "subtitle": "Choose Default Font or Mono-spaced Font",
                "meta": "JetBrains Mono option",
            },
            {
                "label": "Accent Colour",
                "action": "accent_colour",
                "icon": "palette",
                "subtitle": "Choose the highlight colour used across the app",
                "meta": "Buttons, selected states, and badges",
            },
            {
                "label": "Reset Accent",
                "action": "reset_accent_colour",
                "icon": "refresh",
                "subtitle": "Restore the default blue accent",
                "meta": "Default: #2563eb",
            },
        ],
    },
    {
        "header": "Interface",
        "description": "Control layout, scrolling, and visibility preferences.",
        "actions": [
            {
                "label": "Adaptive / Resizable Layout",
                "action": "window_layout",
                "icon": "settings",
                "subtitle": "Screen-aware window and draggable middle panel",
                "meta": "Saved splitter position",
            },
            {
                "label": "Scroll Speed",
                "action": "scroll_speed",
                "icon": "settings",
                "subtitle": "Tune mouse wheel and trackpad scrolling",
                "meta": "Lower value = slower scrolling",
            },
            {
                "label": "UI Zoom",
                "action": "ui_zoom",
                "icon": "settings",
                "subtitle": "Scale text, rows, and controls across the app",
                "meta": "Ctrl + + / Ctrl + -",
            },
            {
                "label": "Smooth Scrolling",
                "action": "smooth_scroll",
                "icon": "settings",
                "subtitle": "Add gentle inertia after wheel input",
                "meta": "Momentum can be toggled on or off",
            },
            {
                "label": "Course Announcements Panel",
                "action": "course_announcements_panel",
                "icon": "announcement",
                "subtitle": "Completely show or hide announcements on the course dashboard",
                "meta": "Hidden frees up dashboard space",
            },
            {
                "label": "Due Countdown Precision",
                "action": "due_countdown_precision",
                "icon": "assignment",
                "subtitle": "Tune when due dates switch from days to hours, minutes, and seconds",
                "meta": "Default: 24h / 60m / 60s",
            },
            {
                "label": "Toggle Change History Panel",
                "action": "toggle_history_panel",
                "icon": "settings",
                "subtitle": "Show or hide the sidebar history card",
                "meta": "Undo/redo visibility",
            },
        ],
    },
    {
        "header": "Canvas Sync",
        "description": "Control what Canvas imports and how syncing behaves.",
        "actions": [
            {
                "label": "Auto Sync on Startup",
                "action": "canvas_auto_sync",
                "icon": "cloud",
                "subtitle": "Automatically sync the selected user when the app opens",
                "meta": "Default: off for faster startup",
            },
            {
                "label": "Canvas Course Blacklist",
                "action": "canvas_blacklist",
                "icon": "warning",
                "subtitle": "Skip old or irrelevant Canvas courses",
                "meta": "Blacklisted courses stay out of active sync",
            },
            {
                "label": "Favourite Canvas Courses",
                "action": "canvas_favourites",
                "icon": "course",
                "subtitle": "Pin key courses to the top of the Courses section",
                "meta": "Useful for current core subjects",
            },
            {
                "label": "Sync Details",
                "action": "canvas_sync_details",
                "icon": "canvas",
                "subtitle": "View sync state and preference counts",
                "meta": "Last sync, blacklist, favourites",
            },
        ],
    },
    {
        "header": "Notifications and Tray",
        "description": "Assignment reminders, background tray behaviour, and close-button handling.",
        "actions": [
            {
                "label": "Run on PC Startup",
                "action": "run_on_startup",
                "icon": "system",
                "subtitle": "Launch ZJX LMS automatically when you sign in",
                "meta": "OS startup registration",
            },
            {
                "label": "Startup Launch Mode",
                "action": "startup_launch_mode",
                "icon": "dashboard",
                "subtitle": "Choose tray background mode or open straight to Dashboard",
                "meta": "Only applies to automatic startup launches",
            },
            {
                "label": "Assignment Notifications",
                "action": "notifications_enabled",
                "icon": "announcement",
                "subtitle": "Native tray reminders for upcoming and overdue assignments",
                "meta": "Smart due-date thresholds",
            },
            {
                "label": "Minimize to Tray",
                "action": "tray_enabled",
                "icon": "system",
                "subtitle": "Keep ZJX LMS running in the system tray",
                "meta": "Required for background reminders",
            },
            {
                "label": "Close Button Behaviour",
                "action": "close_action",
                "icon": "settings",
                "subtitle": "Choose ask, minimize to tray, or quit",
                "meta": "First close asks by default",
            },
            {
                "label": "Reminder Schedule",
                "action": "reminder_schedule",
                "icon": "assignment",
                "subtitle": "Tune polling interval and reminder stages",
                "meta": "Default: 7d, 3d, 1d, 6h, 1h, overdue",
            },
            {
                "label": "Snooze Reminders",
                "action": "snooze_reminders",
                "icon": "moon",
                "subtitle": "Silence assignment reminders for one hour",
                "meta": "Temporary pause",
            },
        ],
    },

    {
        "header": "App Information",
        "description": "Version, release identity, and project metadata.",
        "actions": [
            {
                "label": "About ZJX LMS",
                "action": "app_info",
                "icon": "info",
                "subtitle": "View app name, version, and release details",
                "meta": "Release metadata",
            },
        ],
    },
    {
        "header": "Tools",
        "description": "Open supporting windows for managing the vault.",
        "actions": [
            {
                "label": "Open Resource Library",
                "action": "open_library",
                "icon": "library",
                "subtitle": "Browse resources across all users and courses",
                "meta": "Includes archived courses and assignments",
            },
            {
                "label": "Open Widgets Manager",
                "action": "open_widgets_manager",
                "icon": "dashboard",
                "subtitle": "Open the template-based desktop widgets window",
                "meta": "Countdowns, notes, and shortcut panels",
            },
            {
                "label": "Export Vault Archive",
                "action": "export_vault_archive",
                "icon": "vault",
                "subtitle": "Create a human-readable zip copy of your vault",
                "meta": "Portable archive",
            },
        ],
    },
]

HELP_TOPIC_ORDER = ["getting_started", "shortcuts", "files", "users", "canvas", "widgets"]

HELP_TOPICS = {
    "getting_started": {
        "title": "Getting Started",
        "subtitle": "A quick private-beta walkthrough for the first useful workflow.",
        "icon": "info",
        "list_subtitle": "Create user, sync Canvas, import resources, try widgets",
        "list_meta": "Recommended first stop",
        "cards": [
            {
                "kind": "tips",
                "title": "First Session",
                "tips": [
                    "Create a user profile from the first-run prompt or the Users section.",
                    "Add your Canvas URL and access token if you want live course, assignment, announcement, and profile picture sync.",
                    "Run Sync Canvas Data from the user detail page, Courses section, or user right-click menu.",
                    "Open Courses and Assignments to confirm imported data looks correct before adding resources.",
                ],
            },
            {
                "kind": "tips",
                "title": "Your Local Vault",
                "tips": [
                    "ZJX LMS stores users, Canvas metadata, profile picture cache, widget images, and imported resources in the local vault.",
                    "The default vault path is ~/ZJX-LMS, and it can be changed from Settings.",
                    "Canvas access tokens stay local in the user profile JSON inside the vault.",
                    "Use Settings > Backup Vault Folder before beta testing or before moving the app between machines.",
                ],
            },
            {
                "kind": "tips",
                "title": "Useful Features To Try",
                "tips": [
                    "Drag files or folders into Files to import managed copies into the current course or assignment scope.",
                    "Open Resource Library to browse resources across all users, courses, active assignments, and archived assignments.",
                    "Open Widgets Manager to create assignment countdowns, shortcut panels, and pinned notes.",
                    "Pinned note widgets support pasted images, which are cached locally under the vault.",
                ],
            },
        ],
    },
    "shortcuts": {
        "title": "Keyboard Shortcuts",
        "subtitle": "Fast actions for navigation and resource management.",
        "icon": "help",
        "list_subtitle": "Undo, redo, sidebar, file browser actions",
        "list_meta": "Ctrl+Shift+Z is the redo shortcut",
        "cards": [
            {
                "kind": "details",
                "title": "File Browser Shortcuts",
                "rows": [
                    "Ctrl + A: Select all resources",
                    "Ctrl + C: Copy selected resources",
                    "Ctrl + X: Cut selected resources",
                    "Ctrl + V: Paste copied/cut resources",
                    "Delete: Delete selected resources",
                    "F2: Rename or edit selected resource",
                    "F5: Refresh file explorer",
                    "Enter / Return: Open selected resource",
                ],
            },
            {
                "kind": "details",
                "title": "Global Shortcuts",
                "rows": [
                    "Ctrl + Z: Undo last resource change",
                    "Ctrl + Shift + Z: Redo last undone resource change",
                    "Ctrl + B: Collapse or expand sidebar",
                    "Ctrl + + / Ctrl + -: Increase or decrease UI zoom",
                ],
            },
        ],
    },
    "files": {
        "title": "File Browser Basics",
        "subtitle": "How to interact with resources inside the current scope.",
        "icon": "folder",
        "list_subtitle": "Preview, open, right-click, drag-and-drop",
        "list_meta": "Natural mode and grouped mode",
        "cards": [
            {
                "kind": "tips",
                "title": "Core Interactions",
                "tips": [
                    "Single click a file or resource to preview it and inspect its details.",
                    "Double click a file or resource to open it with the system default app.",
                    "Right click inside the file browser to create, import, rename, move, delete, or manage resources.",
                    "Drag local files or folders onto the app to import them into the selected user/course/scope.",
                ],
            },
            {
                "kind": "tips",
                "title": "Natural Browser Mode",
                "tips": [
                    "Folders appear as real folders instead of being forced into artificial type buckets.",
                    "Imported folder contents appear underneath the folder, so the tree behaves like a normal file browser.",
                    "Other resources sit beside folders at the same scope level.",
                ],
            },
            {
                "kind": "tips",
                "title": "Grouped Mode",
                "tips": [
                    "Use the View button in Files to switch between natural browsing and grouping by resource type.",
                    "Grouped mode is useful when you want to quickly find notes, links, videos, documents, or folders by category.",
                ],
            },
        ],
    },
    "users": {
        "title": "Users and Vault Structure",
        "subtitle": "How local profiles and storage scopes are organised.",
        "icon": "user",
        "list_subtitle": "UID based storage and scope hierarchy",
        "list_meta": "User → Course → Assignment / General",
        "cards": [
            {
                "kind": "tips",
                "title": "Users",
                "tips": [
                    "Each user receives a unique UID when created.",
                    "The UID is used as the folder name, so two people with the same display name can safely use the app.",
                    "Double click a user to select them and move directly into their Courses section.",
                    "Right click a user in the Users section to delete that user and their local vault data.",
                ],
            },
            {
                "kind": "tips",
                "title": "Scope Hierarchy",
                "tips": [
                    "Resources are stored under the selected User, then Course, then Assignment or General Course Resources.",
                    "This avoids a single messy folder where every file from every course is mixed together.",
                    "The Files page always shows the resources for the current scope only.",
                ],
            },
            {
                "kind": "tips",
                "title": "Canvas Token",
                "tips": [
                    "The Canvas access token is collected during onboarding and stored locally.",
                    "Right click a user, or use the user details buttons, to edit Canvas settings or run a Canvas sync.",
                ],
            },
        ],
    },
    "canvas": {
        "title": "Canvas Sync",
        "subtitle": "Import live Canvas course and assignment data into the local vault.",
        "icon": "canvas",
        "list_subtitle": "Courses, assignments, token, validation",
        "list_meta": "Manual sync, local storage",
        "cards": [
            {
                "kind": "tips",
                "title": "How Sync Works",
                "tips": [
                    "Each user stores their own Canvas URL and access token locally.",
                    "Sync imports active and completed Canvas courses first, except courses in the user's Canvas Course Blacklist.",
                    "Canvas courses marked completed, or with an end date in the past, are archived locally and hidden from the active Courses section.",
                    "Then it imports assignments and announcements for each imported course.",
                    "Canvas items use stable IDs such as canvas_12345, so re-syncing updates existing records instead of creating duplicates.",
                    "Canvas announcements are stored on each course and shown in the course dashboard.",
                    "Manual courses and assignments remain separate from Canvas-imported ones.",
                ],
            },
            {
                "kind": "tips",
                "title": "Before You Sync",
                "tips": [
                    "Open Users, select a user, then check that Canvas URL and token are saved in the Canvas Setup card.",
                    "Use Edit User / Canvas Settings if the token is missing or the Canvas URL is wrong.",
                    "Right click the user, open the Courses section, or use the user details card and choose Sync Canvas Data.",
                    "Use Canvas Course Blacklist before syncing if Canvas returns too many old course shells.",
                    "Use Favourite Canvas Courses to pin important current courses to the top.",
                ],
            },
            {
                "kind": "tips",
                "title": "Validation",
                "tips": [
                    "User names, course names, Canvas URLs, tokens, and due dates are validated before they are saved.",
                    "Due dates typed manually should be blank, YYYY-MM-DD, YYYY-MM-DD HH:MM, or Canvas ISO datetime.",
                    "Assignments stay active by default when overdue; ZJX LMS asks before moving them into Archived Assignments.",
                    "The Resource Library now has Expand All, Collapse All, Archived Courses, and Archived Assignments filters for faster review.",
                    "Auto sync can be enabled in Settings → Canvas Sync, but it is off by default to keep startup fast.",
                    "Canvas tokens must not contain spaces or new lines.",
                ],
            },
        ],
    },
    "widgets": {
        "title": "Widget Editor",
        "subtitle": "Create small desktop widgets for assignments, notes, and shortcuts.",
        "icon": "dashboard",
        "list_subtitle": "Countdowns, notes, shortcuts, tray behaviour",
        "list_meta": "Opens as a separate window",
        "cards": [
            {
                "kind": "tips",
                "title": "Opening and Managing Widgets",
                "tips": [
                    "Open Settings, choose Open Widgets Manager, or use the Widgets button in the sidebar.",
                    "The widget editor opens as a separate window so you can keep it beside the main app.",
                    "Use Add Widget to create an assignment countdown, shortcut panel, or pinned note.",
                    "Use Duplicate, Rename, Delete, or the right click menu to manage selected widgets.",
                ],
            },
            {
                "kind": "tips",
                "title": "Enabling Widgets",
                "tips": [
                    "The widget browser on the left shows each widget with an ON or OFF indicator.",
                    "Click a widget row to edit it, or click its ON/OFF pill to show or hide the desktop widget.",
                    "You can also right click a widget and choose Enable Widget or Disable Widget.",
                    "Enabled widgets stay available while the app process is running, including when the main window is hidden in the tray.",
                ],
            },
            {
                "kind": "tips",
                "title": "Editing a Widget",
                "tips": [
                    "Use the right panel to change the widget name, position, size, theme mode, display mode, opacity, and lock state.",
                    "Assignment countdown widgets can be linked to any saved assignment and can show or hide the assignment title, course label, and due label.",
                    "Shortcut panels can open app sections, users, courses, assignments, files, folders, or URLs.",
                    "Note widgets can store a pinned note, and inline editing can be enabled when you want to edit directly from the desktop widget.",
                    "Changes save live and the preview in the centre updates as you edit.",
                ],
            },
        ],
    },

}

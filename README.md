# ZJX LMS

<p align="center">
  <img width="128" alt="ZJX LMS app icon" src="https://github.com/user-attachments/assets/47e402cd-b199-4f24-9b60-966f2351a6b6" />
</p>

<p align="center">
  <strong>A local-first PySide6 desktop companion for Canvas courses, assignments, resources, notes, and study widgets.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="PySide6" src="https://img.shields.io/badge/UI-PySide6-41CD52">
  <img alt="Canvas" src="https://img.shields.io/badge/Canvas-sync-E72429">
  <img alt="Local first" src="https://img.shields.io/badge/storage-local--first-2563EB">
  <img alt="Status" src="https://img.shields.io/badge/status-1.0.0--beta1-F59E0B">
</p>

---

## Overview

**ZJX LMS** is a desktop learning manager built for students and private beta testers who want Canvas data, course resources, assignment notes, and reminder widgets in one local workspace.

The app stores user profiles, courses, assignments, announcements, resources, desktop widgets, cached Canvas profile pictures, and pasted note-widget images in a local vault. Canvas access tokens remain on the user's machine inside the local user profile JSON.

---

## Preview

> Screenshots are not currently checked into this repository. The image links below are ready for future GitHub screenshots and should be added under `docs/images/`.

<img width="2560" height="1380" alt="Image" src="https://github.com/user-attachments/assets/b46e8afb-848a-499e-90a3-fcac6aadcaae" />

<img width="2560" height="1378" alt="Image" src="https://github.com/user-attachments/assets/4ceff306-5bd1-4eea-8463-08502a297908" />

<img width="2560" height="1380" alt="Image" src="https://github.com/user-attachments/assets/bf9bea9f-2681-48d4-9368-e27effe940e6" />

<img width="2560" height="1385" alt="Image" src="https://github.com/user-attachments/assets/c54ba889-9d8f-4750-af92-b10af88af56c" />

<img width="2560" height="1399" alt="Image" src="https://github.com/user-attachments/assets/7311dc73-5d4f-40aa-abe8-1412c1a14c51" />

---

## Features

### Canvas Learning Workflow

- Sync Canvas courses, assignments, announcements, and user profile pictures.
- Pin favourite Canvas courses and skip courses that should stay out of the active workspace.
- Keep Canvas-imported records stable across re-syncs instead of duplicating existing courses or assignments.
- Open Canvas-linked assignment and course resources from inside the app.

### Local Vault And Resources

- Store users, courses, assignments, files, notes, folders, links, widgets, and cached images in a local vault.
- Organize resources by user, course, assignment, and general course context.
- Import, copy, move, rename, delete, edit, preview, archive, and restore resources.
- Browse resources through the main file explorer and the global Resource Library.
- Export a human-readable zip archive of selected users, courses, assignments, files, notes, folders, and links.

### Dashboards And Assignment Tracking

- View upcoming assignments and course-focused study information.
- Mark assignments as finished and keep archived work accessible.
- Use due-date urgency colours and dashboard sorting to keep deadlines visible.
- Work with both Canvas-imported and manually created courses or assignments.

### Desktop Widgets

- Create assignment countdown widgets.
- Create shortcut panels for quick access.
- Create pinned note widgets with pasted image support.
- Keep widget data and pasted images stored locally in the vault.

### Personalization And Desktop Integration

- Switch between dark, light, and system-following theme modes.
- Adjust accent colour, UI zoom, font style, scroll speed, and assignment reminder behaviour.
- Use platform-aware startup registration on Windows, Linux desktop sessions, and macOS.
- Minimize to tray when the current desktop session exposes tray/status notifier support.

---

## Requirements

- Python 3.10 or newer.
- A desktop environment that can run Qt/PySide6 applications.
- Optional Canvas account access for sync features.

Runtime dependencies are listed in `requirements.txt`:

- `PySide6`
- `requests`
- `python-docx`
- `python-pptx`
- `openpyxl`

---

## Run From Source

From this `Main` directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

On macOS or Linux, use the equivalent shell activation command for your environment, then run `python main.py`.

---

## Canvas Setup

Canvas sync requires:

- Your Canvas base URL, such as `https://canvas.example.edu`.
- A Canvas access token for the account you want to sync.

The app stores the Canvas base URL and access token locally in the user's profile JSON. Tokens are not sent to a third-party backend by ZJX LMS. Treat the local vault as private user data and avoid committing vault contents to source control.

---

## Local Data

By default, ZJX LMS creates its vault at:

```text
~/ZJX-LMS
```

The vault can contain:

- User profiles and Canvas access tokens.
- Canvas course, assignment, announcement, and profile picture metadata.
- Imported files, notes, folders, links, and resource metadata.
- Desktop widget definitions.
- Cached Canvas profile pictures.
- Pasted note-widget images.

Use **Settings > Backup Vault Folder** before beta testing, moving machines, or experimenting with real Canvas data. Use **Settings > Tools > Export Vault Archive** when you need a portable, human-readable copy of selected vault content.

---

## Packaging

Windows private beta packaging uses PyInstaller. Runtime source support also covers Linux desktop sessions and macOS, but packaged builds should be produced and smoke-tested on their target operating systems.

See [PACKAGING.md](PACKAGING.md) for the full packaging checklist.

Quick Windows beta build:

```powershell
pip install -r requirements-build.txt
.\scripts\build_beta.ps1
```

Default output:

```text
release\ZJX-LMS-1.0.0-beta1-win64\
release\ZJX-LMS-1.0.0-beta1-win64.zip
```

---

## Architecture

The project is split into small layers so UI, storage, Canvas access, and reusable services stay separated.

- `app/` owns the main window, dashboard views, settings views, app actions, resource actions, Canvas actions, styles, and desktop integration.
- `core/` owns models, validation, vault storage, file operations, URL shortcuts, and UI-neutral helpers.
- `services/` owns Canvas HTTP access, command history, file preview, assignment reminders, Microsoft/Google document helpers, vault export, and logging.
- `ui/` owns reusable PySide6 widgets, dialogs, context menus, icons, drag/drop support, and themed forms.
- `tests/` contains focused unit tests for vault behaviour, dashboard logic, drag/drop, platform compatibility, startup, widgets, export, and settings.

Useful references:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [FILE_BACKEND.md](FILE_BACKEND.md)
- [PACKAGING.md](PACKAGING.md)
- [RELEASE_NOTES.md](RELEASE_NOTES.md)

---

## Privacy And Safety

ZJX LMS is local-first: the app's primary storage is the user's vault on their own machine. Canvas tokens, synced metadata, imported resources, notes, widgets, and cached images should be treated as private user data.

Private beta testers should back up their vault before heavy testing, destructive resource operations, machine migration, or experiments with real Canvas accounts.

---

## Project Status

Current release: **1.0.0-beta1**

This project is in private beta. Core local vault, Canvas sync, resource management, desktop widgets, theme settings, backup, export, and Windows beta packaging workflows are present, but tester feedback and platform-specific smoke checks are still expected.

---

## MIT License

Copyright 2026 ©️ZJX

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACT

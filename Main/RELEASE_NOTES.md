# ZJX LMS 1.0.0 Beta 1 Release Notes

## Private Beta Highlights

- Local-first vault for users, Canvas data, assignments, resources, and widgets.
- Canvas sync for courses, assignments, announcements, and user profile pictures.
- Canvas course skip and pin preferences.
- Resource Library refresh with cleaner vault/preview panels and archived assignment browsing.
- Desktop Widgets Manager for assignment countdowns, shortcut panels, and pinned notes.
- Note widgets support pasted images, cached locally in the vault.
- Backup Vault action in Settings for beta safety.
- Export Vault Archive action in Settings > Tools for creating human-readable portable zip archives.
- Dark/light theme support, accent colour controls, UI zoom, scroll tuning, tray behaviour, and assignment reminders.

## Packaging

- Windows private beta packaging is now repeatable through PyInstaller.
- Build files:
  - `ZJX-LMS.spec`
  - `scripts/build_beta.ps1`
  - `requirements-build.txt`
  - `PACKAGING.md`
- Default output is `release/ZJX-LMS-1.0.0-beta1-win64.zip`.

## Beta Testing Checklist

- Launch fresh and complete onboarding.
- Sync one Canvas user with a profile picture and one without a profile picture.
- Browse Courses, Assignments, Files, and Resource Library.
- Create a note widget, paste an image, restart the app, and confirm the image persists.
- Use Settings > Backup Vault Folder and confirm the backup contains local users, resources, widgets, and cached images.
- Use Settings > Tools > Export Vault Archive and confirm the zip contains readable user, course, assignment, file, note, folder, and link names.
- Launch once while offline after a previous successful sync.

## Local Data

By default, ZJX LMS stores data under:

```text
~/ZJX-LMS
```

The vault includes Canvas tokens, cached profile pictures, imported files, widget definitions, and pasted note-widget images. Treat beta vaults as real local user data and back them up before destructive testing. Use Export Vault Archive when testers need a portable, human-readable copy of their stored resources.

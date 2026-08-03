import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.file_operations import remove_path
from core.helpers import now_iso, slugify, safe_read_json, safe_write_json, unique_path
from core.url_shortcuts import LINK_RESOURCE_TYPES, read_url_shortcut, shortcut_filename, write_url_shortcut
from core.validation import validate_user_payload, validate_course_payload, validate_assignment_payload


class VaultManager:
    """Pure storage/metadata layer. This module intentionally contains no UI code."""

    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.users_dir = self.root_path / "users"

        self.root_path.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)

        self.ensure_defaults()

    # -----------------------------
    # Core paths
    # -----------------------------

    def users_index_path(self):
        return self.root_path / "users.json"

    def widgets_json_path(self):
        return self.root_path / "widgets.json"

    def user_dir(self, user_id):
        return self.users_dir / user_id

    def user_profile_path(self, user_id):
        return self.user_dir(user_id) / "profile.json"

    def user_canvas_avatar_path(self, user_id):
        return self.user_dir(user_id) / "canvas_avatar"

    def courses_dir(self, user_id):
        return self.user_dir(user_id) / "courses"

    def course_dir(self, user_id, course_id):
        return self.courses_dir(user_id) / course_id

    def course_json_path(self, user_id, course_id):
        return self.course_dir(user_id, course_id) / "course.json"

    def assignments_dir(self, user_id, course_id):
        return self.course_dir(user_id, course_id) / "assignments"

    def assignment_dir(self, user_id, course_id, assignment_id):
        return self.assignments_dir(user_id, course_id) / assignment_id

    def assignment_json_path(self, user_id, course_id, assignment_id):
        return self.assignment_dir(user_id, course_id, assignment_id) / "assignment.json"

    def general_dir(self, user_id, course_id):
        return self.course_dir(user_id, course_id) / "general"

    def context_dir(self, user_id, course_id, assignment_id=None):
        if assignment_id:
            return self.assignment_dir(user_id, course_id, assignment_id)
        return self.general_dir(user_id, course_id)

    def resources_json_path(self, user_id, course_id, assignment_id=None):
        return self.context_dir(user_id, course_id, assignment_id) / "resources.json"

    def context_files_dir(self, user_id, course_id, assignment_id=None):
        return self.context_dir(user_id, course_id, assignment_id) / "files"

    def context_folders_dir(self, user_id, course_id, assignment_id=None):
        return self.context_dir(user_id, course_id, assignment_id) / "folders"

    def context_notes_dir(self, user_id, course_id, assignment_id=None):
        return self.context_dir(user_id, course_id, assignment_id) / "notes"

    def ensure_context_dirs(self, user_id, course_id, assignment_id=None):
        context = self.context_dir(user_id, course_id, assignment_id)

        for folder in ["files", "folders", "notes"]:
            (context / folder).mkdir(parents=True, exist_ok=True)

        resource_path = self.resources_json_path(user_id, course_id, assignment_id)
        if not resource_path.exists():
            safe_write_json(resource_path, {"resources": []})

    # -----------------------------
    # Default data
    # -----------------------------

    def ensure_defaults(self):
        """Create the vault index without adding sample users or courses.

        Real user data is now collected by the onboarding flow. Keeping the
        default vault empty prevents demo data from being mistaken for the
        user's actual course structure.
        """
        if self.users_index_path().exists():
            if not self.widgets_json_path().exists():
                safe_write_json(self.widgets_json_path(), {"widgets": []})
            return

        safe_write_json(self.users_index_path(), {"users": []})
        if not self.widgets_json_path().exists():
            safe_write_json(self.widgets_json_path(), {"widgets": []})

    # -----------------------------
    # Users
    # -----------------------------

    def normalise_user(self, user):
        """Return a profile with all fields expected by the current app build."""
        user = dict(user or {})
        user_id = user.get("id") or user.get("uid")
        user["id"] = user_id
        user["uid"] = user.get("uid") or user_id
        user["name"] = user.get("name") or "Unnamed User"
        user["university"] = user.get("university") or ""
        user["canvas_base_url"] = user.get("canvas_base_url") or "https://canvas.sydney.edu.au"
        user["canvas_access_token"] = user.get("canvas_access_token") or ""
        user["canvas_user_id"] = str(user.get("canvas_user_id") or "")
        user["canvas_avatar_url"] = user.get("canvas_avatar_url") or ""
        user["canvas_avatar_path"] = user.get("canvas_avatar_path") or ""
        user["canvas_blacklisted_course_ids"] = [str(item) for item in user.get("canvas_blacklisted_course_ids", [])]
        user["canvas_favourite_course_ids"] = [str(item) for item in user.get("canvas_favourite_course_ids", [])]
        user["created_at"] = user.get("created_at") or now_iso()
        return user

    def get_users(self):
        data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in data.get("users", []) if user.get("id") or user.get("uid")]
        return users

    def get_user(self, user_id):
        for user in self.get_users():
            if user["id"] == user_id:
                return user
        return None

    def create_user_structure(self, user):
        self.user_dir(user["id"]).mkdir(parents=True, exist_ok=True)

        profile_path = self.user_profile_path(user["id"])
        safe_write_json(profile_path, user)

        self.courses_dir(user["id"]).mkdir(parents=True, exist_ok=True)

    def make_user_id(self, existing_ids=None):
        existing_ids = existing_ids or set()

        while True:
            user_id = f"usr_{uuid.uuid4().hex}"
            if user_id not in existing_ids and not self.user_dir(user_id).exists():
                return user_id

    def add_user(self, name, university="", canvas_access_token="", canvas_base_url="https://canvas.sydney.edu.au"):
        payload = validate_user_payload({
            "name": name,
            "university": university,
            "canvas_access_token": canvas_access_token,
            "canvas_base_url": canvas_base_url,
        })

        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in users_data.get("users", [])]

        existing_ids = {user["id"] for user in users}
        user_id = self.make_user_id(existing_ids)

        user = {
            "id": user_id,
            "uid": user_id,
            "name": payload["name"],
            "university": payload["university"],
            "canvas_base_url": payload["canvas_base_url"],
            "canvas_access_token": payload["canvas_access_token"],
            "canvas_last_sync_at": "",
            "canvas_last_sync_result": "Never synced",
            "canvas_user_id": "",
            "canvas_avatar_url": "",
            "canvas_avatar_path": "",
            "canvas_blacklisted_course_ids": [],
            "canvas_favourite_course_ids": [],
            "created_at": now_iso(),
        }

        users.append(user)
        users_data["users"] = users

        safe_write_json(self.users_index_path(), users_data)
        self.create_user_structure(user)
        return user

    def update_user(self, user_id, **fields):
        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in users_data.get("users", [])]

        for index, user in enumerate(users):
            if user.get("id") != user_id:
                continue

            updated = dict(user)
            updated.update(fields)
            payload = validate_user_payload(updated)
            updated.update(payload)
            updated["updated_at"] = now_iso()
            users[index] = updated

            users_data["users"] = users
            safe_write_json(self.users_index_path(), users_data)
            self.create_user_structure(updated)
            return updated

        return None

    def update_user_canvas_course_preferences(self, user_id, blacklisted_course_ids=None, favourite_course_ids=None):
        """Persist Canvas course sync preferences on the user profile."""
        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in users_data.get("users", [])]

        for index, user in enumerate(users):
            if user.get("id") != user_id:
                continue

            if blacklisted_course_ids is not None:
                user["canvas_blacklisted_course_ids"] = sorted({str(item) for item in blacklisted_course_ids if str(item).strip()})

                # A course should not be both favourite and blacklisted.
                blacklisted = set(user["canvas_blacklisted_course_ids"])
                user["canvas_favourite_course_ids"] = [
                    item for item in user.get("canvas_favourite_course_ids", [])
                    if item not in blacklisted
                ]

            if favourite_course_ids is not None:
                blacklisted = set(user.get("canvas_blacklisted_course_ids", []))
                user["canvas_favourite_course_ids"] = sorted({
                    str(item) for item in favourite_course_ids
                    if str(item).strip() and str(item) not in blacklisted
                })

            user["updated_at"] = now_iso()
            users[index] = user
            users_data["users"] = users
            safe_write_json(self.users_index_path(), users_data)
            self.create_user_structure(user)
            return user

        return None

    def update_user_canvas_profile(self, user_id, profile=None, avatar_bytes=None):
        profile = profile or {}
        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in users_data.get("users", [])]

        avatar_url = (
            profile.get("avatar_url")
            or profile.get("profile_pic_url")
            or profile.get("picture")
            or ""
        )

        for index, user in enumerate(users):
            if user.get("id") != user_id:
                continue

            user["canvas_user_id"] = str(profile.get("id") or user.get("canvas_user_id") or "")
            user["canvas_avatar_url"] = str(avatar_url or "")

            avatar_path = self.user_canvas_avatar_path(user_id)
            if avatar_bytes and avatar_url:
                self.user_dir(user_id).mkdir(parents=True, exist_ok=True)
                avatar_path.write_bytes(avatar_bytes)
                user["canvas_avatar_path"] = str(avatar_path)
                user["canvas_avatar_cached_at"] = now_iso()
            elif not avatar_url:
                if avatar_path.exists():
                    remove_path(avatar_path)
                user["canvas_avatar_path"] = ""
                user["canvas_avatar_cached_at"] = ""

            user["updated_at"] = now_iso()
            users[index] = user
            users_data["users"] = users
            safe_write_json(self.users_index_path(), users_data)
            self.create_user_structure(user)
            return user

        return None

    def update_user_canvas_sync_status(self, user_id, summary):
        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = [self.normalise_user(user) for user in users_data.get("users", [])]

        for index, user in enumerate(users):
            if user.get("id") == user_id:
                user["canvas_last_sync_at"] = now_iso()
                user["canvas_last_sync_result"] = summary
                users[index] = user
                users_data["users"] = users
                safe_write_json(self.users_index_path(), users_data)
                self.create_user_structure(user)
                return user

        return None

    def delete_user(self, user_id):
        """Delete one user profile and its UID-based vault folder."""
        users_data = safe_read_json(self.users_index_path(), {"users": []})
        users = users_data.get("users", [])
        remaining_users = [user for user in users if user.get("id") != user_id]

        if len(remaining_users) == len(users):
            return False

        users_data["users"] = remaining_users
        safe_write_json(self.users_index_path(), users_data)

        user_path = self.user_dir(user_id)

        if user_path.exists():
            try:
                user_path.resolve().relative_to(self.users_dir.resolve())
            except ValueError:
                return False

            remove_path(user_path)

        return True

    # -----------------------------
    # Courses
    # -----------------------------

    def add_course(self, user_id, code, name):
        payload = validate_course_payload(code, name)
        course_parent = self.courses_dir(user_id)
        course_parent.mkdir(parents=True, exist_ok=True)

        base_id = slugify(f"{payload['code']}_{payload['name']}")
        course_id = base_id
        counter = 2

        while (course_parent / course_id).exists():
            course_id = f"{base_id}_{counter}"
            counter += 1

        course = {
            "id": course_id,
            "code": payload["code"],
            "name": payload["name"],
            "source": "manual",
            "archived": False,
            "archived_at": "",
            "archived_source": "",
            "created_at": now_iso(),
        }

        self.course_dir(user_id, course_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(self.course_json_path(user_id, course_id), course)

        self.assignments_dir(user_id, course_id).mkdir(parents=True, exist_ok=True)
        self.ensure_context_dirs(user_id, course_id, assignment_id=None)
        return course

    @staticmethod
    def canvas_course_is_finished(canvas_course):
        workflow_state = str((canvas_course or {}).get("workflow_state") or "").strip().lower()
        if workflow_state == "completed":
            return True

        end_at = (canvas_course or {}).get("end_at")
        if not end_at:
            return False

        try:
            end_date = datetime.fromisoformat(str(end_at).replace("Z", "+00:00"))
        except ValueError:
            return False

        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) > end_date.astimezone(timezone.utc)

    def add_or_update_canvas_course(self, user_id, canvas_course):
        canvas_id = str(canvas_course.get("id", "")).strip()
        if not canvas_id:
            return None, False

        course_id = f"canvas_{canvas_id}"
        existing = self.get_course(user_id, course_id) or {}
        synced_at = now_iso()
        canvas_finished = self.canvas_course_is_finished(canvas_course)
        existing_archived = bool(existing.get("archived"))
        archived_source = existing.get("archived_source") or ""

        if canvas_finished:
            archived = True
            archived_at = existing.get("archived_at") or synced_at
            archived_source = archived_source or "canvas"
        elif existing_archived and archived_source == "canvas":
            archived = False
            archived_at = ""
            archived_source = ""
        else:
            archived = existing_archived
            archived_at = existing.get("archived_at") or ""

        course_code = (
            canvas_course.get("course_code")
            or canvas_course.get("sis_course_id")
            or canvas_course.get("name")
            or f"Canvas {canvas_id}"
        )
        course_name = canvas_course.get("name") or course_code

        course = {
            **existing,
            "id": course_id,
            "code": str(course_code).strip(),
            "name": str(course_name).strip(),
            "source": "canvas",
            "canvas_id": canvas_id,
            "canvas_uuid": canvas_course.get("uuid", ""),
            "canvas_workflow_state": canvas_course.get("workflow_state", ""),
            "canvas_start_at": canvas_course.get("start_at") or "",
            "canvas_end_at": canvas_course.get("end_at") or "",
            "canvas_finished": canvas_finished,
            "canvas_enrollment_term_id": str(canvas_course.get("enrollment_term_id", "")),
            "canvas_synced_at": synced_at,
            "archived": archived,
            "archived_at": archived_at,
            "archived_source": archived_source,
            "created_at": existing.get("created_at") or synced_at,
            "updated_at": synced_at,
        }

        self.course_dir(user_id, course_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(self.course_json_path(user_id, course_id), course)
        self.assignments_dir(user_id, course_id).mkdir(parents=True, exist_ok=True)
        self.ensure_context_dirs(user_id, course_id, assignment_id=None)
        return course, not bool(existing)


    def delete_course(self, user_id, course_id):
        """Delete a course directory and everything inside it."""
        course_path = self.course_dir(user_id, course_id)

        if not course_path.exists():
            return False

        try:
            course_path.resolve().relative_to(self.root_path.resolve())
        except ValueError:
            return False

        remove_path(course_path)
        return True

    def get_courses(self, user_id):
        courses = []
        course_parent = self.courses_dir(user_id)

        if not course_parent.exists():
            return courses

        for folder in sorted(course_parent.iterdir()):
            if not folder.is_dir():
                continue

            course = safe_read_json(folder / "course.json", None)
            if course:
                courses.append(course)

        return courses

    def get_course(self, user_id, course_id):
        if not user_id or not course_id:
            return None
        return safe_read_json(self.course_json_path(user_id, course_id), None)

    def save_course(self, user_id, course):
        """Persist a course metadata dictionary back to course.json."""
        if not user_id or not course or not course.get("id"):
            return None

        course["updated_at"] = now_iso()
        safe_write_json(self.course_json_path(user_id, course["id"]), course)
        return course

    def update_course_fields(self, user_id, course_id, **fields):
        """Update selected fields on a course and return the saved object."""
        course = self.get_course(user_id, course_id)
        if not course:
            return None

        course.update(fields)
        return self.save_course(user_id, course)

    def add_or_update_canvas_announcements(self, user_id, course_id, canvas_announcements):
        """Save Canvas announcements on the course metadata object.

        Announcements are course-level metadata, not user resources, so they live
        inside course.json and are displayed by the course dashboard.
        """
        course = self.get_course(user_id, course_id)
        if not course:
            return 0

        existing_by_id = {
            str(item.get("canvas_id") or item.get("id")): item
            for item in course.get("announcements", [])
            if item.get("canvas_id") or item.get("id")
        }

        announcements = []
        for item in canvas_announcements or []:
            item_id = str(item.get("canvas_id") or item.get("id") or "").strip()
            if not item_id:
                continue
            merged = {**existing_by_id.get(item_id, {}), **item}
            merged["synced_at"] = now_iso()
            announcements.append(merged)

        announcements.sort(key=lambda item: item.get("date") or "", reverse=True)
        course["announcements"] = announcements
        course["canvas_announcements_synced_at"] = now_iso()
        self.save_course(user_id, course)
        return len(announcements)

    # -----------------------------
    # Assignments
    # -----------------------------

    def add_assignment(self, user_id, course_id, title, due_date="", status="Not started"):
        payload = validate_assignment_payload(title, due_date, status)
        assignment_parent = self.assignments_dir(user_id, course_id)
        assignment_parent.mkdir(parents=True, exist_ok=True)

        base_id = slugify(payload["title"])
        assignment_id = base_id
        counter = 2

        while (assignment_parent / assignment_id).exists():
            assignment_id = f"{base_id}_{counter}"
            counter += 1

        assignment = {
            "id": assignment_id,
            "title": payload["title"],
            "due_date": payload["due_date"],
            "status": payload["status"],
            "completed": False,
            "completed_at": "",
            "source": "manual",
            "created_at": now_iso(),
        }

        self.assignment_dir(user_id, course_id, assignment_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(self.assignment_json_path(user_id, course_id, assignment_id), assignment)
        self.ensure_context_dirs(user_id, course_id, assignment_id)
        return assignment

    def add_or_update_canvas_assignment(self, user_id, course_id, canvas_assignment):
        canvas_id = str(canvas_assignment.get("id", "")).strip()
        if not canvas_id:
            return None, False

        assignment_id = f"canvas_{canvas_id}"
        existing = self.get_assignment(user_id, course_id, assignment_id) or {}
        due_at = canvas_assignment.get("due_at") or ""
        due_date = due_at[:10] if due_at else ""
        due_date_overridden = bool(existing.get("due_date_overridden_by_user"))
        stored_due_at = existing.get("canvas_due_at", "") if due_date_overridden else due_at
        stored_due_date = existing.get("due_date", "") if due_date_overridden else due_date
        completed = bool(existing.get("completed", False))

        assignment = {
            **existing,
            "id": assignment_id,
            "title": str(canvas_assignment.get("name") or f"Canvas Assignment {canvas_id}").strip(),
            "due_date": stored_due_date,
            "status": "Completed" if completed else (existing.get("status") or "Not started"),
            "completed": completed,
            "completed_at": existing.get("completed_at") if completed else "",
            "source": "canvas",
            "canvas_id": canvas_id,
            "canvas_due_at": stored_due_at,
            "canvas_unlock_at": canvas_assignment.get("unlock_at") or "",
            "canvas_lock_at": canvas_assignment.get("lock_at") or "",
            "canvas_points_possible": canvas_assignment.get("points_possible"),
            "canvas_html_url": canvas_assignment.get("html_url") or "",
            "canvas_synced_at": now_iso(),
            "created_at": existing.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }

        self.assignment_dir(user_id, course_id, assignment_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(self.assignment_json_path(user_id, course_id, assignment_id), assignment)
        self.ensure_context_dirs(user_id, course_id, assignment_id)
        return assignment, not bool(existing)


    def delete_assignment(self, user_id, course_id, assignment_id):
        """Delete an assignment directory and all resources attached to it."""
        assignment_path = self.assignment_dir(user_id, course_id, assignment_id)

        if not assignment_path.exists():
            return False

        try:
            assignment_path.resolve().relative_to(self.root_path.resolve())
        except ValueError:
            return False

        remove_path(assignment_path)
        return True

    def get_assignments(self, user_id, course_id):
        assignments = []
        assignment_parent = self.assignments_dir(user_id, course_id)

        if not assignment_parent.exists():
            return assignments

        for folder in sorted(assignment_parent.iterdir()):
            if not folder.is_dir():
                continue

            assignment = safe_read_json(folder / "assignment.json", None)
            if assignment:
                assignments.append(assignment)

        return assignments

    def get_assignment(self, user_id, course_id, assignment_id):
        if not user_id or not course_id or not assignment_id:
            return None

        return safe_read_json(self.assignment_json_path(user_id, course_id, assignment_id), None)

    def save_assignment(self, user_id, course_id, assignment):
        """Persist an assignment metadata dictionary back to assignment.json."""
        if not user_id or not course_id or not assignment or not assignment.get("id"):
            return None

        assignment["updated_at"] = now_iso()
        safe_write_json(
            self.assignment_json_path(user_id, course_id, assignment["id"]),
            assignment,
        )
        return assignment

    def update_assignment_fields(self, user_id, course_id, assignment_id, **fields):
        """Update selected fields on an assignment and return the saved object."""
        assignment = self.get_assignment(user_id, course_id, assignment_id)
        if not assignment:
            return None

        assignment.update(fields)
        return self.save_assignment(user_id, course_id, assignment)

    # -----------------------------
    # Desktop widgets
    # -----------------------------

    def load_desktop_widgets(self):
        data = safe_read_json(self.widgets_json_path(), {"widgets": []})
        widgets = data.get("widgets", [])
        return widgets if isinstance(widgets, list) else []

    def save_desktop_widgets(self, widgets):
        safe_write_json(self.widgets_json_path(), {"widgets": list(widgets or [])})

    # -----------------------------
    # Resources
    # -----------------------------

    def load_resources(self, user_id, course_id, assignment_id=None):
        self.ensure_context_dirs(user_id, course_id, assignment_id)
        data = safe_read_json(self.resources_json_path(user_id, course_id, assignment_id), {"resources": []})
        return data.get("resources", [])

    def save_resources(self, user_id, course_id, assignment_id, resources):
        self.ensure_context_dirs(user_id, course_id, assignment_id)
        safe_write_json(self.resources_json_path(user_id, course_id, assignment_id), {"resources": resources})

    def sync_context_resource_metadata(self, user_id, course_id, assignment_id=None):
        """Reconcile local file/folder metadata with the current context folders.

        This is intentionally conservative: it only auto-registers direct
        children of the top-level ``files`` and ``folders`` directories, while
        removing stale local_file/local_folder entries whose physical targets no
        longer exist anywhere in the context.
        """
        self.ensure_context_dirs(user_id, course_id, assignment_id)
        resources = list(self.load_resources(user_id, course_id, assignment_id))
        context_dir = self.context_dir(user_id, course_id, assignment_id)
        files_dir = self.context_files_dir(user_id, course_id, assignment_id)
        folders_dir = self.context_folders_dir(user_id, course_id, assignment_id)

        changed = False
        kept_resources = []
        tracked_paths = set()

        for resource in resources:
            resource_type = resource.get("type")
            if resource_type in LINK_RESOURCE_TYPES and not resource.get("path") and resource.get("url"):
                destination_parent = files_dir
                container_path = resource.get("container_path")
                if container_path:
                    candidate_parent = context_dir / container_path
                    if candidate_parent.exists() and candidate_parent.is_dir():
                        destination_parent = candidate_parent

                destination = unique_path(destination_parent, shortcut_filename(resource.get("title") or "Link"))
                write_url_shortcut(
                    destination,
                    resource.get("url", ""),
                    title=resource.get("title", "Link"),
                    resource_type=resource_type,
                    tags=resource.get("tags", []),
                )
                resource = dict(resource)
                resource["path"] = str(destination.relative_to(context_dir))
                resource.pop("container_path", None)
                resource["updated_at"] = now_iso()
                tracked_paths.add(resource["path"])
                kept_resources.append(resource)
                changed = True
                continue

            if resource_type in LINK_RESOURCE_TYPES and resource.get("path"):
                path = self.resource_absolute_path(resource)
                shortcut = read_url_shortcut(path) if path and path.exists() else None
                if not path or not path.exists() or not shortcut:
                    changed = True
                    continue

                try:
                    relative = str(path.relative_to(context_dir))
                except ValueError:
                    changed = True
                    continue

                updated = dict(resource)
                if updated.get("url") != shortcut["url"]:
                    updated["url"] = shortcut["url"]
                    changed = True
                if updated.get("type") != shortcut["type"]:
                    updated["type"] = shortcut["type"]
                    changed = True
                tracked_paths.add(relative)
                kept_resources.append(updated)
                continue

            if resource_type not in {"local_file", "local_folder"}:
                kept_resources.append(resource)
                continue

            path = self.resource_absolute_path(resource)
            if not path or not path.exists():
                changed = True
                continue

            try:
                relative = str(path.relative_to(context_dir))
            except ValueError:
                changed = True
                continue

            expected_type = "local_folder" if path.is_dir() else "local_file"
            if resource_type != expected_type:
                resource = dict(resource)
                resource["type"] = expected_type
                resource["updated_at"] = now_iso()
                changed = True

            tracked_paths.add(relative)
            kept_resources.append(resource)

        discovered = []

        for root_dir, resource_type in ((files_dir, "local_file"), (folders_dir, "local_folder")):
            try:
                entries = sorted(root_dir.iterdir(), key=lambda item: item.name.lower())
            except FileNotFoundError:
                entries = []

            for entry in entries:
                if resource_type == "local_file" and not entry.is_file():
                    continue
                if resource_type == "local_folder" and not entry.is_dir():
                    continue

                relative = str(entry.relative_to(context_dir))
                if relative in tracked_paths:
                    continue

                shortcut = read_url_shortcut(entry) if resource_type == "local_file" else None
                if shortcut:
                    discovered_resource = {
                        "id": f"res_{uuid.uuid4().hex[:10]}",
                        "user_id": user_id,
                        "course_id": course_id,
                        "assignment_id": assignment_id,
                        "type": shortcut["type"],
                        "title": shortcut["title"],
                        "url": shortcut["url"],
                        "path": relative,
                        "tags": shortcut["tags"],
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                else:
                    discovered_resource = {
                        "id": f"res_{uuid.uuid4().hex[:10]}",
                        "user_id": user_id,
                        "course_id": course_id,
                        "assignment_id": assignment_id,
                        "type": resource_type,
                        "title": entry.name,
                        "path": relative,
                        "tags": [],
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }

                discovered.append(discovered_resource)
                tracked_paths.add(relative)
                changed = True

        if not changed:
            return resources

        merged = kept_resources + discovered
        self.save_resources(user_id, course_id, assignment_id, merged)
        return merged

    def add_resource(self, user_id, course_id, assignment_id, resource):
        resources = self.load_resources(user_id, course_id, assignment_id)

        resource["id"] = resource.get("id") or f"res_{uuid.uuid4().hex[:10]}"
        resource["user_id"] = user_id
        resource["course_id"] = course_id
        resource["assignment_id"] = assignment_id
        resource["created_at"] = resource.get("created_at") or now_iso()
        resource["updated_at"] = now_iso()

        resources.append(resource)
        self.save_resources(user_id, course_id, assignment_id, resources)
        return resource

    def update_resource(self, resource):
        user_id = resource["user_id"]
        course_id = resource["course_id"]
        assignment_id = resource.get("assignment_id")

        resources = self.load_resources(user_id, course_id, assignment_id)

        for index, existing in enumerate(resources):
            if existing.get("id") == resource.get("id"):
                resource["updated_at"] = now_iso()
                resources[index] = resource
                self.save_resources(user_id, course_id, assignment_id, resources)
                return resource

        raise ValueError(f"Resource not found: {resource.get('id')}")

    def resource_absolute_path(self, resource):
        relative_path = resource.get("path")
        if not relative_path:
            return None

        context = self.context_dir(
            resource["user_id"],
            resource["course_id"],
            resource.get("assignment_id"),
        )
        return context / relative_path

    def delete_resource(self, resource, delete_physical=False):
        user_id = resource["user_id"]
        course_id = resource["course_id"]
        assignment_id = resource.get("assignment_id")

        if not delete_physical:
            resources = self.load_resources(user_id, course_id, assignment_id)
            resources = [item for item in resources if item.get("id") != resource.get("id")]
            self.save_resources(user_id, course_id, assignment_id, resources)
            return

        path = self.resource_absolute_path(resource)
        if path and path.exists():
            try:
                path.resolve().relative_to(self.root_path.resolve())
            except ValueError:
                pass
            else:
                remove_path(path)

        resources = self.load_resources(user_id, course_id, assignment_id)
        resources = [item for item in resources if item.get("id") != resource.get("id")]
        self.save_resources(user_id, course_id, assignment_id, resources)

    def collect_course_resources(self, user_id, course_id):
        resources = []
        resources.extend(self.load_resources(user_id, course_id, assignment_id=None))

        for assignment in self.get_assignments(user_id, course_id):
            resources.extend(self.load_resources(user_id, course_id, assignment["id"]))

        return resources

    def collect_all_resources(self):
        results = []

        for user in self.get_users():
            user_id = user["id"]

            for course in self.get_courses(user_id):
                course_id = course["id"]

                for resource in self.load_resources(user_id, course_id, assignment_id=None):
                    enriched = dict(resource)
                    enriched["user_name"] = user["name"]
                    enriched["course_code"] = course["code"]
                    enriched["course_name"] = course["name"]
                    enriched["assignment_title"] = "General Course Resources"
                    results.append(enriched)

                for assignment in self.get_assignments(user_id, course_id):
                    for resource in self.load_resources(user_id, course_id, assignment["id"]):
                        enriched = dict(resource)
                        enriched["user_name"] = user["name"]
                        enriched["course_code"] = course["code"]
                        enriched["course_name"] = course["name"]
                        enriched["assignment_title"] = assignment["title"]
                        results.append(enriched)

        return results

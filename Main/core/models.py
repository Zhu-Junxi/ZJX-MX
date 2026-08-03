RESOURCE_TYPES = {
    "local_file": {"label": "Local Files", "icon": "file"},
    "local_folder": {"label": "Folders", "icon": "folder"},
    "note": {"label": "Notes", "icon": "note"},
    "external_link": {"label": "External Links", "icon": "link"},
    "youtube": {"label": "YouTube", "icon": "video"},
    "google_drive": {"label": "Google Drive", "icon": "cloud"},
    "canvas": {"label": "Canvas", "icon": "canvas"},
}


def resource_type_label(resource_type):
    return RESOURCE_TYPES.get(resource_type, {}).get("label", "Resources")


def resource_type_icon(resource_type):
    return RESOURCE_TYPES.get(resource_type, {}).get("icon", "file")


def resource_type_display(resource_type):
    return resource_type_label(resource_type)

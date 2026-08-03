"""Shared file-type helpers for previewing and editing local resources."""

TEXT_PREVIEW_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".json",
    ".csv",
    ".xml",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".log",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
}

IMAGE_PREVIEW_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
}


def is_text_preview_file(path):
    return path.is_file() and path.suffix.lower() in TEXT_PREVIEW_SUFFIXES


def is_image_preview_file(path):
    return path.is_file() and path.suffix.lower() in IMAGE_PREVIEW_SUFFIXES

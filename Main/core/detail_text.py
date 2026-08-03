"""Text formatting helpers used by reusable detail cards."""

_DETAIL_KEY_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_/&().+")


def make_wrap_friendly_text(value):
    """Insert zero-width break points into long paths/URLs for QLabel wrapping."""
    text = str(value or "")
    if len(text) > 32:
        for token in ["\\", "/", "_", "-", ".", ":", "?"]:
            text = text.replace(token, token + "\u200b")
    return text


def is_detail_key(key):
    key = str(key or "").strip()

    if len(key) < 2 or len(key) > 56:
        return False

    if not key[0].isalpha():
        return False

    return any(character.isalpha() for character in key) and all(
        character in _DETAIL_KEY_ALLOWED_CHARS for character in key
    )


def details_pairs_from_text(text):
    """Parse plain detail text into key/value rows without corrupting paths.

    Supports both ``Key: Value`` and ``Key:\nValue`` formats. Non key/value
    lines are returned as notes so callers can still display the source text.
    """
    pairs = []
    notes = []
    lines = [raw_line.strip() for raw_line in (text or "").splitlines() if raw_line.strip()]

    index = 0
    while index < len(lines):
        line = lines[index]
        lower_line = line.lower()

        if lower_line in {"resource details", "file system entry details", "details"}:
            index += 1
            continue

        if line.endswith(":") and is_detail_key(line[:-1]):
            key = line[:-1].strip()
            value = ""

            if index + 1 < len(lines):
                candidate = lines[index + 1]
                candidate_is_next_key = candidate.endswith(":") and is_detail_key(candidate[:-1])

                if not candidate_is_next_key:
                    value = candidate
                    index += 2
                else:
                    index += 1
            else:
                index += 1

            pairs.append((key, value or "—"))
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if is_detail_key(key) and value:
                pairs.append((key, value))
                index += 1
                continue

        notes.append(line)
        index += 1

    return pairs, "\n".join(notes).strip()

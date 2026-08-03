from __future__ import annotations

import json
from dataclasses import asdict

from .dashboard_models import (
    DEFAULT_SUMMARY_METRIC_KEYS,
    SUMMARY_METRIC_KEYS,
    DashboardSettings,
    SORT_OPTIONS,
    TIMEFRAME_OPTIONS,
    VIEW_MODES,
)


DEFAULT_DASHBOARD_SETTINGS = DashboardSettings()


def dashboard_settings_key(user_id: str | None) -> str:
    safe_user = str(user_id or "none").replace("/", "_").replace("\\", "_")
    return f"dashboard/settings/{safe_user}"


def dashboard_settings_from_mapping(values) -> DashboardSettings:
    values = dict(values or {})
    defaults = asdict(DEFAULT_DASHBOARD_SETTINGS)
    merged = {**defaults, **values}

    if merged["timeframe"] not in TIMEFRAME_OPTIONS:
        merged["timeframe"] = defaults["timeframe"]
    if merged["sort"] not in SORT_OPTIONS:
        merged["sort"] = defaults["sort"]
    if merged["view_mode"] not in VIEW_MODES:
        merged["view_mode"] = defaults["view_mode"]
    merged["summary_metric_keys"] = _summary_metric_keys(
        merged.get("summary_metric_keys"),
        defaults["summary_metric_keys"],
    )

    for key, default in defaults.items():
        if isinstance(default, bool):
            merged[key] = _bool_value(merged.get(key), default)

    return DashboardSettings(**{key: merged[key] for key in defaults})


def dashboard_settings_to_mapping(settings: DashboardSettings) -> dict:
    return asdict(dashboard_settings_from_mapping(asdict(settings)))


def load_dashboard_settings(settings_backend, user_id: str | None) -> DashboardSettings:
    raw = settings_backend.value(dashboard_settings_key(user_id), None)
    if not raw:
        return DEFAULT_DASHBOARD_SETTINGS

    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return DEFAULT_DASHBOARD_SETTINGS

    return dashboard_settings_from_mapping(data)


def save_dashboard_settings(settings_backend, user_id: str | None, settings: DashboardSettings) -> DashboardSettings:
    cleaned = dashboard_settings_from_mapping(asdict(settings))
    settings_backend.setValue(dashboard_settings_key(user_id), json.dumps(dashboard_settings_to_mapping(cleaned)))
    return cleaned


def _bool_value(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    return str(value).lower() in {"true", "1", "yes", "on"}


def _summary_metric_keys(value, default=DEFAULT_SUMMARY_METRIC_KEYS) -> tuple[str, str, str, str]:
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple)):
        raw_items = [str(item).strip() for item in value]
    else:
        raw_items = []

    cleaned = []
    for item in raw_items:
        if item in SUMMARY_METRIC_KEYS and item not in cleaned:
            cleaned.append(item)
    for item in default:
        if len(cleaned) >= 4:
            break
        if item in SUMMARY_METRIC_KEYS and item not in cleaned:
            cleaned.append(item)

    for item in sorted(SUMMARY_METRIC_KEYS):
        if len(cleaned) >= 4:
            break
        if item not in cleaned:
            cleaned.append(item)

    while len(cleaned) < 4:
        cleaned.append(DEFAULT_SUMMARY_METRIC_KEYS[len(cleaned)])

    return tuple(cleaned[:4])

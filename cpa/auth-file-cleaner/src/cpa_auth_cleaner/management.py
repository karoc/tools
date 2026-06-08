"""Scan CPA management API runtime auth-file status."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import (
    INVALIDATED_ERROR_CODE,
    INVALIDATED_ERROR_MESSAGE,
    INVALIDATED_ERROR_TYPE,
)
from .models import InvalidAuthFile, ScanReport, SkippedFile


HEALTHY_STATUS_MESSAGES = set(["ok", "healthy", "ready", "success", "available"])


def fetch_management_auth_files(base_url, management_key, timeout=15):
    if not management_key:
        raise ValueError("management key is required")
    url = base_url.rstrip("/") + "/v0/management/auth-files"
    req = Request(url, headers={"X-Management-Key": management_key})
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError("management API returned HTTP %s" % exc.code)
    except URLError as exc:
        raise RuntimeError("management API request failed: %s" % exc.reason)

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("management API returned invalid JSON: %s" % exc)
    return payload


def management_key_from_args(value, env_name):
    if value:
        return value
    if env_name:
        return os.environ.get(env_name, "")
    return ""


def scan_management_payload(payload, match_mode="invalidated", auth_dir=None):
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        raise ValueError("management payload must contain a files array")

    invalid_files = []
    skipped_files = []
    base = Path(auth_dir).expanduser() if auth_dir else Path("")

    for item in files:
        if not isinstance(item, dict):
            skipped_files.append(SkippedFile(path=Path("<management>"), reason="file_entry_not_object"))
            continue
        if is_runtime_only(item):
            continue
        if matches_management_status(item, match_mode):
            invalid_files.append(build_management_candidate(base, item, match_mode))

    return ScanReport(
        auth_dir=base,
        scanned_json_files=len(files),
        invalid_files=tuple(invalid_files),
        skipped_files=tuple(skipped_files),
        source="management",
    )


def matches_management_status(item, match_mode):
    message = status_message(item)
    normalized = message.lower()
    if match_mode == "problem":
        return bool(message)
    if match_mode == "warning":
        return bool(message) and normalized not in HEALTHY_STATUS_MESSAGES
    if match_mode == "invalidated":
        return is_invalidated_status(item, message)
    raise ValueError("unsupported management match mode: %s" % match_mode)


def is_invalidated_status(item, message):
    lowered = message.lower()
    if message == INVALIDATED_ERROR_MESSAGE:
        return True
    if "authentication token has been invalidated" in lowered:
        return True
    if "invalidated" in lowered and "authentication" in lowered:
        return True
    code = string_value(item, "code").lower()
    error_type = string_value(item, "type").lower()
    return code == INVALIDATED_ERROR_CODE and error_type == INVALIDATED_ERROR_TYPE


def build_management_candidate(base, item, match_mode):
    name = string_value(item, "name") or string_value(item, "id") or "<unknown>"
    path_text = string_value(item, "path")
    path = Path(path_text) if path_text else base / name
    status = string_value(item, "status")
    message = status_message(item)
    reason = management_reason(item, match_mode)

    return InvalidAuthFile(
        path=path,
        relative_path=Path(name),
        provider=string_value(item, "type") or string_value(item, "provider") or None,
        email=string_value(item, "email") or None,
        project_id=string_value(item, "project_id") or None,
        error_message=message or status or reason,
        error_type="management_status",
        error_code=reason,
    )


def management_reason(item, match_mode):
    if match_mode == "invalidated":
        return INVALIDATED_ERROR_CODE
    if bool_value(item, "unavailable"):
        return "unavailable"
    status = string_value(item, "status").lower()
    if status and status != "active":
        return status
    return match_mode


def status_message(item):
    raw = item.get("status_message")
    if raw is None:
        raw = item.get("statusMessage")
    if raw is None:
        return ""
    return str(raw).strip()


def string_value(item, key):
    value = item.get(key)
    if value is None:
        return ""
    return str(value).strip()


def bool_value(item, key):
    value = item.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y", "on")
    return False


def is_runtime_only(item):
    return bool_value(item, "runtime_only") or bool_value(item, "runtimeOnly")


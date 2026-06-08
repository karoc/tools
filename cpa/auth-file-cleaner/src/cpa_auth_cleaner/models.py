"""Data models used by the CPA auth cleaner."""

class InvalidAuthFile:
    def __init__(
        self,
        path,
        relative_path,
        provider,
        email,
        project_id,
        error_message,
        error_type,
        error_code,
    ):
        self.path = path
        self.relative_path = relative_path
        self.provider = provider
        self.email = email
        self.project_id = project_id
        self.error_message = error_message
        self.error_type = error_type
        self.error_code = error_code


class SkippedFile:
    def __init__(self, path, reason):
        self.path = path
        self.reason = reason


class ScanReport:
    def __init__(self, auth_dir, scanned_json_files, invalid_files, skipped_files, source="file-marker"):
        self.auth_dir = auth_dir
        self.scanned_json_files = scanned_json_files
        self.invalid_files = invalid_files
        self.skipped_files = skipped_files
        self.source = source


class MoveRecord:
    def __init__(self, source, destination, moved):
        self.source = source
        self.destination = destination
        self.moved = moved

import getpass
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RetentionUnit(str, Enum):
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


@dataclass
class RetentionPolicy:
    keep_last: int = 10
    keep_hourly: int = 24
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 12
    keep_yearly: int = 5


@dataclass
class FileChange:
    path: str
    change_type: str  # added, modified, deleted
    size_bytes: int | None = None
    checksum: str | None = None


@dataclass
class BackupConfig:
    name: str
    source_paths: list[Path]
    restic_repo: Path
    schedule: str
    retention: RetentionPolicy
    encryption_key_file: Path | None = None
    keychain_account: str | None = None
    exclude_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.encryption_key_file and not self.keychain_account:
            raise ValueError("Must specify either encryption_key_file or keychain_account")


class SnapshotMetadata(BaseModel):
    snapshot_id: str
    message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    author: str = Field(default_factory=getpass.getuser)
    tags: list[str] = Field(default_factory=list)
    file_changes: list[FileChange] = Field(default_factory=list)
    parent_snapshot: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


@dataclass
class BackupStats:
    files_new: int = 0
    files_changed: int = 0
    files_unmodified: int = 0
    dirs_new: int = 0
    dirs_changed: int = 0
    dirs_unmodified: int = 0
    data_blobs: int = 0
    tree_blobs: int = 0
    data_added: int = 0
    total_files_processed: int = 0
    total_bytes_processed: int = 0
    total_duration: timedelta = field(default_factory=lambda: timedelta())


@dataclass
class RestoreOptions:
    target_path: Path
    selective_paths: list[str] | None = None
    exclude_patterns: list[str] | None = None
    include_patterns: list[str] | None = None
    verify: bool = True
    overwrite: bool = False

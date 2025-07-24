from .backup_manager import ModernBackupManager
from .cli import cli
from .metadata_store import MetadataStore
from .models import BackupConfig, FileChange, RetentionPolicy, SnapshotMetadata
from .monitor import FileMonitor, MonitorConfig, ScheduledBackupService
from .restic_wrapper import ResticError, ResticWrapper

__version__ = "0.1.0"

__all__ = [
    "BackupConfig",
    "RetentionPolicy",
    "SnapshotMetadata",
    "FileChange",
    "ModernBackupManager",
    "ResticWrapper",
    "ResticError",
    "MetadataStore",
    "FileMonitor",
    "MonitorConfig",
    "ScheduledBackupService",
    "cli",
]

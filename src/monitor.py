import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .backup_manager import ModernBackupManager
from .models import BackupConfig


@dataclass
class MonitorConfig:
    auto_snapshot_threshold: int = 50  # Auto snapshot after N changes
    auto_snapshot_interval: timedelta = field(
        default_factory=lambda: timedelta(hours=1)
    )  # Max time between auto snapshots
    debounce_seconds: float = 30.0  # Wait time after last change before processing
    ignore_patterns: set[str] = field(
        default_factory=lambda: {"*.tmp", "*.swp", "*.lock", ".DS_Store", "__pycache__"}
    )


class BackupEventHandler(FileSystemEventHandler):
    def __init__(self, monitor: "FileMonitor"):
        self.monitor = monitor

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip ignored patterns
        for pattern in self.monitor.config.ignore_patterns:
            if file_path.match(pattern):
                logger.debug(
                    f"Ignoring {event.event_type} event for {file_path} (matches {pattern})"
                )
                return

        logger.debug(f"File {event.event_type}: {file_path}")
        self.monitor._record_change(file_path, event.event_type)


class FileMonitor:
    def __init__(
        self,
        backup_config: BackupConfig,
        monitor_config: MonitorConfig = None,
        backup_manager: ModernBackupManager = None,
    ):
        self.backup_config = backup_config
        self.config = monitor_config or MonitorConfig()
        self.backup_manager = backup_manager or ModernBackupManager(backup_config)

        self.observer = Observer()
        self.handler = BackupEventHandler(self)
        self._changes: dict[str, dict[str, Any]] = {}
        self._last_change_time: datetime | None = None
        self._last_auto_snapshot: datetime | None = None
        self._change_lock = threading.Lock()
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks
        self.on_auto_snapshot: Callable[[str], None] | None = None
        self.on_change_detected: Callable[[Path, str], None] | None = None

    def start(self):
        logger.info("Starting file monitor...")

        # Add watchers for all source paths
        for source_path in self.backup_config.source_paths:
            if source_path.exists():
                self.observer.schedule(self.handler, str(source_path), recursive=True)
                logger.info(f"Monitoring: {source_path}")
            else:
                logger.warning(f"Source path does not exist: {source_path}")

        self.observer.start()

        # Start the monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("File monitor started")

    def stop(self):
        logger.info("Stopping file monitor...")

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        self.observer.stop()
        self.observer.join()

        logger.info("File monitor stopped")

    def _record_change(self, file_path: Path, event_type: str):
        with self._change_lock:
            path_str = str(file_path)
            self._changes[path_str] = {
                "path": file_path,
                "event_type": event_type,
                "timestamp": datetime.now(),
            }
            self._last_change_time = datetime.now()

            # Call callback if set
            if self.on_change_detected:
                try:
                    self.on_change_detected(file_path, event_type)
                except Exception as e:
                    logger.error(f"Error in change callback: {e}")

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_auto_snapshot()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

    def _check_auto_snapshot(self):
        with self._change_lock:
            now = datetime.now()

            # No changes to process
            if not self._changes or not self._last_change_time:
                return

            # Check if enough time has passed since last change (debounce)
            time_since_last_change = now - self._last_change_time
            if time_since_last_change < timedelta(seconds=self.config.debounce_seconds):
                return

            # Check if we should create an auto snapshot
            should_snapshot = False
            reason = ""

            # Threshold-based snapshot
            if len(self._changes) >= self.config.auto_snapshot_threshold:
                should_snapshot = True
                reason = f"change threshold ({len(self._changes)} changes)"

            # Time-based snapshot
            elif self._last_auto_snapshot:
                time_since_last_snapshot = now - self._last_auto_snapshot
                if time_since_last_snapshot >= self.config.auto_snapshot_interval:
                    should_snapshot = True
                    reason = f"time interval ({time_since_last_snapshot})"

            # First auto snapshot (no previous snapshot recorded)
            elif not self._last_auto_snapshot and len(self._changes) > 0:
                should_snapshot = True
                reason = "initial auto snapshot"

            if should_snapshot:
                try:
                    self._create_auto_snapshot(reason)
                except Exception as e:
                    logger.error(f"Failed to create auto snapshot: {e}")

    def _create_auto_snapshot(self, reason: str):
        change_count = len(self._changes)

        # Create a meaningful commit message
        change_summary = self._summarize_changes()
        message = f"Auto snapshot: {change_summary} ({reason})"

        logger.info(f"Creating auto snapshot: {message}")

        try:
            snapshot_id = self.backup_manager.snapshot(
                message=message,
                tags=["auto", "monitor"],
                validate_sources=False,  # Skip validation for auto snapshots
            )

            # Clear processed changes
            self._changes.clear()
            self._last_auto_snapshot = datetime.now()

            logger.info(f"Auto snapshot created: {snapshot_id[:12]}... ({change_count} changes)")

            # Call callback if set
            if self.on_auto_snapshot:
                try:
                    self.on_auto_snapshot(snapshot_id)
                except Exception as e:
                    logger.error(f"Error in auto snapshot callback: {e}")

        except Exception as e:
            logger.error(f"Auto snapshot failed: {e}")
            # Don't clear changes on failure so we can retry

    def _summarize_changes(self) -> str:
        if not self._changes:
            return "no changes"

        # Count change types
        counts = {}
        for change in self._changes.values():
            event_type = change["event_type"]
            counts[event_type] = counts.get(event_type, 0) + 1

        # Create summary
        parts = []
        if counts.get("created", 0) > 0:
            parts.append(f"{counts['created']} added")
        if counts.get("modified", 0) > 0:
            parts.append(f"{counts['modified']} modified")
        if counts.get("deleted", 0) > 0:
            parts.append(f"{counts['deleted']} deleted")
        if counts.get("moved", 0) > 0:
            parts.append(f"{counts['moved']} moved")

        return ", ".join(parts) if parts else f"{len(self._changes)} changes"

    def get_pending_changes(self) -> dict[str, dict[str, Any]]:
        with self._change_lock:
            return self._changes.copy()

    def clear_pending_changes(self):
        with self._change_lock:
            self._changes.clear()
            self._last_change_time = None

    def force_snapshot(self, message: str | None = None) -> str:
        change_count = len(self._changes)
        if change_count == 0:
            raise ValueError("No pending changes to snapshot")

        if not message:
            change_summary = self._summarize_changes()
            message = f"Manual snapshot: {change_summary}"

        snapshot_id = self.backup_manager.snapshot(
            message=message, tags=["manual", "monitor"], validate_sources=False
        )

        self.clear_pending_changes()
        self._last_auto_snapshot = datetime.now()

        logger.info(f"Manual snapshot created: {snapshot_id[:12]}... ({change_count} changes)")
        return snapshot_id

    def get_status(self) -> dict[str, Any]:
        with self._change_lock:
            return {
                "monitoring": self.observer.is_alive(),
                "pending_changes": len(self._changes),
                "last_change": self._last_change_time.isoformat()
                if self._last_change_time
                else None,
                "last_auto_snapshot": self._last_auto_snapshot.isoformat()
                if self._last_auto_snapshot
                else None,
                "monitored_paths": [str(p) for p in self.backup_config.source_paths],
                "config": {
                    "auto_snapshot_threshold": self.config.auto_snapshot_threshold,
                    "auto_snapshot_interval": str(self.config.auto_snapshot_interval),
                    "debounce_seconds": self.config.debounce_seconds,
                },
            }


class ScheduledBackupService:
    def __init__(self, backup_config: BackupConfig, backup_manager: ModernBackupManager = None):
        self.backup_config = backup_config
        self.backup_manager = backup_manager or ModernBackupManager(backup_config)
        self._schedule_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self):
        if not self.backup_config.schedule:
            logger.info("No schedule configured, skipping scheduled backups")
            return

        logger.info(
            f"Starting scheduled backup service with schedule: {self.backup_config.schedule}"
        )
        self._schedule_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self._schedule_thread.start()

    def stop(self):
        if self._schedule_thread:
            logger.info("Stopping scheduled backup service...")
            self._stop_event.set()
            self._schedule_thread.join(timeout=5.0)

    def _schedule_loop(self):
        # This is a simplified scheduler - in production you'd use a proper cron library
        # For now, just create periodic snapshots based on a simple interval

        # Parse simple schedule format (e.g., "1h", "30m", "2d")
        interval = self._parse_schedule(self.backup_config.schedule)
        if not interval:
            logger.error(f"Invalid schedule format: {self.backup_config.schedule}")
            return

        next_backup = datetime.now() + interval
        logger.info(f"Next scheduled backup: {next_backup}")

        while not self._stop_event.is_set():
            now = datetime.now()

            if now >= next_backup:
                try:
                    self._create_scheduled_backup()
                    next_backup = now + interval
                    logger.info(f"Next scheduled backup: {next_backup}")
                except Exception as e:
                    logger.error(f"Scheduled backup failed: {e}")
                    # Still update next backup time to avoid continuous failures
                    next_backup = now + interval

            # Sleep for a short time to avoid busy waiting
            self._stop_event.wait(60)  # Check every minute

    def _parse_schedule(self, schedule: str) -> timedelta | None:
        schedule = schedule.strip().lower()

        if schedule.endswith("h"):
            try:
                hours = int(schedule[:-1])
                return timedelta(hours=hours)
            except ValueError:
                return None
        elif schedule.endswith("m"):
            try:
                minutes = int(schedule[:-1])
                return timedelta(minutes=minutes)
            except ValueError:
                return None
        elif schedule.endswith("d"):
            try:
                days = int(schedule[:-1])
                return timedelta(days=days)
            except ValueError:
                return None

        return None

    def _create_scheduled_backup(self):
        message = f"Scheduled backup ({self.backup_config.schedule})"

        snapshot_id = self.backup_manager.snapshot(message=message, tags=["scheduled", "automatic"])

        logger.info(f"Scheduled backup created: {snapshot_id[:12]}...")

        # Apply retention policy after scheduled backup
        try:
            removed = self.backup_manager.forget(dry_run=False)
            if removed:
                logger.info(f"Retention policy removed {len(removed)} old snapshots")
        except Exception as e:
            logger.warning(f"Failed to apply retention policy: {e}")

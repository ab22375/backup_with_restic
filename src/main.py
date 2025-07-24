#!/usr/bin/env python3

import signal
import sys
from pathlib import Path

from loguru import logger

from .backup_manager import ModernBackupManager
from .cli import cli
from .models import BackupConfig, RetentionPolicy
from .monitor import FileMonitor, MonitorConfig, ScheduledBackupService


def create_sample_config():
    """Create a sample configuration for demonstration"""
    return BackupConfig(
        name="sample-backup",
        source_paths=[Path.home() / "Documents", Path.home() / "Pictures"],
        restic_repo=Path.home() / "backups" / "restic-repo",
        schedule="1h",  # Every hour
        retention=RetentionPolicy(
            keep_last=10,
            keep_hourly=24,
            keep_daily=7,
            keep_weekly=4,
            keep_monthly=12,
            keep_yearly=5,
        ),
        encryption_key_file=Path.home() / ".backup" / "encryption.key",
        exclude_patterns=[
            "*.tmp",
            "*.log",
            ".DS_Store",
            "__pycache__",
            "node_modules",
            ".git",
            "*.cache",
        ],
    )


def run_daemon_mode(config: BackupConfig):
    """Run the backup system in daemon mode with monitoring and scheduling"""
    logger.info("Starting backup daemon...")

    # Create backup manager
    backup_manager = ModernBackupManager(config)

    # Create file monitor
    monitor_config = MonitorConfig(
        auto_snapshot_threshold=25,  # Auto snapshot after 25 changes
        debounce_seconds=30.0,
    )
    file_monitor = FileMonitor(config, monitor_config, backup_manager)

    # Create scheduled backup service
    scheduler = ScheduledBackupService(config, backup_manager)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping services...")
        file_monitor.stop()
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start services
        file_monitor.start()
        scheduler.start()

        logger.info("Backup daemon started successfully")
        logger.info("Press Ctrl+C to stop")

        # Keep the main thread alive
        signal.pause()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        file_monitor.stop()
        scheduler.stop()


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        # Run in daemon mode
        config = create_sample_config()
        run_daemon_mode(config)
    else:
        # Run CLI interface
        cli()


if __name__ == "__main__":
    main()

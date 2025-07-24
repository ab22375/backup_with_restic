import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .metadata_store import MetadataStore
from .models import BackupConfig, FileChange, SnapshotMetadata
from .restic_wrapper import ResticWrapper


class ModernBackupManager:
    def __init__(self, config: BackupConfig):
        self.config = config
        self.restic = ResticWrapper(
            config.restic_repo,
            password_file=config.encryption_key_file,
            keychain_account=config.keychain_account,
        )
        self.metadata_store = MetadataStore(config.restic_repo / "metadata")
        self._last_snapshot_info = None

    def snapshot(
        self, message: str = None, tags: list[str] = None, validate_sources: bool = True
    ) -> str:
        start_time = time.time()

        try:
            if validate_sources:
                self._validate_sources()

            # Detect changes since last snapshot
            file_changes = self._detect_changes()

            # Create restic snapshot
            all_tags = (tags or []).copy()
            if message:
                all_tags.append(f"message:{message}")

            logger.info(f"Creating snapshot for {len(self.config.source_paths)} paths")
            snapshot_id = self.restic.backup(
                paths=self.config.source_paths,
                tags=all_tags,
                exclude_patterns=self.config.exclude_patterns,
                include_patterns=self.config.include_patterns,
                message=message,
            )

            # Get parent snapshot for lineage
            parent_snapshot = self._get_last_snapshot_id()

            # Get backup statistics
            restic_stats = self.restic.get_repo_stats()
            backup_stats = {
                "duration_seconds": time.time() - start_time,
                "files_changed": len(
                    [c for c in file_changes if c.change_type in ["added", "modified"]]
                ),
                "total_size_bytes": restic_stats.get("total_size", 0),
                "total_file_count": restic_stats.get("total_file_count", 0),
            }

            # Store rich metadata
            metadata = SnapshotMetadata(
                snapshot_id=snapshot_id,
                message=message,
                timestamp=datetime.now(),
                tags=tags or [],
                file_changes=file_changes,
                parent_snapshot=parent_snapshot,
                stats=backup_stats,
            )

            self.metadata_store.save(metadata)
            self._last_snapshot_info = metadata

            logger.info(
                f"Snapshot {snapshot_id} created successfully in {backup_stats['duration_seconds']:.2f}s"
            )
            return snapshot_id

        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            raise

    def log(
        self, limit: int = 10, author: str | None = None, tags: list[str] | None = None
    ) -> list[SnapshotMetadata]:
        logger.debug(f"Retrieving {limit} recent snapshots")
        return self.metadata_store.get_recent(limit=limit, author=author, tags=tags)

    def restore(
        self,
        ref: str,
        target: Path,
        selective_paths: list[str] = None,
        exclude_patterns: list[str] = None,
        include_patterns: list[str] = None,
        verify: bool = True,
        overwrite: bool = False,
    ) -> bool:
        try:
            # Resolve reference to snapshot ID
            snapshot_id = self._resolve_ref(ref)

            # Validate target directory
            if target.exists() and not overwrite:
                if any(target.iterdir()):
                    raise ValueError(
                        f"Target directory {target} is not empty. Use overwrite=True to force."
                    )

            target.mkdir(parents=True, exist_ok=True)

            logger.info(f"Restoring snapshot {snapshot_id} to {target}")

            # Perform restore
            self.restic.restore(
                snapshot_id=snapshot_id,
                target_path=target,
                selective_paths=selective_paths,
                exclude_patterns=exclude_patterns,
                include_patterns=include_patterns,
                verify=verify,
            )

            logger.info(f"Successfully restored snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise

    def show(self, ref: str = "latest") -> SnapshotMetadata | None:
        try:
            snapshot_id = self._resolve_ref(ref)
            return self.metadata_store.get(snapshot_id)
        except Exception as e:
            logger.error(f"Failed to show snapshot {ref}: {e}")
            return None

    def diff(self, ref1: str = "HEAD~1", ref2: str = "HEAD") -> list[FileChange]:
        try:
            snapshot1 = self.show(ref1)
            snapshot2 = self.show(ref2)

            if not snapshot1 or not snapshot2:
                logger.error("One or both snapshots not found")
                return []

            # Simple diff based on file changes
            changes = []
            files1 = {change.path: change for change in snapshot1.file_changes}
            files2 = {change.path: change for change in snapshot2.file_changes}

            # Files in snapshot2 but not in snapshot1 (added)
            for path in files2:
                if path not in files1:
                    changes.append(files2[path])
                elif files1[path].checksum != files2[path].checksum:
                    changes.append(FileChange(path=path, change_type="modified"))

            # Files in snapshot1 but not in snapshot2 (deleted)
            for path in files1:
                if path not in files2:
                    changes.append(FileChange(path=path, change_type="deleted"))

            return changes

        except Exception as e:
            logger.error(f"Failed to diff snapshots: {e}")
            return []

    def status(self) -> dict[str, Any]:
        try:
            # Get repository stats
            repo_stats = self.restic.get_repo_stats()

            # Get recent snapshots
            recent_snapshots = self.log(limit=5)

            # Check repository health
            repo_healthy = self.restic.check_repo()

            # Detect uncommitted changes
            current_changes = self._detect_changes()
            has_changes = len(current_changes) > 0

            return {
                "repository_path": str(self.config.restic_repo),
                "repository_healthy": repo_healthy,
                "total_snapshots": len(self.restic.list_snapshots()),
                "repository_size": repo_stats.get("total_size", 0),
                "last_snapshot": recent_snapshots[0].timestamp if recent_snapshots else None,
                "uncommitted_changes": len(current_changes),
                "has_uncommitted_changes": has_changes,
                "source_paths": [str(p) for p in self.config.source_paths],
                "recent_snapshots": [
                    {
                        "id": snap.snapshot_id[:8],
                        "message": snap.message,
                        "timestamp": snap.timestamp,
                        "author": snap.author,
                    }
                    for snap in recent_snapshots
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {"error": str(e)}

    def search(self, query: str, limit: int = 50) -> list[SnapshotMetadata]:
        return self.metadata_store.search(query, limit)

    def forget(self, refs: list[str] = None, dry_run: bool = False) -> list[str]:
        try:
            if refs:
                # Forget specific snapshots
                removed = []
                for ref in refs:
                    snapshot_id = self._resolve_ref(ref)
                    if not dry_run:
                        # Remove from restic (this is tricky - restic doesn't have direct delete)
                        # We'd need to use forget with specific snapshot
                        pass
                    removed.append(snapshot_id)
                return removed
            else:
                # Use retention policy
                retention_dict = {
                    "last": self.config.retention.keep_last,
                    "hourly": self.config.retention.keep_hourly,
                    "daily": self.config.retention.keep_daily,
                    "weekly": self.config.retention.keep_weekly,
                    "monthly": self.config.retention.keep_monthly,
                    "yearly": self.config.retention.keep_yearly,
                }

                removed_snapshots = self.restic.forget_snapshots(
                    retention_policy=retention_dict, dry_run=dry_run, prune=True
                )

                # Clean up metadata for removed snapshots
                if not dry_run:
                    for snapshot_id in removed_snapshots:
                        self.metadata_store.delete(snapshot_id)

                return removed_snapshots

        except Exception as e:
            logger.error(f"Failed to forget snapshots: {e}")
            return []

    def _validate_sources(self):
        for path in self.config.source_paths:
            if not path.exists():
                raise FileNotFoundError(f"Source path does not exist: {path}")
            if not os.access(path, os.R_OK):
                raise PermissionError(f"Cannot read source path: {path}")

    def _detect_changes(self) -> list[FileChange]:
        changes = []

        # Simple change detection - compare with last snapshot
        # In a full implementation, this would be more sophisticated
        last_snapshot = self._get_last_snapshot_info()
        if not last_snapshot:
            # First snapshot - everything is new
            for source_path in self.config.source_paths:
                for file_path in self._walk_directory(source_path):
                    try:
                        stat = file_path.stat()
                        changes.append(
                            FileChange(
                                path=str(file_path.relative_to(source_path)),
                                change_type="added",
                                size_bytes=stat.st_size,
                                checksum=self._calculate_checksum(file_path),
                            )
                        )
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Cannot access {file_path}: {e}")
                        continue
        else:
            # Compare with previous snapshot (simplified)
            # A full implementation would store file metadata and compare timestamps/checksums
            logger.debug("Change detection against previous snapshot not fully implemented")

        return changes

    def _walk_directory(self, path: Path):
        try:
            if path.is_file():
                yield path
            elif path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file() and not self._should_exclude(item):
                        yield item
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot walk directory {path}: {e}")

    def _should_exclude(self, path: Path) -> bool:
        path_str = str(path)

        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if path.match(pattern) or pattern in path_str:
                return True

        # If include patterns are specified, only include matching files
        if self.config.include_patterns:
            for pattern in self.config.include_patterns:
                if path.match(pattern) or pattern in path_str:
                    return False
            return True

        return False

    def _calculate_checksum(self, file_path: Path) -> str:
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return ""

    def _resolve_ref(self, ref: str) -> str:
        return self.restic.resolve_snapshot_ref(ref)

    def _get_last_snapshot_id(self) -> str | None:
        try:
            snapshots = self.restic.list_snapshots()
            return snapshots[-1]["id"] if snapshots else None
        except Exception:
            return None

    def _get_last_snapshot_info(self) -> SnapshotMetadata | None:
        if self._last_snapshot_info:
            return self._last_snapshot_info

        recent = self.log(limit=1)
        return recent[0] if recent else None

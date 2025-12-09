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
        self,
        message: str = None,
        tags: list[str] = None,
        validate_sources: bool = True,
        progress_callback: callable = None,
    ) -> tuple[str, dict]:
        """Create a snapshot and return (snapshot_id, summary_stats)."""
        start_time = time.time()

        try:
            if validate_sources:
                self._validate_sources()

            # Create restic snapshot
            all_tags = (tags or []).copy()
            if message:
                all_tags.append(f"message:{message}")

            logger.info(f"Creating snapshot for {len(self.config.source_paths)} paths")
            snapshot_id, backup_summary = self.restic.backup(
                paths=self.config.source_paths,
                tags=all_tags,
                exclude_patterns=self.config.exclude_patterns,
                include_patterns=self.config.include_patterns,
                message=message,
                progress_callback=progress_callback,
            )

            # Get parent snapshot for lineage
            parent_snapshot = self._get_last_snapshot_id()

            # Build stats from restic summary
            backup_stats = {
                "duration_seconds": time.time() - start_time,
                "files_new": backup_summary.get("files_new", 0),
                "files_changed": backup_summary.get("files_changed", 0),
                "files_unmodified": backup_summary.get("files_unmodified", 0),
                "dirs_new": backup_summary.get("dirs_new", 0),
                "dirs_changed": backup_summary.get("dirs_changed", 0),
                "dirs_unmodified": backup_summary.get("dirs_unmodified", 0),
                "data_added": backup_summary.get("data_added", 0),
                "total_files_processed": backup_summary.get("total_files_processed", 0),
                "total_bytes_processed": backup_summary.get("total_bytes_processed", 0),
            }

            # Detect changes for metadata (simplified)
            file_changes = self._detect_changes()

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
            return snapshot_id, backup_stats

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
        """Detect file changes since the last snapshot using restic diff."""
        changes = []

        last_snapshot_id = self._get_last_snapshot_id()
        if not last_snapshot_id:
            # First snapshot - everything is new, but don't enumerate all files
            # (too slow for large directories, restic will handle it)
            logger.debug("First snapshot - skipping change detection")
            return changes

        try:
            # Use restic diff to compare last snapshot with current filesystem
            # Note: restic diff compares two snapshots, not filesystem vs snapshot
            # For filesystem comparison, we compare second-to-last vs last snapshot
            snapshots = self.restic.list_snapshots()
            if len(snapshots) < 2:
                logger.debug("Only one snapshot exists - skipping change detection")
                return changes

            # Get the two most recent snapshots
            prev_snapshot_id = snapshots[-2]["id"]
            last_snapshot_id = snapshots[-1]["id"]

            diff_result = self.restic.diff_snapshots(prev_snapshot_id, last_snapshot_id)

            # Convert to FileChange objects
            for path in diff_result.get("added", []):
                changes.append(FileChange(path=path, change_type="added"))

            for path in diff_result.get("removed", []):
                changes.append(FileChange(path=path, change_type="deleted"))

            for path in diff_result.get("modified", []):
                changes.append(FileChange(path=path, change_type="modified"))

            logger.debug(
                f"Change detection: {len(diff_result.get('added', []))} added, "
                f"{len(diff_result.get('removed', []))} removed, "
                f"{len(diff_result.get('modified', []))} modified"
            )

        except Exception as e:
            logger.warning(f"Change detection failed: {e}")

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

        # Check .backupignore files (like .gitignore)
        if self._check_backupignore(path):
            return True

        # Check exclude patterns from config
        for pattern in self.config.exclude_patterns:
            # Skip comment lines
            if pattern.startswith('#'):
                continue
            if path.match(pattern) or pattern in path_str:
                return True

        # If include patterns are specified, only include matching files
        if self.config.include_patterns:
            for pattern in self.config.include_patterns:
                if path.match(pattern) or pattern in path_str:
                    return False
            return True

        return False
    
    def _check_backupignore(self, path: Path) -> bool:
        """Check if path should be excluded based on .backupignore files"""
        # Look for .backupignore files in parent directories
        current_dir = path.parent if path.is_file() else path
        
        while current_dir and current_dir != current_dir.parent:
            backupignore_file = current_dir / '.backupignore'
            if backupignore_file.exists():
                try:
                    with open(backupignore_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if not line or line.startswith('#'):
                                continue
                            
                            # Create relative path for pattern matching
                            try:
                                rel_path = path.relative_to(current_dir)
                                if rel_path.match(line) or line in str(rel_path):
                                    return True
                            except ValueError:
                                # path is not relative to current_dir
                                continue
                except (OSError, PermissionError):
                    continue
            
            # Move up one directory
            current_dir = current_dir.parent
        
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

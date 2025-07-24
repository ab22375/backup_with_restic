import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .models import FileChange, SnapshotMetadata


class MetadataStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.store_path / "metadata.db"
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    message TEXT,
                    timestamp TEXT NOT NULL,
                    author TEXT NOT NULL,
                    tags TEXT,
                    parent_snapshot TEXT,
                    stats TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id TEXT,
                    path TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    size_bytes INTEGER,
                    checksum TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots (snapshot_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp
                ON snapshots (timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_snapshot
                ON file_changes (snapshot_id)
            """)

            conn.commit()

    def save(self, metadata: SnapshotMetadata) -> None:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Insert snapshot metadata
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO snapshots
                        (snapshot_id, message, timestamp, author, tags, parent_snapshot, stats)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            metadata.snapshot_id,
                            metadata.message,
                            metadata.timestamp.isoformat(),
                            metadata.author,
                            json.dumps(metadata.tags),
                            metadata.parent_snapshot,
                            json.dumps(metadata.stats),
                        ),
                    )

                    # Delete existing file changes for this snapshot
                    conn.execute(
                        "DELETE FROM file_changes WHERE snapshot_id = ?", (metadata.snapshot_id,)
                    )

                    # Insert file changes
                    for change in metadata.file_changes:
                        conn.execute(
                            """
                            INSERT INTO file_changes
                            (snapshot_id, path, change_type, size_bytes, checksum)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (
                                metadata.snapshot_id,
                                change.path,
                                change.change_type,
                                change.size_bytes,
                                change.checksum,
                            ),
                        )

                    conn.commit()
                    logger.debug(f"Saved metadata for snapshot {metadata.snapshot_id}")

            except sqlite3.Error as e:
                logger.error(f"Failed to save metadata for snapshot {metadata.snapshot_id}: {e}")
                raise

    def get(self, snapshot_id: str) -> SnapshotMetadata | None:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row

                    # Get snapshot metadata
                    cursor = conn.execute(
                        """
                        SELECT * FROM snapshots WHERE snapshot_id = ?
                    """,
                        (snapshot_id,),
                    )

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # Get file changes
                    changes_cursor = conn.execute(
                        """
                        SELECT path, change_type, size_bytes, checksum
                        FROM file_changes WHERE snapshot_id = ?
                    """,
                        (snapshot_id,),
                    )

                    file_changes = [
                        FileChange(
                            path=change_row["path"],
                            change_type=change_row["change_type"],
                            size_bytes=change_row["size_bytes"],
                            checksum=change_row["checksum"],
                        )
                        for change_row in changes_cursor.fetchall()
                    ]

                    return SnapshotMetadata(
                        snapshot_id=row["snapshot_id"],
                        message=row["message"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        author=row["author"],
                        tags=json.loads(row["tags"]) if row["tags"] else [],
                        parent_snapshot=row["parent_snapshot"],
                        stats=json.loads(row["stats"]) if row["stats"] else {},
                        file_changes=file_changes,
                    )

            except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to get metadata for snapshot {snapshot_id}: {e}")
                return None

    def get_recent(
        self, limit: int = 10, author: str | None = None, tags: list[str] | None = None
    ) -> list[SnapshotMetadata]:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row

                    query = "SELECT * FROM snapshots WHERE 1=1"
                    params = []

                    if author:
                        query += " AND author = ?"
                        params.append(author)

                    if tags:
                        # Simple tag filtering - could be improved with proper JSON queries
                        for tag in tags:
                            query += " AND tags LIKE ?"
                            params.append(f'%"{tag}"%')

                    query += " ORDER BY timestamp DESC LIMIT ?"
                    params.append(limit)

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()

                    snapshots = []
                    for row in rows:
                        # Get file changes for each snapshot
                        changes_cursor = conn.execute(
                            """
                            SELECT path, change_type, size_bytes, checksum
                            FROM file_changes WHERE snapshot_id = ?
                        """,
                            (row["snapshot_id"],),
                        )

                        file_changes = [
                            FileChange(
                                path=change_row["path"],
                                change_type=change_row["change_type"],
                                size_bytes=change_row["size_bytes"],
                                checksum=change_row["checksum"],
                            )
                            for change_row in changes_cursor.fetchall()
                        ]

                        snapshots.append(
                            SnapshotMetadata(
                                snapshot_id=row["snapshot_id"],
                                message=row["message"],
                                timestamp=datetime.fromisoformat(row["timestamp"]),
                                author=row["author"],
                                tags=json.loads(row["tags"]) if row["tags"] else [],
                                parent_snapshot=row["parent_snapshot"],
                                stats=json.loads(row["stats"]) if row["stats"] else {},
                                file_changes=file_changes,
                            )
                        )

                    return snapshots

            except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to get recent snapshots: {e}")
                return []

    def search(self, query: str, limit: int = 50) -> list[SnapshotMetadata]:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row

                    # Search in message, author, and tags
                    cursor = conn.execute(
                        """
                        SELECT * FROM snapshots
                        WHERE message LIKE ? OR author LIKE ? OR tags LIKE ?
                        ORDER BY timestamp DESC LIMIT ?
                    """,
                        (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                    )

                    rows = cursor.fetchall()

                    snapshots = []
                    for row in rows:
                        # Get file changes for each snapshot
                        changes_cursor = conn.execute(
                            """
                            SELECT path, change_type, size_bytes, checksum
                            FROM file_changes WHERE snapshot_id = ?
                        """,
                            (row["snapshot_id"],),
                        )

                        file_changes = [
                            FileChange(
                                path=change_row["path"],
                                change_type=change_row["change_type"],
                                size_bytes=change_row["size_bytes"],
                                checksum=change_row["checksum"],
                            )
                            for change_row in changes_cursor.fetchall()
                        ]

                        snapshots.append(
                            SnapshotMetadata(
                                snapshot_id=row["snapshot_id"],
                                message=row["message"],
                                timestamp=datetime.fromisoformat(row["timestamp"]),
                                author=row["author"],
                                tags=json.loads(row["tags"]) if row["tags"] else [],
                                parent_snapshot=row["parent_snapshot"],
                                stats=json.loads(row["stats"]) if row["stats"] else {},
                                file_changes=file_changes,
                            )
                        )

                    return snapshots

            except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to search snapshots: {e}")
                return []

    def delete(self, snapshot_id: str) -> bool:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Delete file changes first
                    conn.execute("DELETE FROM file_changes WHERE snapshot_id = ?", (snapshot_id,))

                    # Delete snapshot metadata
                    cursor = conn.execute(
                        "DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
                    )

                    deleted = cursor.rowcount > 0
                    conn.commit()

                    if deleted:
                        logger.debug(f"Deleted metadata for snapshot {snapshot_id}")

                    return deleted

            except sqlite3.Error as e:
                logger.error(f"Failed to delete metadata for snapshot {snapshot_id}: {e}")
                return False

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) as total_snapshots FROM snapshots")
                    total_snapshots = cursor.fetchone()[0]

                    cursor = conn.execute("SELECT COUNT(*) as total_changes FROM file_changes")
                    total_changes = cursor.fetchone()[0]

                    cursor = conn.execute("""
                        SELECT author, COUNT(*) as count
                        FROM snapshots
                        GROUP BY author
                        ORDER BY count DESC
                    """)
                    authors = [{"author": row[0], "count": row[1]} for row in cursor.fetchall()]

                    return {
                        "total_snapshots": total_snapshots,
                        "total_file_changes": total_changes,
                        "authors": authors,
                    }

            except sqlite3.Error as e:
                logger.error(f"Failed to get metadata stats: {e}")
                return {}

    def cleanup(self, keep_days: int = 365):
        with self._lock:
            try:
                cutoff_date = datetime.now().replace(day=datetime.now().day - keep_days)
                cutoff_iso = cutoff_date.isoformat()

                with sqlite3.connect(self.db_path) as conn:
                    # Get snapshot IDs to delete
                    cursor = conn.execute(
                        """
                        SELECT snapshot_id FROM snapshots WHERE timestamp < ?
                    """,
                        (cutoff_iso,),
                    )

                    old_snapshots = [row[0] for row in cursor.fetchall()]

                    if old_snapshots:
                        # Delete file changes
                        placeholders = ",".join(["?" for _ in old_snapshots])
                        conn.execute(
                            f"""
                            DELETE FROM file_changes
                            WHERE snapshot_id IN ({placeholders})
                        """,
                            old_snapshots,
                        )

                        # Delete snapshots
                        conn.execute(
                            f"""
                            DELETE FROM snapshots
                            WHERE snapshot_id IN ({placeholders})
                        """,
                            old_snapshots,
                        )

                        conn.commit()
                        logger.info(
                            f"Cleaned up {len(old_snapshots)} old snapshot metadata entries"
                        )

                    return len(old_snapshots)

            except sqlite3.Error as e:
                logger.error(f"Failed to cleanup old metadata: {e}")
                return 0

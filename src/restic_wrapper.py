import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from .keychain_helper import KeychainManager


class ResticError(Exception):
    pass


class ResticWrapper:
    def __init__(
        self,
        repo_path: Path,
        password_file: Path | None = None,
        password: str | None = None,
        keychain_account: str | None = None,
    ):
        self.repo_path = repo_path
        self.password_file = password_file
        self.password = password
        self.keychain_account = keychain_account
        self.keychain = KeychainManager() if keychain_account else None
        self._ensure_repo_exists()

    def _get_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["RESTIC_REPOSITORY"] = str(self.repo_path)

        # Priority order: password_file > keychain > direct password
        if self.password_file:
            env["RESTIC_PASSWORD_FILE"] = str(self.password_file)
        elif self.keychain_account and self.keychain:
            keychain_password = self.keychain.get_password(self.keychain_account)
            if keychain_password:
                env["RESTIC_PASSWORD"] = keychain_password
            else:
                raise ResticError(
                    f"Could not retrieve password from keychain for account: {self.keychain_account}"
                )
        elif self.password:
            env["RESTIC_PASSWORD"] = self.password
        else:
            raise ResticError("No password, password file, or keychain account provided")

        return env

    def _run_command(
        self, args: list[str], capture_output: bool = True, check: bool = True
    ) -> subprocess.CompletedProcess:
        cmd = ["restic"] + args
        logger.debug(f"Running restic command: {' '.join(shlex.quote(arg) for arg in cmd)}")

        try:
            result = subprocess.run(
                cmd, env=self._get_env(), capture_output=capture_output, text=True, check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Restic command failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise ResticError(f"Restic command failed: {e.stderr}")
        except FileNotFoundError:
            raise ResticError("Restic binary not found. Please install restic first.")

    def _ensure_repo_exists(self):
        try:
            self._run_command(["cat", "config"])
        except ResticError:
            logger.info(f"Repository doesn't exist, initializing at {self.repo_path}")
            self.init_repo()

    def init_repo(self):
        self.repo_path.parent.mkdir(parents=True, exist_ok=True)
        result = self._run_command(["init"])
        logger.info(f"Initialized restic repository at {self.repo_path}")
        return result

    def backup(
        self,
        paths: list[Path],
        tags: list[str] = None,
        exclude_patterns: list[str] = None,
        include_patterns: list[str] = None,
        message: str = None,
        progress_callback: callable = None,
    ) -> tuple[str, dict]:
        """Run backup and return (snapshot_id, summary_stats).

        Args:
            progress_callback: Optional callback(status_dict) called with real-time progress
        """
        args = ["backup"] + [str(path) for path in paths]

        if tags:
            for tag in tags:
                args.extend(["--tag", tag])

        if exclude_patterns:
            for pattern in exclude_patterns:
                args.extend(["--exclude", pattern])

        if include_patterns:
            for pattern in include_patterns:
                args.extend(["--include", pattern])

        if message:
            args.extend(["--tag", f"message:{message}"])

        args.append("--json")

        # Use streaming mode if callback provided
        if progress_callback:
            return self._run_backup_streaming(args, progress_callback)

        result = self._run_command(args)

        # Parse the JSON output to get snapshot ID
        try:
            backup_result = json.loads(result.stdout.strip().split("\n")[-1])
            snapshot_id = backup_result.get("snapshot_id")
            if not snapshot_id:
                raise ResticError("No snapshot ID returned from backup")

            logger.info(f"Backup completed with snapshot ID: {snapshot_id}")
            return snapshot_id, backup_result
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse backup result: {e}")
            logger.error(f"Raw output: {result.stdout}")
            raise ResticError(f"Failed to parse backup result: {e}")

    def _run_backup_streaming(self, args: list[str], progress_callback: callable) -> tuple[str, dict]:
        """Run backup with streaming JSON output for progress updates."""
        cmd = ["restic"] + args
        logger.debug(f"Running restic command (streaming): {' '.join(shlex.quote(arg) for arg in cmd)}")

        summary = {}
        snapshot_id = None

        try:
            process = subprocess.Popen(
                cmd,
                env=self._get_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    msg_type = data.get("message_type", "")

                    if msg_type == "status":
                        # Real-time progress update
                        progress_callback(data)
                    elif msg_type == "summary":
                        # Final summary
                        summary = data
                        snapshot_id = data.get("snapshot_id")
                        progress_callback(data)

                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON output: {line}")

            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read()
                raise ResticError(f"Backup failed: {stderr}")

            if not snapshot_id:
                raise ResticError("No snapshot ID returned from backup")

            return snapshot_id, summary

        except FileNotFoundError:
            raise ResticError("Restic binary not found. Please install restic first.")

    def list_snapshots(
        self, tags: list[str] = None, paths: list[str] = None
    ) -> list[dict[str, Any]]:
        args = ["snapshots", "--json"]

        if tags:
            for tag in tags:
                args.extend(["--tag", tag])

        if paths:
            for path in paths:
                args.extend(["--path", path])

        result = self._run_command(args)

        try:
            snapshots = json.loads(result.stdout)
            return snapshots if snapshots else []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse snapshots list: {e}")
            return []

    def restore(
        self,
        snapshot_id: str,
        target_path: Path,
        selective_paths: list[str] = None,
        exclude_patterns: list[str] = None,
        include_patterns: list[str] = None,
        verify: bool = True,
    ):
        args = ["restore", snapshot_id, "--target", str(target_path)]

        if selective_paths:
            for path in selective_paths:
                args.extend(["--include", path])

        if exclude_patterns:
            for pattern in exclude_patterns:
                args.extend(["--exclude", pattern])

        if include_patterns:
            for pattern in include_patterns:
                args.extend(["--include", pattern])

        if verify:
            args.append("--verify")

        result = self._run_command(args)
        logger.info(f"Restored snapshot {snapshot_id} to {target_path}")
        return result

    def get_snapshot_info(self, snapshot_id: str) -> dict[str, Any]:
        args = ["snapshots", "--json", snapshot_id]

        result = self._run_command(args)

        try:
            snapshots = json.loads(result.stdout)
            if snapshots:
                return snapshots[0]
            else:
                raise ResticError(f"Snapshot {snapshot_id} not found")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse snapshot info: {e}")
            raise ResticError(f"Failed to parse snapshot info: {e}")

    def forget_snapshots(
        self,
        retention_policy: dict[str, int] = None,
        tags: list[str] = None,
        dry_run: bool = False,
        prune: bool = True,
    ) -> list[str]:
        args = ["forget"]

        if retention_policy:
            for key, value in retention_policy.items():
                args.extend([f"--keep-{key.replace('_', '-')}", str(value)])

        if tags:
            for tag in tags:
                args.extend(["--tag", tag])

        if dry_run:
            args.append("--dry-run")

        if prune:
            args.append("--prune")

        args.append("--json")

        result = self._run_command(args)

        try:
            forget_result = json.loads(result.stdout)
            removed_snapshots = []
            for group in forget_result:
                if "remove" in group:
                    removed_snapshots.extend([snap["id"] for snap in group["remove"]])

            logger.info(f"Removed {len(removed_snapshots)} snapshots")
            return removed_snapshots
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse forget result: {e}")
            return []

    def check_repo(self, read_data: bool = False) -> bool:
        args = ["check"]
        if read_data:
            args.append("--read-data")

        try:
            self._run_command(args)
            logger.info("Repository check passed")
            return True
        except ResticError as e:
            logger.error(f"Repository check failed: {e}")
            return False

    def get_repo_stats(self) -> dict[str, Any]:
        result = self._run_command(["stats", "--json"])

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse repository stats: {e}")
            return {}

    def unlock_repo(self):
        try:
            self._run_command(["unlock"])
            logger.info("Repository unlocked")
        except ResticError as e:
            logger.warning(f"Failed to unlock repository: {e}")

    def resolve_snapshot_ref(self, ref: str) -> str:
        if ref.startswith("snap"):
            return ref

        # Handle special refs like 'latest', 'HEAD'
        if ref in ["latest", "HEAD"]:
            snapshots = self.list_snapshots()
            if not snapshots:
                raise ResticError("No snapshots found")
            return snapshots[-1]["id"]

        # Handle HEAD~n syntax
        if ref.startswith("HEAD~"):
            try:
                offset = int(ref[5:])
                snapshots = self.list_snapshots()
                if len(snapshots) <= offset:
                    raise ResticError(f"Not enough snapshots for {ref}")
                return snapshots[-(offset + 1)]["id"]
            except ValueError:
                raise ResticError(f"Invalid reference format: {ref}")

        # Try to find by tag
        snapshots = self.list_snapshots(tags=[ref])
        if snapshots:
            return snapshots[-1]["id"]

        # Assume it's a snapshot ID
        return ref

    def diff_snapshots(self, snapshot1: str, snapshot2: str) -> dict[str, Any]:
        """Compare two snapshots and return file changes.

        Returns dict with keys: added, removed, modified (lists of file paths)
        """
        args = ["diff", "--json", snapshot1, snapshot2]

        result = self._run_command(args)

        changes = {"added": [], "removed": [], "modified": []}

        try:
            # restic diff outputs JSON lines
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                entry = json.loads(line)

                # restic diff JSON format has 'message_type' for status messages
                # and actual diff entries with 'path' and 'modifier'
                if "path" in entry:
                    modifier = entry.get("modifier", "")
                    path = entry["path"]

                    if modifier == "+":
                        changes["added"].append(path)
                    elif modifier == "-":
                        changes["removed"].append(path)
                    elif modifier == "M":
                        changes["modified"].append(path)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse diff output: {e}")

        return changes

    def ls_snapshot(self, snapshot_id: str, path: str = "") -> list[dict[str, Any]]:
        """List files in a snapshot."""
        args = ["ls", "--json", snapshot_id]
        if path:
            args.append(path)

        result = self._run_command(args)

        files = []
        try:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                entry = json.loads(line)
                # Skip the snapshot header entry
                if entry.get("struct_type") == "snapshot":
                    continue
                files.append(entry)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse ls output: {e}")

        return files

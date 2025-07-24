import subprocess
import sys
from pathlib import Path

from loguru import logger


class KeychainManager:
    """Manage Restic passwords using macOS Keychain"""

    def __init__(self, service_name: str = "restic-backup"):
        self.service_name = service_name

    def store_password(self, account_name: str, password: str) -> bool:
        """Store password in macOS Keychain"""
        try:
            cmd = [
                "security",
                "add-generic-password",
                "-s",
                self.service_name,
                "-a",
                account_name,
                "-w",
                password,
                "-U",  # Update if exists
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Password stored in keychain for {account_name}")
                return True
            else:
                logger.error(f"Failed to store password: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Keychain storage failed: {e}")
            return False

    def get_password(self, account_name: str) -> str | None:
        """Retrieve password from macOS Keychain"""
        try:
            cmd = [
                "security",
                "find-generic-password",
                "-s",
                self.service_name,
                "-a",
                account_name,
                "-w",  # Return password only
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Failed to retrieve password: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Keychain retrieval failed: {e}")
            return None

    def delete_password(self, account_name: str) -> bool:
        """Delete password from macOS Keychain"""
        try:
            cmd = [
                "security",
                "delete-generic-password",
                "-s",
                self.service_name,
                "-a",
                account_name,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Keychain deletion failed: {e}")
            return False


def migrate_existing_password():
    """Interactive migration of existing password to keychain"""
    import getpass

    keychain = KeychainManager()

    print("🔐 Migrating Restic password to macOS Keychain")
    print("This is more secure than environment variables or config files.\n")

    # Get repository path
    repo_path = input("Enter your Restic repository path: ").strip()
    if not repo_path:
        repo_path = "/Volumes/Crucial2506/restic-backup"
        print(f"Using default: {repo_path}")

    # Get current password securely
    password = getpass.getpass("Enter your current Restic password: ")

    # Create account name from repo path
    account_name = Path(repo_path).name or "default"

    # Store in keychain
    if keychain.store_password(account_name, password):
        print(f"✅ Password stored in keychain as '{account_name}'")

        # Create updated config
        config_data = {
            "name": "migrated-backup",
            "source_paths": [str(Path.home() / "Documents"), str(Path.home() / "Projects")],
            "restic_repo": repo_path,
            "keychain_account": account_name,  # New field
            "schedule": "1h",
            "retention": {
                "keep_last": 10,
                "keep_hourly": 24,
                "keep_daily": 7,
                "keep_weekly": 4,
                "keep_monthly": 12,
                "keep_yearly": 5,
            },
            "exclude_patterns": [
                "*.tmp",
                "*.log",
                ".DS_Store",
                "__pycache__",
                "node_modules",
                ".git",
                "*.cache",
            ],
        }

        print("\n📝 Suggested backup_config.json:")
        import json

        print(json.dumps(config_data, indent=2))

        print("\n🚀 You can now remove these environment variables:")
        print("unset RESTIC_REPOSITORY")
        print("unset RESTIC_PASSWORD")

    else:
        print("❌ Failed to store password in keychain")
        sys.exit(1)


if __name__ == "__main__":
    migrate_existing_password()

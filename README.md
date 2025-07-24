# Enhanced Restic Backup Manager

A comprehensive backup solution for macOS folders with Restic versioning, real-time monitoring, and automated retention policies. This project provides Git-like semantics on top of Restic's robust backup engine.

## Features

🔐 **Secure by Default**: Built on Restic's proven encryption  
🚀 **Git-like Interface**: Familiar commands like `snapshot`, `log`, `restore`, `show`  
⚡ **Real-time Monitoring**: Automatic backups triggered by file changes  
📅 **Flexible Scheduling**: Configurable backup intervals  
🎯 **Smart Retention**: Automatic cleanup with granular policies  
🔍 **Rich Metadata**: Track changes with detailed commit-like messages  
🎨 **Beautiful CLI**: Rich terminal UI with progress indicators  

## Quick Start

### Prerequisites

1. Install [Restic](https://restic.net/):
   ```bash
   brew install restic  # macOS
   ```

2. Install this package:
   ```bash
   uv sync
   ```

### Migrate from Existing Restic Setup

If you already have a Restic repository with environment variables:

```bash
# OLD insecure method:
export RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
export RESTIC_PASSWORD='<PWD>'

# NEW secure migration:
python -m src.cli migrate --repo-path /Volumes/Crucial2506/restic-backup
```

This will:
- Store your password securely in macOS Keychain
- Create a `backup_config.json` with your settings
- Preserve all existing snapshots

### For New Setup

```bash
backup init-config
```

This creates a `backup_config.json` file with your backup settings.

### Create Your First Snapshot

```bash
# With a descriptive message (Git-like)
python -m src.cli snapshot -m "Monthly accounting backup"

# With tags for organization
python -m src.cli snapshot -m "Project files updated" --tag work --tag important
```

### View Backup History

```bash
# Recent snapshots (Git-like log)
python -m src.cli log

# Show details of specific snapshot
python -m src.cli show latest
python -m src.cli show HEAD~2

# Search through history
python -m src.cli search "accounting"
```

### Restore Files

```bash
# Restore entire snapshot
python -m src.cli restore latest ~/restored-files

# Restore specific files only
python -m src.cli restore latest ~/restore --path "Documents/important.txt"
```

## Usage Examples

### Basic Operations

```bash
# Create a snapshot with a message
python -m src.cli snapshot -m "Added new project files" --tag work

# View recent backups (Git-like log)
python -m src.cli log --limit 5

# Show details of a specific snapshot
python -m src.cli show latest
python -m src.cli show HEAD~2

# Search through backup history
python -m src.cli search "project files"

# Check backup status
python -m src.cli status

# Restore specific files
python -m src.cli restore latest ~/restore --path "Documents/important.txt"

# Apply retention policy
python -m src.cli forget --dry-run  # See what would be deleted
python -m src.cli forget             # Actually delete old backups
```

### Real-World Example (Based on Working Setup)

```bash
# Current working configuration
cat backup_config.json
{
  "name": "crucial-ssd-backup",
  "source_paths": [
    "/Users/z/_MBJ/accounting",
    "/Users/z/_MBJ/management",
    "/Users/z/_MBJ/ongoing", 
    "/Users/z/_MBJ/staff"
  ],
  "restic_repo": "/Volumes/Crucial2506/restic-backup",
  "keychain_account": "restic-backup"
}

# Create monthly backup
python -m src.cli snapshot -m "July 2025 business records backup"

# View history with rich output
python -m src.cli log
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━┓
┃ ID       ┃ Date               ┃ Author ┃ Message            ┃ Tags ┃ Changes ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━┩
│ 57e6e292 │ 2025-07-24 15:48:21│ z      │ July 2025 business │ -    │  24718  │
│          │                    │        │ records backup     │      │         │
└──────────┴────────────────────┴────────┴────────────────────┴──────┴─────────┘

# Check repository health
python -m src.cli status
╭──────────────── Backup Status ─────────────────╮
│ Repository: /Volumes/Crucial2506/restic-backup │
│ Health: ✅ Healthy                             │
│ Total snapshots: 4                             │
│ Working directory clean                        │
╰────────────────────────────────────────────────╯
```

### Keychain Management

```bash
# Store password securely
python -m src.cli keychain store restic-backup

# Test retrieval (for debugging)
python -m src.cli keychain get restic-backup

# Remove password if needed
python -m src.cli keychain delete restic-backup
```

### Daemon Mode (Continuous Monitoring)

```bash
# Run with automatic monitoring and scheduled backups
python src/main.py daemon
```

## Configuration

The `backup_config.json` file controls all backup behavior:

```json
{
  "name": "crucial-ssd-backup",
  "source_paths": [
    "/Users/z/_MBJ/accounting",
    "/Users/z/_MBJ/management",
    "/Users/z/_MBJ/ongoing",
    "/Users/z/_MBJ/staff"
  ],
  "restic_repo": "/Volumes/Crucial2506/restic-backup",
  "keychain_account": "restic-backup", 
  "schedule": "1h",
  "retention": {
    "keep_last": 10,
    "keep_hourly": 24,
    "keep_daily": 7,
    "keep_weekly": 4,
    "keep_monthly": 12,
    "keep_yearly": 5
  },
  "exclude_patterns": [
    "*.tmp",
    "*.log", 
    ".DS_Store",
    "__pycache__",
    "node_modules",
    ".git",
    "*.cache",
    "*.swp",
    ".vscode/settings.json",
    "Thumbs.db",
    "*.pyc",
    ".pytest_cache"
  ]
}
```

### Configuration Options

- **`source_paths`**: Directories to backup (absolute paths recommended)
- **`restic_repo`**: Where to store backup data (can be local or remote)
- **`keychain_account`**: macOS Keychain account for secure password storage
- **`schedule`**: Backup frequency (`1h`, `30m`, `2d`) for daemon mode
- **`retention`**: How long to keep different backup types
- **`encryption_key_file`**: Alternative to keychain (file-based password)
- **`exclude_patterns`**: Files/folders to skip during backup
- **`include_patterns`**: Override excludes for specific patterns

## Architecture

### Core Components

1. **ModernBackupManager**: Main interface with Git-like semantics
2. **ResticWrapper**: Python interface to Restic CLI
3. **MetadataStore**: SQLite-based storage for rich snapshot metadata
4. **FileMonitor**: Real-time file change detection with Watchdog
5. **ScheduledBackupService**: Automated backup scheduling

### Git-like References

The system supports Git-style references:

- `latest` or `HEAD`: Most recent snapshot
- `HEAD~1`, `HEAD~2`: Previous snapshots  
- `tag-name`: Snapshots with specific tags
- `snap-12345678`: Direct snapshot ID

## Development

### Setup

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check src/
uv run ruff format src/

# Run the CLI in development
python -m src.cli --help

# Test with your actual repository
python -m src.cli status
python -m src.cli log
```

### Project Structure

```
src/
├── models.py          # Data models and configuration
├── backup_manager.py  # Main backup orchestration  
├── restic_wrapper.py  # Restic CLI interface
├── metadata_store.py  # SQLite metadata storage
├── monitor.py         # File monitoring and scheduling
├── cli.py            # Command-line interface
└── main.py           # Entry point
```

## Why This Approach?

### Restic + Python Enhancement

- **Proven Backup Tool**: Restic is battle-tested for backups
- **Git Semantics**: Familiar interface for developers  
- **Better Performance**: Restic's incremental backup is superior
- **Security by Default**: Encryption without extra setup
- **Simpler Maintenance**: One primary tool with Python enhancements

### Compared to Alternatives

- **vs Pure Git**: Better for large files, proper backup features
- **vs Time Machine**: Cross-platform, more granular control
- **vs Cloud Backup**: Local control, no vendor lock-in
- **vs rsync**: Version history, encryption, deduplication

## Requirements

- **Python**: 3.12+
- **Restic**: Latest version
- **macOS**: Primary target (Linux/Windows compatible)
- **Dependencies**: Click, Rich, Watchdog, Pydantic, Loguru

## License

MIT License - see LICENSE file for details.

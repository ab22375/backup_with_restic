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

2. Install [uv](https://github.com/astral-sh/uv) (modern Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install this package:
   ```bash
   uv sync
   ```

### Environment Setup with direnv (Recommended)

This project includes `.envrc` for automatic virtual environment activation using [direnv](https://direnv.net/).

**One-time setup:**
```bash
# Install direnv (if not already installed)
brew install direnv  # macOS

# Add direnv hook to your shell (~/.zshrc or ~/.bashrc)
eval "$(direnv hook zsh)"   # For zsh
# OR
eval "$(direnv hook bash)"  # For bash

# Allow direnv to activate the .envrc in this project
cd /path/to/backup_with_restic
direnv allow
```

**With direnv active**, the virtual environment activates automatically when you `cd` into the project directory, so you can run commands directly:
```bash
python -m src.cli log      # No "uv run" prefix needed!
python -m src.cli status
```

**Without direnv**, use the `uv run` prefix:
```bash
uv run python -m src.cli log
uv run python -m src.cli status
```

#### Shared Virtual Environment Configuration

The `.envrc` is configured to use a shared virtual environment:
```bash
# .envrc contents:
export UV_PROJECT_ENVIRONMENT=$HOME/.venv-shared
unset VIRTUAL_ENV
source $UV_PROJECT_ENVIRONMENT/bin/activate
```

This means:
- Dependencies are installed in `~/.venv-shared` instead of project-local `.venv`
- Multiple projects can share the same environment
- Faster setup when switching between projects with similar dependencies

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

# Remove stale repository locks
python -m src.cli unlock

# Restore specific files
python -m src.cli restore latest ~/restore --path "Documents/important.txt"

# Apply retention policy
python -m src.cli forget --dry-run  # See what would be deleted
python -m src.cli forget             # Actually delete old backups
```

**Note:** Examples assume direnv is active. If not using direnv, prefix all commands with `uv run`.

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

### Exclusion Management (.gitignore-like)

```bash
# Test what files would be excluded/included
python -m src.cli exclude-test
python -m src.cli exclude-test --show-excluded

# Test a specific pattern
python -m src.cli exclude-test --pattern "*.pdf" --show-excluded

# Create .backupignore file (like .gitignore)
python -m src.cli create-backupignore
python -m src.cli create-backupignore /path/to/directory

# View current exclusion analysis
python -m src.cli exclude-test
📊 Exclusion Analysis
✅ Files to include: 46,681
❌ Files to exclude: 0
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
    "# Python",
    "__pycache__", "*.pyc", ".venv", "venv/", ".env", ".pytest_cache",

    "# Node.js",
    "node_modules", ".npm", "dist/", "*.log",

    "# Java",
    "*.class", "target/", ".gradle/", "build/",

    "# C/C++",
    "*.o", "*.so", "*.exe", "*.dll", "CMakeFiles/",

    "# Version Control",
    ".git", ".svn", ".hg", ".bzr",

    "# IDE/Editor",
    ".vscode/settings.json", ".idea/", "*.sublime-workspace",

    "# System files",
    ".DS_Store", "Thumbs.db", "*.tmp", "*.swp", "*.bak",

    "# Large archives (optional)",
    "*.zip", "*.tar.gz", "*.iso", "*.dmg"
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
- **`exclude_patterns`**: Files/folders to skip during backup (supports programming language defaults)
- **`include_patterns`**: Override excludes for specific patterns

## File Exclusion System

### Multiple Exclusion Methods

**1. Configuration File (`backup_config.json`)**
```json
"exclude_patterns": [
  "# Python",
  "__pycache__", "*.pyc", ".venv", ".env",
  "# Node.js",
  "node_modules", ".npm", "dist/",
  "# Version Control",
  ".git", ".svn", ".hg"
]
```

**2. .backupignore Files (Like .gitignore)**
```bash
# Create in any directory
python -m src.cli create-backupignore /path/to/project

# Example .backupignore content:
# .backupignore
*.tmp
*.log
__pycache__/
node_modules/
.venv/
.DS_Store
```

**3. Runtime Pattern Testing**
```bash
# Test exclusion patterns
python -m src.cli exclude-test --show-excluded

# Test specific pattern
python -m src.cli exclude-test --pattern "*.pdf"
```

### Built-in Programming Language Support

The system automatically excludes common development artifacts:

- **Python**: `__pycache__`, `.venv`, `*.pyc`, `.pytest_cache`, `.coverage`
- **Node.js**: `node_modules`, `.npm`, `dist/`, `yarn-error.log`
- **Java**: `*.class`, `target/`, `.gradle/`, `build/`
- **C/C++**: `*.o`, `*.so`, `CMakeFiles/`, `*.exe`
- **Go**: `vendor/`, `*.test`, `*.prof`
- **Rust**: `target/`, `Cargo.lock`
- **Version Control**: `.git`, `.svn`, `.hg`, `.bzr`
- **IDEs**: `.vscode/settings.json`, `.idea/`, `*.sublime-workspace`
- **System**: `.DS_Store`, `Thumbs.db`, `*.tmp`, `*.swp`

### Exclusion Priority

1. **`.backupignore` files** (hierarchical, like .gitignore)
2. **Configuration patterns** (`exclude_patterns`)
3. **Include patterns** (whitelist override)

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

## Shell Integration

### Quick Installation

**Option 1: Use the provided shell script**
```bash
# Add to your ~/.zshrc
echo 'source /Users/z/dev/python/backup_with_restic/shell_integration.sh' >> ~/.zshrc
source ~/.zshrc
```

**Option 2: Manual function setup**

Add this function to your `~/.zshrc` or `~/.bashrc` to use the backup command from anywhere:

```bash
# Add to ~/.zshrc (macOS) or ~/.bashrc (Linux)
backup() {
    local backup_dir="/Users/z/dev/python/backup_with_restic"
    local config_file="$backup_dir/backup_config.json"

    # Change to backup directory and run command
    (cd "$backup_dir" && python -m src.cli --config "$config_file" "$@")
}

# Alternative: Using absolute paths (more robust)
backup() {
    /Users/z/.pyenv/versions/3.12.0/bin/python \
        -m src.cli \
        --config /Users/z/dev/python/backup_with_restic/backup_config.json \
        "$@" 2>/dev/null || \
    (cd /Users/z/dev/python/backup_with_restic && python -m src.cli "$@")
}
```

**After adding to your shell config:**
```bash
# Reload your shell configuration
source ~/.zshrc  # or source ~/.bashrc

# Now use from anywhere:
backup status                    # ✅ Works from any directory
backup snapshot -m "Quick backup from ~/Documents"
backup log
backup restore latest ~/temp
```

### Advanced Shell Function (Recommended)

For a more robust setup with error handling and path detection:

```bash
# Advanced backup function for ~/.zshrc (works with direnv)
backup() {
    local script_dir="/Users/z/dev/python/backup_with_restic"
    local config_file="$script_dir/backup_config.json"

    # Verify script directory exists
    if [[ ! -d "$script_dir" ]]; then
        echo "❌ Backup script directory not found: $script_dir"
        return 1
    fi

    # Verify config file exists
    if [[ ! -f "$config_file" ]]; then
        echo "❌ Config file not found: $config_file"
        echo "💡 Run 'backup init-config' to create one"
        return 1
    fi

    # Change to script directory and run command
    # direnv will automatically activate the .venv when we cd into script_dir
    (cd "$script_dir" && python -m src.cli --config "$config_file" "$@")
}

# Auto-completion for backup commands (optional)
_backup_complete() {
    local commands="snapshot log restore show status search forget exclude-test create-backupignore keychain migrate init-config"
    COMPREPLY=($(compgen -W "$commands" -- "${COMP_WORDS[1]}"))
}
complete -F _backup_complete backup
```

### Usage Examples After Shell Integration

```bash
# From any directory:
cd ~/Documents
backup snapshot -m "Documents updated"

cd ~/Projects/my-app
backup status
backup log --limit 5

# Create .backupignore in current project
backup create-backupignore .

# Test exclusions on current directory's files
backup exclude-test --show-excluded

# Using convenience aliases (from shell_integration.sh)
backup-quick                     # Quick snapshot with current directory message
backup-status                    # Show status
backup-log                      # Show last 10 snapshots
backup-test                     # Test exclusions
backup-ignore                   # Create .backupignore in current directory
```

### Available Commands After Integration

```bash
# Core commands (work from any directory)
backup snapshot -m "message"    # Create snapshot
backup log                      # View history
backup status                   # Repository health
backup unlock                   # Remove stale locks
backup show latest              # Snapshot details
backup restore HEAD~1 ~/temp   # Restore files
backup search "query"           # Search snapshots
backup forget --dry-run        # Preview cleanup

# Exclusion management
backup exclude-test             # Analyze exclusions
backup create-backupignore .    # Create .backupignore
backup exclude-test --pattern "*.log"  # Test pattern

# Security management
backup keychain store account   # Store password
backup migrate --repo-path /path  # Migrate existing setup

# Convenience aliases (if using shell_integration.sh)
backup-quick                    # Quick snapshot from current directory
backup-status                   # Show status
backup-log                      # Last 10 snapshots
backup-test                     # Test exclusions
backup-ignore                   # Create .backupignore here
```

## Development

### Setup

```bash
# Install dependencies
uv sync

# Configure direnv (one-time)
direnv allow

# Run linting (with direnv active)
ruff check src/
ruff format src/

# Or without direnv
uv run ruff check src/
uv run ruff format src/

# Run the CLI in development (with direnv active)
python -m src.cli --help

# Test with your actual repository
python -m src.cli status
python -m src.cli log
```

### Virtual Environment Notes

- **With direnv**: Environment activates automatically when you `cd` into the project
- **Without direnv**: Use `uv run` prefix or manually activate with `source ~/.venv-shared/bin/activate`
- **Shared environment**: Located at `~/.venv-shared` (configured in `.envrc`)
- **Dependencies**: Managed via `pyproject.toml` and installed with `uv sync`

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

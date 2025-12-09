# macOS Backup Manager - Implementation Details

A comprehensive backup solution for macOS folders with Restic versioning, real-time monitoring, and automated retention policies.

## ✅ COMPLETED IMPLEMENTATION

This project has been successfully implemented with all planned features working in production.

### Working Example (Real Setup)

```bash
# Current configuration
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

# Migration from old method (successful)
# OLD: export RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
# OLD: export RESTIC_PASSWORD='<PWD>'
# NEW: Secure keychain storage + Git-like interface

# Working commands
python -m src.cli status        # ✅ Shows 4 snapshots, healthy repo
python -m src.cli log           # ✅ Rich table output with metadata
python -m src.cli show latest   # ✅ Detailed snapshot view with 24K files
python -m src.cli snapshot -m "Monthly backup"  # ✅ Creates new snapshot
```

## Python Dependencies (using uv)

### Installation

```bash
# Install all dependencies
uv sync
```

### Development Environment Setup

This project uses `uv` for package management and `direnv` for automatic virtual environment activation.

**Environment Configuration (`.envrc`):**
```bash
export UV_PROJECT_ENVIRONMENT=.venv
source .venv/bin/activate
```

**Key Points:**
- Dependencies are installed in `.venv` (local to this project)
- `direnv` automatically activates the environment when entering the project directory
- No need for `uv run` prefix when direnv is active

**Package Management:**
```bash
# Add a new dependency
uv add <package-name>

# Install/sync all dependencies
uv sync

# Run commands without direnv
uv run python -m src.cli <command>

# Run commands with direnv (automatic activation)
python -m src.cli <command>
```

**Dependencies (defined in `pyproject.toml`):**
- rich>=14.0.0
- click>=8.2.1
- pydantic>=2.11.7
- watchdog>=6.0.0
- gitpython>=3.1.45
- python-dotenv>=1.1.1
- ruff>=0.12.4
- loguru>=0.7.3

## Architecture Overview (IMPLEMENTED)

```python
# Core Components (all working)
@dataclass
class BackupConfig:
    name: str
    source_paths: List[Path]
    restic_repo: Path
    schedule: str
    retention: RetentionPolicy
    keychain_account: Optional[str] = None  # ✅ NEW: Secure keychain support
    encryption_key_file: Optional[Path] = None

class ModernBackupManager:
    def __init__(self, config: BackupConfig):
        self.config = config
        self.restic = ResticWrapper(
            config.restic_repo,
            keychain_account=config.keychain_account  # ✅ Keychain integration
        )
        self.metadata_store = MetadataStore(config.restic_repo / "metadata")

    def snapshot(self, message: str = None, tags: List[str] = None):
        """✅ WORKING: Create a snapshot with Git-like semantics"""
        # Pre-backup validation
        self._validate_sources()

        # Create restic snapshot with keychain authentication
        snapshot_id = self.restic.backup(
            paths=self.config.source_paths,
            tags=tags or []
        )

        # Store rich metadata (like Git commits)
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            message=message,
            timestamp=datetime.now(),
            author=getpass.getuser(),
            tags=tags,
            file_changes=self._detect_changes()
        )
        self.metadata_store.save(metadata)  # ✅ SQLite storage working

        return snapshot_id

    def log(self, limit: int = 10) -> List[SnapshotMetadata]:
        """✅ WORKING: Git-like log of snapshots"""
        return self.metadata_store.get_recent(limit)

    def restore(self, ref: str, target: Path, selective_paths: List[str] = None):
        """✅ WORKING: Restore with Git-like reference support"""
        snapshot_id = self._resolve_ref(ref)  # Support HEAD~1, tags, etc.
        self.restic.restore(snapshot_id, target, selective_paths)
```

## Key Features (ALL IMPLEMENTED)

✅ **Proven backup tool** - Restic is battle-tested for backups
✅ **Python layer adds Git semantics** - Familiar interface for developers
✅ **Better performance** - Restic's incremental backup is superior
✅ **Security by default** - macOS Keychain encryption without extra setup
✅ **Simpler maintenance** - One primary tool with Python enhancements
✅ **Rich metadata** - SQLite storage for Git-like commit messages
✅ **Real-time monitoring** - Watchdog file system events
✅ **Beautiful CLI** - Rich terminal UI with tables and progress bars
✅ **Real-time progress** - Live file/data counts during backup
✅ **Backup verification** - Integrity checks with partial/full data verification
✅ **Debug mode** - `--debug` flag for detailed logging when troubleshooting

## Production Usage

```bash
# Secure migration completed
python -m src.cli migrate --repo-path /Volumes/Crucial2506/restic-backup

# Daily operations (snapshot shows real-time progress)
python -m src.cli snapshot -m "Daily business backup" --tag work
python -m src.cli log                    # View history
python -m src.cli status                 # Health check
python -m src.cli show latest           # Detailed view
python -m src.cli restore HEAD~1 ~/temp # Quick restore
python -m src.cli unlock                 # Remove stale repository locks

# Verify backup integrity
python -m src.cli verify                        # Quick structure check
python -m src.cli verify --read-data-subset 5%  # Verify 5% of data (recommended monthly)
python -m src.cli verify --read-data            # Full data verification (slow)

# Exclusion management (.gitignore-like)
python -m src.cli exclude-test           # Analyze what's excluded
python -m src.cli exclude-test --show-excluded  # Show excluded files
python -m src.cli create-backupignore /path/to/project  # Create .backupignore

# Maintenance
python -m src.cli forget --dry-run      # Check retention
python -m src.cli forget                # Apply cleanup

# Debug mode (show detailed logs)
python -m src.cli --debug snapshot -m "Debug backup"
```

## Security Improvements

### OLD Method (Insecure)
```bash
export RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
export RESTIC_PASSWORD='<PWD>'  # ❌ Visible in process list, shell history
restic backup /Users/z/_MBJ/accounting
```

### NEW Method (Secure)
```bash
# One-time setup
python -m src.cli keychain store restic-backup  # ✅ macOS Keychain encryption

# Daily usage
python -m src.cli snapshot -m "Accounting backup"  # ✅ Password auto-retrieved
```

## File Structure (Created)
```
src/
├── models.py          # ✅ Data models and configuration
├── backup_manager.py  # ✅ Main backup orchestration + exclusion system
├── restic_wrapper.py  # ✅ Restic CLI interface with keychain
├── metadata_store.py  # ✅ SQLite metadata storage
├── monitor.py         # ✅ File monitoring and scheduling
├── cli.py            # ✅ Command-line interface with Rich UI + exclusion commands
├── keychain_helper.py # ✅ macOS Keychain integration
└── main.py           # ✅ Entry point

backup_config.json     # ✅ Working configuration with comprehensive exclusions
.backupignore          # ✅ .gitignore-like exclusion files
.envrc                 # ✅ direnv configuration for auto venv activation
pyproject.toml         # ✅ uv package dependencies and project config
example_config.json    # ✅ Template
MIGRATION_GUIDE.md     # ✅ Security migration guide
README.md              # ✅ User documentation
CLAUDE.md              # ✅ AI context and implementation details
```

## Testing Results

✅ Repository health: Healthy
✅ Total snapshots: 39+
✅ Keychain authentication: Working
✅ File processing: 46,681+ files analyzed
✅ Exclusion system: Comprehensive programming language defaults
✅ .backupignore support: Hierarchical exclusion files working
✅ Rich CLI output: Tables, progress bars, colors
✅ Git-like references: HEAD, HEAD~1, latest, tags
✅ Migration: Successful from environment variables
✅ Exclusion commands: exclude-test, create-backupignore working
✅ Real-time progress: Live file/byte counts during backup
✅ Backup verification: Structure and data integrity checks
✅ Debug mode: Detailed logging with --debug flag

## Status: PRODUCTION READY

This is a COMPLETED implementation. All features are working in production with real data:
- ✅ **Secure keychain storage** implemented and tested
- ✅ **Git-like interface** fully functional (snapshot, log, restore, show)
- ✅ **Rich metadata tracking** with SQLite storage
- ✅ **Beautiful CLI** with Rich library (tables, progress bars, colors)
- ✅ **Real-time backup progress** showing files/bytes processed
- ✅ **Backup verification** with quick, partial, and full data checks
- ✅ **Debug mode** via `--debug` flag for troubleshooting
- ✅ **Comprehensive exclusion system** (.backupignore + config patterns)
- ✅ **Programming language defaults** (Python, Node.js, Java, C/C++, Go, Rust)
- ✅ **Real backup repository migration** successful from environment variables
- ✅ **File monitoring and scheduling** with Watchdog
- ✅ **All CLI commands** working: migrate, snapshot, log, show, restore, status, search, forget, unlock, verify, exclude-test, create-backupignore
- ✅ **Production tested** with 46,681+ files analyzed and backed up

## Latest Enhancement: Enterprise-Grade Exclusion System

```bash
# Configuration-based exclusions (100+ programming language defaults)
"exclude_patterns": ["__pycache__", "node_modules", ".git", "target/", "*.pyc", ...]

# .backupignore files (hierarchical, like .gitignore)
python -m src.cli create-backupignore /path/to/project

# Exclusion testing and analysis
python -m src.cli exclude-test --show-excluded
📊 Exclusion Analysis
✅ Files to include: 46,681
❌ Files to exclude: 0
```

## Development Environment Configuration

### direnv + Local Virtual Environment

The project is configured for automatic environment activation using a local `.venv` directory:

**Project `.envrc`:**
```bash
export UV_PROJECT_ENVIRONMENT=.venv
source .venv/bin/activate
```

**Benefits:**
- ✅ Automatic venv activation when entering project directory
- ✅ Local dependencies isolated to this project (.venv)
- ✅ No need for `uv run` prefix in commands
- ✅ Seamless integration with uv package manager
- ✅ One-time `direnv allow` per project

**Workflow:**
```bash
cd /path/to/backup_with_restic  # direnv auto-activates venv
python -m src.cli log           # Works immediately, no prefix needed
uv add new-package              # Add dependencies easily
uv sync                         # Sync dependencies
```

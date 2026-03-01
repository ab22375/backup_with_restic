# Disaster Recovery Guide

How to restore your backups if your current Mac is lost, damaged, or replaced.

## What You Need

1. **The external drive** — `/Volumes/Crucial2506/restic-backup` (the restic repository)
2. **The repository password** — stored in macOS Keychain under service `restic-backup`, account `restic-backup`

**CRITICAL: Write down your restic password and store it somewhere safe (password manager, printed copy in a safe, etc.). Without it, the backup data is unrecoverable.**

To retrieve your current password:
```bash
security find-generic-password -s restic-backup -a restic-backup -w
```

---

## Recovery on a New Mac

### Step 1: Install restic

```bash
brew install restic
```

### Step 2: Connect the backup drive

Plug in the Crucial SSD. It should mount at `/Volumes/Crucial2506`.

### Step 3: Verify repository access

```bash
# Set password (enter when prompted)
restic -r /Volumes/Crucial2506/restic-backup snapshots
```

Or to avoid repeated prompts:
```bash
export RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
export RESTIC_PASSWORD='your-password-here'
restic snapshots
```

### Step 4: Browse and restore

```bash
# List all snapshots
restic snapshots

# See what's in the latest snapshot
restic ls latest

# Restore everything to a target directory
restic restore latest --target ~/restored-backup

# Restore specific paths only
restic restore latest --target ~/restored-backup --include "/Users/z/_MBJ"
restic restore latest --target ~/restored-backup --include "/Users/z/dev"

# Restore a specific older snapshot (use ID from `restic snapshots`)
restic restore abc12345 --target ~/restored-backup
```

### Step 5: (Optional) Set up the Python backup tool again

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or copy the backup tool project
cd ~/dev/python/backup_with_restic
uv sync

# Store password in keychain
python -m src.cli keychain store restic-backup

# Edit backup_config.json to match new paths if needed
# Then test
python -m src.cli status
python -m src.cli log
```

---

## Recovery on Ubuntu Linux

Yes, restic repositories are fully cross-platform. The backup data is not tied to macOS.

### Step 1: Install restic

```bash
# Ubuntu/Debian
sudo apt install restic

# Or get the latest version
wget https://github.com/restic/restic/releases/latest/download/restic_0.17.3_linux_amd64.bz2
bunzip2 restic_*.bz2
chmod +x restic_*
sudo mv restic_* /usr/local/bin/restic
```

### Step 2: Mount the drive

```bash
# Find the drive
lsblk

# Mount it (exFAT or HFS+ depending on format)
sudo mount /dev/sdX1 /mnt/crucial

# For HFS+ (macOS-formatted) drives, you may need:
sudo apt install hfsprogs
sudo mount -t hfsplus -o ro /dev/sdX1 /mnt/crucial

# For APFS drives (newer macOS default):
# APFS is not natively supported on Linux — use linux-apfs-rw driver
# or reformat the backup drive as exFAT for cross-platform use
```

### Step 3: Restore

```bash
export RESTIC_REPOSITORY=/mnt/crucial/restic-backup
export RESTIC_PASSWORD='your-password-here'

restic snapshots
restic restore latest --target ~/restored-backup
```

**Note:** File permissions and macOS-specific metadata (xattrs, resource forks) may not be preserved on Linux. The file contents will be intact.

---

## Recovery on Windows

Also fully supported.

### Step 1: Install restic

```powershell
# Using scoop
scoop install restic

# Or winget
winget install restic

# Or download from https://github.com/restic/restic/releases
```

### Step 2: Connect the drive

Plug in the Crucial SSD. It will appear as a drive letter (e.g., `E:\`).

**Note:** If the drive is formatted as HFS+ or APFS (macOS-native), Windows cannot read it natively. Options:
- Use [Paragon HFS+ for Windows](https://www.paragon-software.com/home/hfs-windows/) (paid)
- Use [MacDrive](https://www.macdrive.com/) (paid)
- Boot a Linux live USB and restore from there instead

If the drive is exFAT, it works natively on Windows.

### Step 3: Restore

```powershell
$env:RESTIC_REPOSITORY = "E:\restic-backup"
$env:RESTIC_PASSWORD = "your-password-here"

restic snapshots
restic restore latest --target C:\restored-backup
```

---

## Drive Format Recommendations

Your backup drive's filesystem determines cross-platform access:

| Format | macOS | Linux | Windows | Max File Size |
|--------|-------|-------|---------|---------------|
| **exFAT** | Native | Native | Native | 16 EB |
| **APFS** | Native | Difficult | No | 8 EB |
| **HFS+** | Native | Read-only* | No* | 8 EB |

**Recommendation:** If you want easy cross-platform recovery, format the backup drive as **exFAT**. Check your current format:

```bash
diskutil info /Volumes/Crucial2506 | grep "File System"
```

If it's APFS/HFS+ and you want cross-platform access, you can reformat (after ensuring you have the data elsewhere):
```bash
# WARNING: This erases the drive
diskutil eraseDisk ExFAT Crucial2506 /dev/diskN
# Then re-initialize: restic init -r /Volumes/Crucial2506/restic-backup
```

---

## Quick Reference

| Task | Command |
|------|---------|
| List snapshots | `restic -r /path/to/repo snapshots` |
| Browse files in snapshot | `restic -r /path/to/repo ls latest` |
| Restore everything | `restic -r /path/to/repo restore latest --target ~/restore` |
| Restore one folder | `restic -r /path/to/repo restore latest --target ~/restore --include "/Users/z/dev"` |
| Mount as filesystem | `restic -r /path/to/repo mount /mnt/restic` (macOS/Linux only) |
| Check repo integrity | `restic -r /path/to/repo check` |
| Find a file | `restic -r /path/to/repo find "filename.txt"` |

## Summary

- Restic repos are **fully cross-platform** (macOS, Linux, Windows)
- You only need **restic + the drive + the password**
- No need for this Python tool to restore — raw `restic` commands work
- The Python tool is a convenience layer; restic itself does all the heavy lifting
- **Store your password somewhere safe outside this computer**

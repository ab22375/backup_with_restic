# Migration Guide: Secure Your Existing Restic Setup

This guide helps you migrate from environment variables to secure password management.

## Current Setup (Insecure)
```bash
export RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
export RESTIC_PASSWORD='<PWD>'
```

## Recommended Solutions (Secure)

### Option 1: macOS Keychain (Most Secure) ⭐

**Advantages:**
- Passwords encrypted by macOS 
- No plaintext files
- Integrated with system security
- Works with Touch ID/Face ID

**Quick Migration:**
```bash
# Run the migration helper
backup migrate --repo-path /Volumes/Crucial2506/restic-backup

# Or do it manually
backup keychain store restic-backup
# Enter password: <PWD>

# Remove old environment variables
unset RESTIC_REPOSITORY
unset RESTIC_PASSWORD
```

**Your config will look like:**
```json
{
  "name": "restic-backup",
  "restic_repo": "/Volumes/Crucial2506/restic-backup",
  "keychain_account": "restic-backup",
  ...
}
```

### Option 2: Secure Password File

**Create password file:**
```bash
# Create secure directory
mkdir -p ~/.backup
chmod 700 ~/.backup

# Store password securely
echo '<PWD>' > ~/.backup/restic-password
chmod 600 ~/.backup/restic-password
```

**Your config:**
```json
{
  "name": "restic-backup", 
  "restic_repo": "/Volumes/Crucial2506/restic-backup",
  "encryption_key_file": "~/.backup/restic-password",
  ...
}
```

### Option 3: Environment File (.env)

**Create .env file:**
```bash
# .env file (add to .gitignore!)
RESTIC_REPOSITORY=/Volumes/Crucial2506/restic-backup
RESTIC_PASSWORD=<PWD>
```

**Load automatically:**
```bash
# Add to your shell profile (.zshrc, .bashrc)
if [ -f ~/.backup/.env ]; then
    export $(cat ~/.backup/.env | xargs)
fi
```

## Step-by-Step Migration

### Step 1: Test Current Setup
```bash
# Verify your current setup works
restic -r /Volumes/Crucial2506/restic-backup snapshots
```

### Step 2: Migrate Password
```bash
# Option A: Use migration helper (recommended)
backup migrate

# Option B: Manual keychain setup
backup keychain store restic-backup
# Enter: <PWD>

# Option C: Create password file
mkdir -p ~/.backup
echo '<PWD>' > ~/.backup/restic-password
chmod 600 ~/.backup/restic-password
```

### Step 3: Create Configuration
```bash
# Initialize config (will prompt for details)
backup init-config

# Or use migrate command which creates config automatically
backup migrate
```

### Step 4: Test New Setup
```bash
# Test connection
backup status

# List existing snapshots
backup log
```

### Step 5: Clean Up
```bash
# Remove old environment variables
unset RESTIC_REPOSITORY
unset RESTIC_PASSWORD

# Remove from shell profile if set there
# Edit ~/.zshrc or ~/.bashrc and remove the export lines
```

## Security Comparison

| Method | Security | Convenience | Platform |
|--------|----------|-------------|----------|
| **Environment Variables** | ⚠️ Poor | ✅ Easy | All |
| **Keychain** | ✅ Excellent | ✅ Easy | macOS only |
| **Password File** | ✅ Good | ✅ Easy | All |
| **Environment File** | ⚠️ Moderate | ✅ Easy | All |

## Troubleshooting

### Keychain Issues
```bash
# List all restic passwords in keychain
security find-generic-password -s restic-backup

# Delete if needed
backup keychain delete restic-backup

# Test retrieval
backup keychain get restic-backup
```

### Permission Issues
```bash
# Fix password file permissions
chmod 600 ~/.backup/restic-password

# Fix directory permissions  
chmod 700 ~/.backup
```

### Repository Access
```bash
# Test repository access
backup status

# Check restic directly
restic -r /Volumes/Crucial2506/restic-backup check
```

## Best Practices

1. **Never store passwords in:**
   - Shell history
   - Git repositories
   - Configuration files in plaintext
   - Environment variables in production

2. **Always:**
   - Use keychain on macOS
   - Set restrictive file permissions (600)
   - Test after migration
   - Keep backups of your configuration

3. **Regular maintenance:**
   - Rotate passwords periodically
   - Audit keychain entries
   - Monitor backup logs

## Next Steps

After migration:
1. Create your first snapshot: `backup snapshot -m "Post-migration test"`
2. Set up monitoring: `python src/main.py daemon`
3. Configure retention policies in your config
4. Schedule regular backups

## Need Help?

- Test keychain: `backup keychain get restic-backup`
- Check config: `backup status`  
- View snapshots: `backup log`
- Get help: `backup --help`
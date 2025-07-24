#!/bin/bash
# Shell integration for Enhanced Restic Backup Manager
# Add this to your ~/.zshrc or ~/.bashrc

# Enhanced backup function with error handling and auto-completion
backup() {
    local script_dir="/Users/z/dev/python/backup_with_restic"
    local config_file="$script_dir/backup_config.json"


    # Verify script directory exists
    if [[ ! -d "$script_dir" ]]; then
        echo "❌ Backup script directory not found: $script_dir"
        echo "💡 Update the script_dir path in your shell function"
        return 1
    fi

    # Verify config file exists
    if [[ ! -f "$config_file" ]]; then
        echo "❌ Config file not found: $config_file"
        echo "💡 Run 'backup init-config' to create one"
        return 1
    fi

    # Show current directory context for better UX
    if [[ "$1" == "snapshot" && "$PWD" != "$script_dir" ]]; then
        echo "📁 Running backup from: $PWD"
    fi

    # Change to script directory and run command
    # direnv will automatically activate the .venv when we cd into script_dir
    (cd "$script_dir" && python -m src.cli --config "$config_file" "$@")

    # Store exit code to preserve it
    local exit_code=$?

    # Show helpful message for common commands
    if [[ $exit_code -eq 0 ]]; then
        case "$1" in
            "snapshot")
                echo "✅ Snapshot created successfully"
                ;;
            "status")
                echo "💡 Use 'backup log' to see recent snapshots"
                ;;
        esac
    fi

    return $exit_code
}

# Auto-completion for backup commands
_backup_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local commands="snapshot log restore show status search forget exclude-test create-backupignore keychain migrate init-config"

    # Complete subcommands for keychain
    if [[ "${COMP_WORDS[1]}" == "keychain" ]]; then
        local keychain_commands="store get delete"
        COMPREPLY=($(compgen -W "$keychain_commands" -- "$cur"))
        return
    fi

    # Complete main commands
    COMPREPLY=($(compgen -W "$commands" -- "$cur"))
}

# Register completion function
complete -F _backup_complete backup

# Aliases for common operations
alias backup-quick='backup snapshot -m "Quick backup from $PWD"'
alias backup-status='backup status'
alias backup-log='backup log --limit 10'
alias backup-test='backup exclude-test'

# Helper function to create .backupignore in current directory
backup-ignore() {
    backup create-backupignore .
    echo "💡 Edit .backupignore to customize exclusions for this directory"
}

echo "🚀 Enhanced Restic Backup Manager loaded!"
echo "   Commands: backup snapshot, backup log, backup status, backup restore"
echo "   Aliases: backup-quick, backup-status, backup-log, backup-test"
echo "   Helper: backup-ignore (creates .backupignore in current directory)"

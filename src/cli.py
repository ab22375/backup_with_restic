import json
from pathlib import Path

import click
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from .backup_manager import ModernBackupManager
from .keychain_helper import KeychainManager
from .models import BackupConfig, RetentionPolicy

console = Console()


def load_config(config_path: Path) -> BackupConfig:
    if not config_path.exists():
        raise click.ClickException(f"Configuration file not found: {config_path}")

    try:
        with open(config_path) as f:
            config_data = json.load(f)

        return BackupConfig(
            name=config_data["name"],
            source_paths=[Path(p) for p in config_data["source_paths"]],
            restic_repo=Path(config_data["restic_repo"]),
            schedule=config_data.get("schedule", ""),
            retention=RetentionPolicy(**config_data.get("retention", {})),
            encryption_key_file=Path(config_data["encryption_key_file"])
            if config_data.get("encryption_key_file")
            else None,
            keychain_account=config_data.get("keychain_account"),
            exclude_patterns=config_data.get("exclude_patterns", []),
            include_patterns=config_data.get("include_patterns", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        raise click.ClickException(f"Invalid configuration file: {e}")


@click.group()
@click.option("--config", "-c", default="backup_config.json", help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, config, verbose):
    if verbose:
        logger.add(lambda msg: console.print(msg, style="dim"))

    ctx.ensure_object(dict)
    ctx.obj["config_path"] = Path(config)


@cli.command()
@click.option("--message", "-m", help="Snapshot message")
@click.option("--tag", multiple=True, help="Tags for the snapshot")
@click.option("--no-validate", is_flag=True, help="Skip source validation")
@click.pass_context
def snapshot(ctx, message, tag, no_validate):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Creating snapshot...", total=None)

        try:
            snapshot_id = manager.snapshot(
                message=message, tags=list(tag) if tag else None, validate_sources=not no_validate
            )
            progress.update(task, description="Snapshot created successfully")
            console.print(f"✅ Created snapshot: [bold green]{snapshot_id[:12]}...[/bold green]")

            if message:
                console.print(f"📝 Message: {message}")
            if tag:
                console.print(f"🏷️  Tags: {', '.join(tag)}")

        except Exception as e:
            progress.update(task, description="Snapshot failed")
            console.print(f"❌ Snapshot failed: [bold red]{e}[/bold red]")
            raise click.ClickException(str(e))


@cli.command()
@click.option("--limit", "-n", default=10, help="Number of snapshots to show")
@click.option("--author", help="Filter by author")
@click.option("--tag", multiple=True, help="Filter by tags")
@click.pass_context
def log(ctx, limit, author, tag):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    snapshots = manager.log(limit=limit, author=author, tags=list(tag) if tag else None)

    if not snapshots:
        console.print("No snapshots found")
        return

    table = Table(title="Backup History")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Author", style="green")
    table.add_column("Message", style="white")
    table.add_column("Tags", style="yellow")
    table.add_column("Changes", justify="right")

    for snap in snapshots:
        table.add_row(
            snap.snapshot_id[:8],
            snap.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            snap.author,
            snap.message or "-",
            ", ".join(snap.tags) if snap.tags else "-",
            str(len(snap.file_changes)),
        )

    console.print(table)


@cli.command()
@click.argument("ref")
@click.argument("target")
@click.option("--path", multiple=True, help="Selective paths to restore")
@click.option("--exclude", multiple=True, help="Exclude patterns")
@click.option("--include", multiple=True, help="Include patterns")
@click.option("--verify/--no-verify", default=True, help="Verify restored files")
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
@click.pass_context
def restore(ctx, ref, target, path, exclude, include, verify, overwrite):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    target_path = Path(target)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task(f"Restoring snapshot {ref}...", total=None)

        try:
            manager.restore(
                ref=ref,
                target=target_path,
                selective_paths=list(path) if path else None,
                exclude_patterns=list(exclude) if exclude else None,
                include_patterns=list(include) if include else None,
                verify=verify,
                overwrite=overwrite,
            )
            progress.update(task, description="Restore completed successfully")
            console.print(
                f"✅ Restored snapshot [bold green]{ref}[/bold green] to [bold cyan]{target}[/bold cyan]"
            )

        except Exception as e:
            progress.update(task, description="Restore failed")
            console.print(f"❌ Restore failed: [bold red]{e}[/bold red]")
            raise click.ClickException(str(e))


@cli.command()
@click.argument("ref", default="latest")
@click.pass_context
def show(ctx, ref):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    snapshot = manager.show(ref)
    if not snapshot:
        console.print(f"Snapshot '{ref}' not found")
        return

    # Create a rich display of snapshot info
    info_text = Text()
    info_text.append(f"Snapshot: {snapshot.snapshot_id}\n", style="bold cyan")
    info_text.append(f"Date: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n", style="magenta")
    info_text.append(f"Author: {snapshot.author}\n", style="green")

    if snapshot.message:
        info_text.append(f"Message: {snapshot.message}\n", style="white")

    if snapshot.tags:
        info_text.append(f"Tags: {', '.join(snapshot.tags)}\n", style="yellow")

    if snapshot.parent_snapshot:
        info_text.append(f"Parent: {snapshot.parent_snapshot[:8]}\n", style="dim")

    if snapshot.stats:
        stats = snapshot.stats
        info_text.append(f"Duration: {stats.get('duration_seconds', 0):.2f}s\n", style="blue")
        info_text.append(f"Files changed: {stats.get('files_changed', 0)}\n", style="blue")

    panel = Panel(info_text, title="Snapshot Details", expand=False)
    console.print(panel)

    if snapshot.file_changes:
        table = Table(title="File Changes")
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="white")
        table.add_column("Size", justify="right")

        for change in snapshot.file_changes[:20]:  # Limit to first 20
            size_str = f"{change.size_bytes:,}" if change.size_bytes else "-"
            table.add_row(change.change_type, change.path, size_str)

        if len(snapshot.file_changes) > 20:
            table.add_row("...", f"({len(snapshot.file_changes) - 20} more)", "")

        console.print(table)


@cli.command()
@click.pass_context
def status(ctx):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Getting status...", total=None)

        try:
            status_info = manager.status()
            progress.update(task, description="Status retrieved")

            # Display status information
            status_text = Text()
            status_text.append(f"Repository: {status_info['repository_path']}\n", style="bold cyan")
            status_text.append(
                f"Health: {'✅ Healthy' if status_info['repository_healthy'] else '❌ Issues detected'}\n"
            )
            status_text.append(
                f"Total snapshots: {status_info['total_snapshots']}\n", style="green"
            )

            if status_info["last_snapshot"]:
                last_snap_time = status_info["last_snapshot"].strftime("%Y-%m-%d %H:%M:%S")
                status_text.append(f"Last snapshot: {last_snap_time}\n", style="magenta")

            if status_info["has_uncommitted_changes"]:
                status_text.append(
                    f"Uncommitted changes: {status_info['uncommitted_changes']} files\n",
                    style="yellow",
                )
            else:
                status_text.append("Working directory clean\n", style="green")

            panel = Panel(status_text, title="Backup Status", expand=False)
            console.print(panel)

            # Show recent snapshots
            if status_info["recent_snapshots"]:
                table = Table(title="Recent Snapshots")
                table.add_column("ID", style="cyan")
                table.add_column("Date", style="magenta")
                table.add_column("Author", style="green")
                table.add_column("Message", style="white")

                for snap in status_info["recent_snapshots"]:
                    table.add_row(
                        snap["id"],
                        snap["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        snap["author"],
                        snap["message"] or "-",
                    )

                console.print(table)

        except Exception as e:
            progress.update(task, description="Status check failed")
            console.print(f"❌ Status check failed: [bold red]{e}[/bold red]")


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=20, help="Maximum results to show")
@click.pass_context
def search(ctx, query, limit):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    results = manager.search(query, limit)

    if not results:
        console.print(f"No snapshots found matching '{query}'")
        return

    table = Table(title=f"Search Results for '{query}'")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Author", style="green")
    table.add_column("Message", style="white")
    table.add_column("Tags", style="yellow")

    for snap in results:
        table.add_row(
            snap.snapshot_id[:8],
            snap.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            snap.author,
            snap.message or "-",
            ", ".join(snap.tags) if snap.tags else "-",
        )

    console.print(table)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
@click.pass_context
def forget(ctx, dry_run):
    config = load_config(ctx.obj["config_path"])
    manager = ModernBackupManager(config)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Applying retention policy...", total=None)

        try:
            removed = manager.forget(dry_run=dry_run)
            progress.update(task, description="Retention policy applied")

            if dry_run:
                console.print(f"Would remove {len(removed)} snapshots (dry run)")
            else:
                console.print(f"✅ Removed {len(removed)} snapshots")

            if removed:
                for snapshot_id in removed[:10]:  # Show first 10
                    console.print(f"  - {snapshot_id[:12]}...")
                if len(removed) > 10:
                    console.print(f"  ... and {len(removed) - 10} more")

        except Exception as e:
            progress.update(task, description="Retention policy failed")
            console.print(f"❌ Retention policy failed: [bold red]{e}[/bold red]")
            raise click.ClickException(str(e))


@cli.command()
@click.pass_context
def init_config(ctx):
    config_path = ctx.obj["config_path"]

    if config_path.exists():
        if not click.confirm(f"Configuration file {config_path} exists. Overwrite?"):
            return

    console.print("🔧 Creating backup configuration...")

    name = click.prompt("Backup name", default="my-backup")

    source_paths = []
    console.print("📁 Enter source paths to backup (empty line to finish):")
    while True:
        path = click.prompt("Source path", default="", show_default=False)
        if not path:
            break
        source_paths.append(path)

    if not source_paths:
        raise click.ClickException("At least one source path is required")

    restic_repo = click.prompt("Restic repository path", default="./backup-repo")
    encryption_key_file = click.prompt("Encryption key file", default="./backup.key")

    # Create encryption key file if it doesn't exist
    key_path = Path(encryption_key_file)
    if not key_path.exists():
        import secrets

        key_path.parent.mkdir(parents=True, exist_ok=True)
        with open(key_path, "w") as f:
            f.write(secrets.token_urlsafe(32))
        console.print(f"🔑 Created encryption key file: {key_path}")

    config_data = {
        "name": name,
        "source_paths": source_paths,
        "restic_repo": restic_repo,
        "schedule": "0 2 * * *",  # Daily at 2 AM
        "retention": {
            "keep_last": 10,
            "keep_hourly": 24,
            "keep_daily": 7,
            "keep_weekly": 4,
            "keep_monthly": 12,
            "keep_yearly": 5,
        },
        "encryption_key_file": encryption_key_file,
        "exclude_patterns": ["*.tmp", "*.log", ".DS_Store", "__pycache__", "node_modules"],
        "include_patterns": [],
    }

    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)

    console.print(f"✅ Configuration saved to {config_path}")
    console.print("🚀 You can now run 'backup snapshot' to create your first backup!")


@cli.group()
def keychain():
    """Manage passwords in macOS Keychain"""
    pass


@keychain.command("store")
@click.argument("account_name")
@click.option("--password", prompt=True, hide_input=True, help="Password to store")
def keychain_store(account_name, password):
    """Store a password in macOS Keychain"""
    keychain = KeychainManager()

    if keychain.store_password(account_name, password):
        console.print(
            f"✅ Password stored in keychain for account: [bold green]{account_name}[/bold green]"
        )
        console.print(f'💡 Add to your config: "keychain_account": "{account_name}"')
    else:
        console.print("❌ Failed to store password in keychain")
        raise click.ClickException("Keychain storage failed")


@keychain.command("get")
@click.argument("account_name")
def keychain_get(account_name):
    """Retrieve a password from macOS Keychain (for testing)"""
    keychain = KeychainManager()

    password = keychain.get_password(account_name)
    if password:
        console.print(f"✅ Password found for account: [bold green]{account_name}[/bold green]")
        console.print(f"Password: [dim]{password[:4]}...{password[-4:]}[/dim]")
    else:
        console.print(f"❌ No password found for account: {account_name}")


@keychain.command("delete")
@click.argument("account_name")
@click.confirmation_option(prompt="Are you sure you want to delete this password?")
def keychain_delete(account_name):
    """Delete a password from macOS Keychain"""
    keychain = KeychainManager()

    if keychain.delete_password(account_name):
        console.print(
            f"✅ Password deleted from keychain for account: [bold green]{account_name}[/bold green]"
        )
    else:
        console.print("❌ Failed to delete password from keychain")


@cli.command()
@click.option("--repo-path", help="Path to existing Restic repository")
@click.option("--account-name", help="Keychain account name (defaults to repo folder name)")
def migrate(repo_path, account_name):
    """Migrate existing Restic setup to use keychain"""
    import getpass

    console.print("🔐 [bold]Migrating Restic password to macOS Keychain[/bold]")
    console.print("This is more secure than environment variables.\n")

    # Get repository path
    if not repo_path:
        repo_path = click.prompt(
            "Enter your Restic repository path", default="/Volumes/Crucial2506/restic-backup"
        )

    repo_path = Path(repo_path).expanduser()
    if not repo_path.exists():
        console.print(f"❌ Repository path does not exist: {repo_path}")
        raise click.ClickException("Invalid repository path")

    # Get account name
    if not account_name:
        account_name = repo_path.name

    console.print(f"📁 Repository: [cyan]{repo_path}[/cyan]")
    console.print(f"🔑 Account name: [yellow]{account_name}[/yellow]\n")

    # Get current password securely
    password = getpass.getpass("Enter your current Restic password: ")

    # Store in keychain
    keychain = KeychainManager()
    if keychain.store_password(account_name, password):
        console.print(
            f"✅ Password stored in keychain as '[bold green]{account_name}[/bold green]'\n"
        )

        # Create updated config
        config_data = {
            "name": f"{account_name}-backup",
            "source_paths": [str(Path.home() / "Documents"), str(Path.home() / "Projects")],
            "restic_repo": str(repo_path),
            "keychain_account": account_name,
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

        # Save config
        config_path = Path("backup_config.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        console.print(f"📝 Created [cyan]{config_path}[/cyan] with keychain integration")

        console.print("\n🚀 [bold green]Migration complete![/bold green]")
        console.print("You can now remove these environment variables:")
        console.print("[dim]unset RESTIC_REPOSITORY[/dim]")
        console.print("[dim]unset RESTIC_PASSWORD[/dim]")
        console.print("\nTest with: [bold]backup status[/bold]")

    else:
        console.print("❌ Failed to store password in keychain")
        raise click.ClickException("Migration failed")


if __name__ == "__main__":
    cli()

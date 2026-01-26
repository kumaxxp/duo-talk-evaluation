"""HAKONIWA CLI entry point.

Commands:
- hakoniwa config validate <path>: Validate config file
- hakoniwa up [--config <path>]: Show health summary
- hakoniwa load <path> [--dry-run]: Load world state
"""

import json
import sys
from pathlib import Path

import click

from hakoniwa import __version__
from hakoniwa.config import (
    HakoniwaConfig,
    get_config_hash,
    get_health_summary,
    load_config,
    validate_config,
)
from hakoniwa.persistence import load_dry_run, load_world_state


@click.group()
@click.version_option(version=__version__, prog_name="hakoniwa")
def cli():
    """HAKONIWA-G3: World State Management for duo-talk."""
    pass


@cli.group()
def config():
    """Config management commands."""
    pass


@config.command("validate")
@click.argument("config_path", type=click.Path(exists=False))
def config_validate(config_path: str):
    """Validate config file.

    CONFIG_PATH: Path to YAML config file
    """
    path = Path(config_path)

    is_valid, errors = validate_config(path)

    if is_valid:
        click.echo(click.style("✓ Config OK", fg="green"))

        # Show loaded config summary
        try:
            loaded_config = load_config(path)
            click.echo(f"  config_hash: {get_config_hash(loaded_config)}")
            click.echo(f"  llm_backend: {loaded_config.llm_backend}")
            click.echo(f"  llm_model: {loaded_config.llm_model}")
        except Exception:
            pass

        sys.exit(0)
    else:
        click.echo(click.style("✗ Config Invalid", fg="red"))
        for error in errors:
            click.echo(f"  - {error}")
        sys.exit(1)


@cli.command("up")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output as JSON",
)
def up(config_path: str | None, output_json: bool):
    """Show health summary and config hash.

    Validates config and displays system status.
    """
    # Load config
    path = Path(config_path) if config_path else None
    loaded_config = load_config(path)

    # Get health summary
    summary = get_health_summary(loaded_config)

    if output_json:
        click.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        click.echo(click.style("HAKONIWA Health Summary", fg="cyan", bold=True))
        click.echo()
        click.echo(f"  status:      {click.style(summary['status'], fg='green')}")
        click.echo(f"  config_hash: {summary['config_hash']}")
        click.echo()
        click.echo("  LLM Settings:")
        click.echo(f"    backend:   {summary['llm_backend']}")
        click.echo(f"    model:     {summary['llm_model']}")
        click.echo(f"    base_url:  {summary['llm_base_url']}")
        click.echo()
        click.echo("  Session Settings:")
        click.echo(f"    max_turns:   {summary['max_turns']}")
        click.echo(f"    max_retries: {summary['max_retries']}")
        click.echo(f"    results_dir: {summary['results_dir']}")


@cli.command("load")
@click.argument("state_path", type=click.Path(exists=False))
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Validate only, don't load state",
)
def load(state_path: str, dry_run: bool):
    """Load world state from file.

    STATE_PATH: Path to world state JSON file

    With --dry-run: Validates file integrity and schema compatibility.
    Without --dry-run: Loads and displays state summary.
    """
    path = Path(state_path)

    if dry_run:
        # Dry-run mode: validate only
        is_valid, errors = load_dry_run(path)

        if is_valid:
            click.echo(click.style("✓ State OK", fg="green"))
            click.echo(f"  path: {path}")
            click.echo(f"  schema_version: 1.0.0")
            sys.exit(0)
        else:
            click.echo(click.style("✗ State Invalid", fg="red"))
            for error in errors:
                click.echo(f"  - {error}")
            sys.exit(1)
    else:
        # Full load mode
        try:
            # First validate
            is_valid, errors = load_dry_run(path)
            if not is_valid:
                click.echo(click.style("✗ State Invalid", fg="red"))
                for error in errors:
                    click.echo(f"  - {error}")
                sys.exit(1)

            # Load state
            state = load_world_state(path)

            # Display summary
            click.echo(click.style("HAKONIWA State Loaded", fg="cyan", bold=True))
            click.echo()
            click.echo(f"  session_id:     {state.manifest.session_id}")
            click.echo(f"  schema_version: {state.manifest.schema_version}")
            click.echo(f"  scenario_id:    {state.scenario_id}")
            click.echo(f"  turn_count:     {len(state.history)}")
            click.echo(f"  created_at:     {state.manifest.created_at.isoformat()}")
            if state.manifest.modified_at:
                click.echo(f"  modified_at:    {state.manifest.modified_at.isoformat()}")

        except Exception as e:
            click.echo(click.style(f"✗ Load failed: {e}", fg="red"))
            sys.exit(1)


def main():
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()

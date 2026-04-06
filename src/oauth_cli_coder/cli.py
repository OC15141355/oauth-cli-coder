"""Click CLI — the oauth-coder command."""

from __future__ import annotations

import time
from datetime import datetime

import click

from . import format as fmt
from . import providers as _providers  # noqa: F401 — triggers auto-registration
from . import session, tmux
from .provider import get_provider, list_providers

# Polling config
POLL_INTERVAL = 0.5
STABLE_THRESHOLD = 3


def _wait_for_idle(tmux_session: str, provider, timeout: int) -> bool:
    """Poll until the CLI tool is idle or timeout."""
    start = time.time()
    last_screen = ""
    stable = 0

    while time.time() - start < timeout:
        raw = tmux.capture_pane(tmux_session)
        screen = tmux.strip_ansi(raw)

        if provider.is_idle(screen):
            if screen == last_screen:
                stable += 1
                if stable >= STABLE_THRESHOLD:
                    return True
            else:
                stable = 0
                last_screen = screen
        else:
            stable = 0

        time.sleep(POLL_INTERVAL)

    return False


@click.group()
@click.version_option(package_name="oauth-cli-coder")
def cli():
    """Drive AI CLI tools via tmux sessions with existing OAuth tokens."""


@cli.command()
@click.argument("provider_name", metavar="PROVIDER")
@click.argument("prompt")
@click.option("-s", "--session-id", "session_name", default="default",
              help="Named session for context persistence.")
@click.option("-m", "--model", default=None,
              help="Model variant (e.g. 'sonnet', 'opus').")
@click.option("--cwd", default=None,
              help="Working directory for the session.")
@click.option("-o", "--option", "options", multiple=True,
              help="Extra CLI flags passed to the tool.")
@click.option("--raw", is_flag=True,
              help="Skip output formatting (no markdown stripping).")
@click.option("--ascii", "ascii_only", is_flag=True,
              help="Strip all non-ASCII from output.")
@click.option("-w", "--width", default=76, show_default=True,
              help="Wrap width for output.")
@click.option("-t", "--timeout", default=300, show_default=True,
              help="Response timeout in seconds.")
def ask(provider_name, prompt, session_name, model, cwd, options, raw,
        ascii_only, width, timeout):
    """Send a prompt to PROVIDER and print the response.

    PROVIDER is one of: claude, gemini, codex.

    \b
    Examples:
        oauth-coder ask claude "explain this repo"
        oauth-coder ask claude "review my code" -s my-project -m opus
        oauth-coder ask gemini "what does main.go do?" --cwd ~/Projects/app
    """
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="PROVIDER")

    # Get or create session
    click.echo(f"session: {session_name} ({provider_name})", err=True)
    sess = session.get_or_create(
        session_name, provider, model=model, cwd=cwd,
        options=list(options) if options else None,
    )

    if not sess.alive:
        click.echo("error: session died during startup", err=True)
        raise SystemExit(1)

    # Check idle
    raw_screen = tmux.capture_pane(sess.tmux_session)
    screen = tmux.strip_ansi(raw_screen)
    if not provider.is_idle(screen):
        # Wait briefly — might still be starting up
        click.echo("waiting for idle...", err=True)
        if not _wait_for_idle(sess.tmux_session, provider, timeout=30):
            click.echo("error: provider is busy — try again later", err=True)
            raise SystemExit(1)

    # Clear screen for clean capture
    tmux.send_keys(sess.tmux_session, ["C-l"])
    time.sleep(0.3)

    # Paste prompt and submit
    tmux.paste_text(sess.tmux_session, prompt)
    time.sleep(0.3)
    tmux.send_keys(sess.tmux_session, ["Enter"])

    # Wait for response
    click.echo("thinking...", err=True)
    _wait_for_idle(sess.tmux_session, provider, timeout=timeout)

    # Extract response
    raw_scrollback = tmux.capture_pane(sess.tmux_session, full_history=True)
    clean = tmux.strip_ansi(raw_scrollback)
    response = provider.extract_response(clean)

    if not response:
        click.echo("warning: empty response", err=True)
        raise SystemExit(1)

    if raw:
        click.echo(response)
    else:
        click.echo(fmt.format_for_terminal(response, width=width,
                                            ascii_only=ascii_only))


@cli.command("list")
def list_sessions():
    """List all active sessions."""
    sessions = session.list_all()
    session.prune()

    if not sessions:
        click.echo("no active sessions")
        return

    click.echo(f"{'NAME':<20} {'PROVIDER':<10} {'MODEL':<10} {'STATUS':<8} {'CREATED'}")
    click.echo("-" * 72)
    for s in sessions:
        status_text = "alive" if s.alive else "dead"
        status_color = "green" if s.alive else "red"
        created = datetime.fromtimestamp(s.created).strftime("%Y-%m-%d %H:%M")
        model = s.model or "-"
        line = f"{s.name:<20} {s.provider:<10} {model:<10} {status_text:<8} {created}"
        # Colorize just the status word
        line = line.replace(status_text, click.style(status_text, fg=status_color), 1)
        click.echo(line)


@cli.command()
@click.argument("name", default="default")
def stop(name):
    """Stop a session and remove it."""
    if session.stop(name):
        click.echo(f"stopped: {name}")
    else:
        click.echo(f"no session: {name}", err=True)
        raise SystemExit(1)


@cli.command("stop-all")
@click.confirmation_option(prompt="Stop all sessions?")
def stop_all():
    """Stop all sessions."""
    count = session.stop_all()
    click.echo(f"stopped {count} session(s)")


@cli.command()
@click.argument("provider_name", metavar="PROVIDER")
@click.argument("name", default="default")
@click.option("-m", "--model", default=None, help="Model variant.")
@click.option("--cwd", default=None, help="Working directory.")
@click.option("-o", "--option", "options", multiple=True,
              help="Extra CLI flags.")
def start(provider_name, name, model, cwd, options):
    """Pre-create a session without sending a prompt.

    \b
    Examples:
        oauth-coder start claude my-project --cwd ~/Projects/app
        oauth-coder start gemini review -m pro
    """
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="PROVIDER")

    click.echo(f"starting {provider_name} session: {name}...", err=True)
    sess = session.create(name, provider, model=model, cwd=cwd,
                          options=list(options) if options else None)

    if sess.alive:
        click.echo(f"ready: {name} (tmux: {sess.tmux_session})")
    else:
        click.echo("error: session failed to start", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("provider_name", metavar="PROVIDER")
@click.argument("name", default="default")
def status(provider_name, name):
    """Check if a session is alive and idle."""
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="PROVIDER")

    sess = session.get(name)
    if not sess or not sess.alive:
        click.echo(f"{name}: not running")
        raise SystemExit(1)

    raw = tmux.capture_pane(sess.tmux_session)
    screen = tmux.strip_ansi(raw)
    idle = provider.is_idle(screen)
    state = "idle" if idle else "busy"
    click.echo(f"{name}: {state}")


@cli.command()
def providers():
    """List available providers."""
    for name in list_providers():
        click.echo(name)

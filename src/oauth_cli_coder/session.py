"""Session registry — persistent named sessions stored as JSON."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import tmux
from .provider import Provider

SESSIONS_DIR = Path.home() / ".config" / "oauth-cli-coder"
SESSIONS_FILE = SESSIONS_DIR / "sessions.json"


@dataclass
class Session:
    name: str
    provider: str
    tmux_session: str
    model: str | None
    cwd: str | None
    created: float  # time.time()

    @property
    def alive(self) -> bool:
        return tmux.has_session(self.tmux_session)


def _load() -> dict[str, dict]:
    """Load session registry from disk."""
    if not SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, dict]) -> None:
    """Write session registry to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def create(name: str, provider: Provider, model: str | None = None,
           cwd: str | None = None, options: list[str] | None = None) -> Session:
    """Create a new tmux session running the provider's CLI tool."""
    tmux_name = tmux.session_name(provider.name, name)

    # Kill existing session if it's stale
    if tmux.has_session(tmux_name):
        tmux.kill_session(tmux_name)

    command = provider.launch_command(model=model, options=options)
    tmux.create_session(tmux_name, command, cwd=cwd)

    session = Session(
        name=name,
        provider=provider.name,
        tmux_session=tmux_name,
        model=model,
        cwd=cwd,
        created=time.time(),
    )

    # Persist
    data = _load()
    data[name] = asdict(session)
    _save(data)

    # Wait for the CLI to start up
    time.sleep(provider.startup_time)

    return session


def get(name: str) -> Session | None:
    """Look up a session by name."""
    data = _load()
    if name not in data:
        return None
    return Session(**data[name])


def get_or_create(name: str, provider: Provider, model: str | None = None,
                  cwd: str | None = None,
                  options: list[str] | None = None) -> Session:
    """Get an existing session or create a new one."""
    session = get(name)
    if session and session.alive and session.provider == provider.name:
        return session
    return create(name, provider, model=model, cwd=cwd, options=options)


def list_all() -> list[Session]:
    """List all registered sessions with live status."""
    data = _load()
    return [Session(**v) for v in data.values()]


def stop(name: str) -> bool:
    """Stop a session and remove from registry."""
    session = get(name)
    if not session:
        return False

    tmux.kill_session(session.tmux_session)

    data = _load()
    data.pop(name, None)
    _save(data)
    return True


def stop_all() -> int:
    """Stop all sessions. Returns count of sessions stopped."""
    sessions = list_all()
    count = 0
    for s in sessions:
        if tmux.kill_session(s.tmux_session):
            count += 1
    _save({})
    return count


def prune() -> int:
    """Remove dead sessions from registry. Returns count pruned."""
    data = _load()
    dead = [name for name, info in data.items()
            if not tmux.has_session(info["tmux_session"])]
    for name in dead:
        del data[name]
    if dead:
        _save(data)
    return len(dead)

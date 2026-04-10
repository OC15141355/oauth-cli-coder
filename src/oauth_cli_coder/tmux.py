"""Low-level tmux operations.

All subprocess interaction with tmux lives here. Provides session
lifecycle, input/output, and stealth mode (hide tmux env vars from
child processes so CLI tools behave as if running in a real terminal).
"""

import os
import platform
import re
import subprocess
import tempfile
import time

# tmux session prefix — avoids collisions with user sessions
SESSION_PREFIX = "occ"


def run(cmd: list[str], timeout: int = 30) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def has_session(session: str) -> bool:
    """Check if a tmux session exists."""
    p = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True, text=True,
    )
    return p.returncode == 0


def create_session(session: str, command: str, cwd: str | None = None,
                   stealth: bool = True) -> None:
    """Create a detached tmux session running a command.

    With stealth=True (default), strips TMUX environment variables so the
    child process doesn't know it's inside tmux. This prevents CLI tools
    from adjusting their output format.
    """
    # Pin the session to 80x24 (Terminal.app default) via THREE mechanisms
    # because tmux 3.6+ has multiple overlapping size controls:
    #   1. `-x 80 -y 24` on new-session sets the initial geometry.
    #   2. `default-size 80x24` overrides tmux's default (200x50 on 3.6+)
    #      and is what the session falls back to when no clients attached.
    #   3. `window-size manual` disables auto-resize when clients come/go.
    # TUI applications like Claude Code draw horizontal rules and frame
    # buffers sized to the current terminal width; if tmux ever resizes the
    # pane, those cached graphics wrap badly. All three controls combined
    # keep the session nailed to 80x24 regardless of what clients attach.
    # Users with wider Terminal windows will see 80-wide content that
    # doesn't use the whole screen — that's fine, it's consistent and
    # readable, and it matches the worker-terminal constraint.
    cmd = ["tmux", "new-session", "-d", "-s", session, "-x", "80", "-y", "24"]
    post_create_cmds = [
        ["tmux", "set-option", "-t", session, "default-size", "80x24"],
        ["tmux", "set-option", "-t", session, "window-size", "manual"],
    ]
    if cwd:
        cmd.extend(["-c", cwd])

    if stealth:
        # Build a shell command that scrubs tmux env vars and sets a clean TERM
        # Use double quotes for the outer shell to allow single quotes in commands
        # Platform-specific: macOS script syntax differs from Linux
        inner = f"env -u TMUX -u TMUX_PANE TERM=xterm-256color {command}"
        if platform.system() == "Darwin":
            shell_cmd = f'script -q /dev/null bash -c "{inner}"'
        else:
            shell_cmd = f'script -q /dev/null -c "{inner}"'
        cmd.append(shell_cmd)
    else:
        cmd.append(command)

    subprocess.run(cmd, capture_output=True, text=True)
    # Pin the session geometry so Claude's TUI doesn't get resized out of
    # whatever shape it rendered at on startup. See create_session comments.
    for pc in post_create_cmds:
        subprocess.run(pc, capture_output=True, text=True)
    # Force the session to the pinned geometry explicitly — on some tmux
    # versions the initial -x/-y is honored by new-session but overridden
    # by default-size on first auto-resize. `resize-window` is the big
    # hammer: it sets the window to exactly these dimensions now.
    subprocess.run(
        ["tmux", "resize-window", "-t", session, "-x", "80", "-y", "24"],
        capture_output=True, text=True,
    )
    # Give the process a moment to start
    time.sleep(1.0)


def kill_session(session: str) -> bool:
    """Kill a tmux session. Returns True if it existed."""
    if not has_session(session):
        return False
    subprocess.run(
        ["tmux", "kill-session", "-t", session],
        capture_output=True, text=True,
    )
    return True


def send_keys(session: str, keys: list[str]) -> None:
    """Send keys to a tmux session."""
    subprocess.run(
        ["tmux", "send-keys", "-t", session] + keys,
        capture_output=True, text=True,
    )


def capture_pane(session: str, full_history: bool = False) -> str:
    """Capture tmux pane content, optionally with full scrollback."""
    cmd = ["tmux", "capture-pane", "-p", "-t", session]
    if full_history:
        cmd.extend(["-S", "-", "-E", "-"])
    return run(cmd, timeout=10)


def paste_text(session: str, text: str) -> None:
    """Paste text into a tmux session via buffer (avoids shell escaping issues)."""
    # Use a per-session buffer name to avoid races when multiple sessions
    # are driven concurrently (shared "occ-buf" caused prompt clobbering).
    buf_name = f"occ-{session}"
    fd, tmp = tempfile.mkstemp(prefix="occ-", suffix=".txt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        run(["tmux", "load-buffer", "-b", buf_name, tmp])
        run(["tmux", "paste-buffer", "-b", buf_name, "-p", "-t", session])
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)


def session_name(provider: str, name: str) -> str:
    """Generate a tmux session name: occ-{provider}-{name}."""
    return f"{SESSION_PREFIX}-{provider}-{name}"

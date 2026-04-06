# oauth-cli-coder

Drive AI CLI tools via tmux sessions using existing OAuth tokens. No API keys needed — reuses your browser-based authentication.

Supports **Claude Code**, **Gemini CLI**, and **Codex CLI**.

## How it works

```
┌─────────────┐     tmux session     ┌──────────────┐
│ oauth-coder │ ──── paste/read ──── │  claude/     │
│   (CLI)     │                      │  gemini/     │
└─────────────┘                      │  codex       │
                                     └──────────────┘
                                       ↕ OAuth tokens
                                     (already cached)
```

Instead of managing API keys, oauth-cli-coder launches real CLI tools in background tmux sessions and automates them — paste prompts, poll for completion, extract responses. Your existing OAuth login handles authentication.

## Install

```bash
# With uv (recommended)
uv tool install .

# Or with pip
pip install .
```

**Requirements:** Python 3.10+, tmux, and at least one AI CLI tool installed (`claude`, `gemini`, or `codex`).

## Quick start

```bash
# One-shot query
oauth-coder ask claude "explain this error"

# Named session (maintains context across calls)
oauth-coder ask claude "analyze this codebase" -s my-project --cwd ~/Projects/app
oauth-coder ask claude "now refactor the auth module" -s my-project

# Specific model
oauth-coder ask claude "review for security issues" -m opus

# Other providers
oauth-coder ask gemini "what does main.go do?"
oauth-coder ask codex "write tests for utils.py"
```

## Commands

```
ask PROVIDER "prompt"     Send a prompt, print the response
start PROVIDER [name]     Pre-create a session without a prompt
status PROVIDER [name]    Check if a session is alive and idle
list                      List all active sessions
stop [name]               Stop a session
stop-all                  Stop all sessions
providers                 List available providers
```

## Options

```
-s, --session-id TEXT     Named session (default: "default")
-m, --model TEXT          Model variant (e.g. "sonnet", "opus")
--cwd PATH                Working directory for the session
-o, --option TEXT         Extra flags passed to the CLI tool
--raw                     Skip markdown stripping
--ascii                   Strip all non-ASCII (for retro terminals)
-w, --width INT           Wrap width (default: 76)
-t, --timeout INT         Response timeout in seconds (default: 300)
```

## Session management

Sessions are persistent tmux processes. First `ask` auto-creates a session; subsequent calls to the same session maintain conversation context.

```bash
# Pre-create for faster first response
oauth-coder start claude my-project --cwd ~/Projects/app

# Check status
oauth-coder status claude my-project

# List all
oauth-coder list

# Clean up
oauth-coder stop my-project
oauth-coder stop-all
```

Sessions are registered in `~/.config/oauth-cli-coder/sessions.json` and auto-pruned when dead.

## Stealth mode

By default, sessions launch with tmux environment variables stripped and a fresh pseudo-terminal allocated. This prevents CLI tools from detecting they're inside tmux and adjusting their output format.

## Output formatting

Responses are automatically processed:
- Markdown syntax stripped (headings, bold, code fences, links)
- Unicode normalized to ASCII equivalents (em dashes, smart quotes)
- Lines wrapped to terminal width
- Use `--raw` to disable, `--ascii` for pure ASCII output

## Adding providers

Create a new file in `src/oauth_cli_coder/providers/` following the pattern:

```python
from ..provider import Provider

class MyProvider(Provider):
    name = "my-tool"
    command = "my-tool-cli"
    idle_marker = ">"           # prompt character when idle
    busy_markers = ["..."]      # indicators the tool is working
    startup_time = 5.0          # seconds to wait after launch

    def model_flag(self, model: str) -> list[str]:
        return ["--model", model]
```

Then register it in `providers/__init__.py`.

## Architecture

```
src/oauth_cli_coder/
├── cli.py              # Click entry point
├── tmux.py             # Low-level tmux operations + stealth mode
├── session.py          # Persistent session registry
├── provider.py         # Base provider class + registry
├── format.py           # Output formatting (markdown, unicode, wrapping)
└── providers/
    ├── claude.py       # Claude Code (battle-tested)
    ├── gemini.py       # Gemini CLI
    └── codex.py        # Codex CLI
```

## Prior art

Inspired by [codeninja/oauth-cli-coder](https://github.com/codeninja/oauth-cli-coder). This is a clean-room implementation with a focus on proven tmux interaction patterns from real-world use on constrained hardware (9600 baud serial terminals).

## License

MIT

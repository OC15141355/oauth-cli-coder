"""Base provider and provider registry.

Each AI CLI tool (Claude Code, Gemini CLI, Codex) is a provider that knows
how to launch itself, detect idle state, and extract responses from tmux
scrollback.
"""

from __future__ import annotations

# Provider registry
_PROVIDERS: dict[str, Provider] = {}


class Provider:
    """Base class for AI CLI tool providers."""

    name: str = ""
    command: str = ""
    idle_marker: str = ""
    busy_markers: list[str] = []
    response_markers: list[str] = []
    startup_time: float = 5.0  # seconds to wait for CLI to start

    def launch_command(self, model: str | None = None,
                       options: list[str] | None = None) -> str:
        """Return the shell command to start this CLI tool."""
        parts = [self.command]
        if model:
            parts.extend(self.model_flag(model))
        if options:
            parts.extend(options)
        return " ".join(parts)

    def model_flag(self, model: str) -> list[str]:
        """Return CLI flags for a specific model. Override per provider."""
        return []

    def is_idle(self, screen: str) -> bool:
        """Check if the CLI tool is at an idle prompt.

        Only checks the last 5 lines for busy markers to avoid false
        positives from response content containing words like 'Running'.
        """
        has_prompt = self.idle_marker in screen
        tail = "\n".join(screen.split("\n")[-5:])
        is_busy = any(m in tail for m in self.busy_markers)
        return has_prompt and not is_busy

    def extract_response(self, scrollback: str) -> str:
        """Extract the latest response from tmux scrollback.

        Default: find content between the last two idle markers.
        Providers with richer TUI output should override this.
        """
        lines = scrollback.split("\n")
        prompt_positions = [
            i for i, line in enumerate(lines) if self.idle_marker in line
        ]
        if len(prompt_positions) >= 2:
            start = prompt_positions[-2] + 1
            end = prompt_positions[-1]
            content = lines[start:end]
            return "\n".join(l for l in content if l.strip()).strip()
        return ""


def register(provider: Provider) -> None:
    """Register a provider by name."""
    _PROVIDERS[provider.name] = provider


def get_provider(name: str) -> Provider:
    """Look up a provider by name."""
    if name not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    return _PROVIDERS[name]


def list_providers() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(_PROVIDERS)

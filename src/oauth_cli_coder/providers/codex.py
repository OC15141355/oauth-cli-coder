"""OpenAI Codex CLI provider.

Drives the `codex` CLI tool. Marker patterns discovered empirically —
update if Codex CLI changes its TUI format.
"""

from __future__ import annotations

from ..provider import Provider


class CodexProvider(Provider):
    name = "codex"
    command = "codex"
    idle_marker = ">"
    busy_markers = ["...", "Thinking", "Running"]
    startup_time = 8.0

    def model_flag(self, model: str) -> list[str]:
        return ["--model", model]

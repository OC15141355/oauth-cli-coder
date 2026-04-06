"""Gemini CLI provider.

Drives the `gemini` CLI tool. Marker patterns discovered empirically —
update if Gemini CLI changes its TUI format.
"""

from __future__ import annotations

from ..provider import Provider


class GeminiProvider(Provider):
    name = "gemini"
    command = "gemini"
    idle_marker = ">"
    busy_markers = ["...", "Generating", "Thinking"]
    startup_time = 8.0

    def model_flag(self, model: str) -> list[str]:
        return ["--model", model]

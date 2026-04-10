"""Claude Code provider.

Drives the `claude` CLI tool. Battle-tested idle detection and response
extraction from real-world use (9600 baud serial terminal).
"""

from __future__ import annotations

from ..provider import Provider

# Claude Code TUI markers
_IDLE = "\u276f"                    # ❯ prompt
_BUSY = [
    "\u280b", "\u280d", "\u2839",   # braille spinners
    "\u2838", "\u2834", "\u2826",
    "\u2807", "\u280f",
    "Thinking", "Running",
]
# Response markers: ● (U+25CF) or ⏺ (U+23FA) depending on version
_RESPONSE_PREFIXES = ("\u25cf\u200a", "\u25cf ", "\u23fa\u200a", "\u23fa ")
# UI chrome that signals end of response
_CHROME = ("\u2500\u2500", "\u2580\u2580", "\u2584\u2584",
           ".---.", "(\u00b0>\u00b0)", "\u2501\u2501")


class ClaudeProvider(Provider):
    name = "claude"
    command = "claude --dangerously-skip-permissions"
    idle_marker = _IDLE
    busy_markers = _BUSY
    startup_time = 10.0  # Claude Code takes a moment to initialize

    def model_flag(self, model: str) -> list[str]:
        return ["--model", model]

    def extract_response(self, scrollback: str) -> str:
        """Extract the last Claude response from scrollback.

        Claude Code format:
            ❯ <user prompt>
            ● <response text...>
               <continued...>
            ❯ (next idle prompt)

        Also handles ⎿ (continuation/result marker).
        """
        lines = scrollback.split("\n")

        # Find response marker positions (● or ⏺)
        marker_positions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(stripped.startswith(m) for m in _RESPONSE_PREFIXES):
                marker_positions.append(i)

        if not marker_positions:
            # Fallback: content between last two ❯ prompts
            return super().extract_response(scrollback)

        # Extract from last response marker to next idle prompt
        start = marker_positions[-1]
        result = []

        for i in range(start, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # Stop at idle prompt
            if i > start and _IDLE in line:
                break

            # Stop at UI chrome
            if any(b in line for b in _CHROME):
                break

            # Strip response marker from first line
            if i == start:
                for prefix in _RESPONSE_PREFIXES:
                    if stripped.startswith(prefix):
                        stripped = stripped[len(prefix):]
                        break
                result.append(stripped)
            else:
                result.append(line.rstrip())

        return "\n".join(result).strip()

"""Provider auto-registration."""

from ..provider import register
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .codex import CodexProvider

register(ClaudeProvider())
register(GeminiProvider())
register(CodexProvider())

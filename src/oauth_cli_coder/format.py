"""Output formatting — markdown stripping, unicode normalization, word wrapping."""

import re
import textwrap

# Markdown patterns to strip (order matters)
_MD_PATTERNS = [
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),              # headings
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),                       # bold
    (re.compile(r"\*(.+?)\*"), r"\1"),                           # italic
    (re.compile(r"`{3}[\w]*\n?", re.MULTILINE), ""),            # code fences
    (re.compile(r"`(.+?)`"), r"\1"),                             # inline code
    (re.compile(r"^\s*[-*]\s+", re.MULTILINE), "- "),            # normalize bullets
    (re.compile(r"^\s*\d+\.\s+", re.MULTILINE), "- "),          # numbered → bullets
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),               # links → text
]

# Unicode → ASCII replacements
_UNICODE_MAP = {
    "\u2014": "--",    # em dash
    "\u2013": "-",     # en dash
    "\u2018": "'",     # left single quote
    "\u2019": "'",     # right single quote
    "\u201c": '"',     # left double quote
    "\u201d": '"',     # right double quote
    "\u2026": "...",   # ellipsis
    "\u00a0": " ",     # non-breaking space
    "\u200a": " ",     # hair space
    "\u00b7": "-",     # middle dot
    "\u2022": "-",     # bullet
}


def strip_markdown(text: str) -> str:
    """Remove markdown formatting from text."""
    for pattern, replacement in _MD_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def normalize_unicode(text: str) -> str:
    """Replace common unicode characters with ASCII equivalents."""
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)
    return text


def strip_non_ascii(text: str) -> str:
    """Remove all non-ASCII characters."""
    return "".join(c if ord(c) < 128 else "" for c in text)


def format_for_terminal(text: str, width: int = 76, ascii_only: bool = False) -> str:
    """Format text for terminal display.

    Strips markdown, normalizes unicode, wraps lines. With ascii_only=True,
    also strips any remaining non-ASCII characters (for terminals like Mac Plus).
    """
    text = strip_markdown(text)
    text = normalize_unicode(text)

    if ascii_only:
        text = strip_non_ascii(text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Wrap long lines
    wrapped = []
    for line in text.split("\n"):
        if len(line) <= width:
            wrapped.append(line)
        elif line.startswith("- "):
            wrapped.extend(textwrap.wrap(line, width=width,
                                         subsequent_indent="  "))
        else:
            wrapped.extend(textwrap.wrap(line, width=width) or [""])

    return "\n".join(wrapped).strip()

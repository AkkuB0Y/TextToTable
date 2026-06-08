"""
Text normalization — Phase 3.

Cleans raw Whisper transcripts by removing filler words,
lowercasing, and collapsing whitespace.
"""

from __future__ import annotations

import re

# Common filler words to strip from transcripts
FILLERS = [
    "um", "uh", "like", "you know", "so", "actually", "basically",
    "i mean", "sort of", "kind of", "right", "well",
]


def normalize(text: str) -> str:
    """
    Clean a raw transcript for downstream processing.

    Steps:
        1. Lowercase + strip
        2. Remove filler words (whole-word matches)
        3. Collapse runs of whitespace
        4. Strip leading/trailing whitespace and punctuation artifacts

    Args:
        text: Raw transcript from Whisper.

    Returns:
        Cleaned, normalized text.
    """
    text = text.lower().strip()

    # Remove filler words — longest first so "you know" is matched before "you"
    for filler in sorted(FILLERS, key=len, reverse=True):
        # Match the filler as a whole word/phrase with optional surrounding commas
        pattern = rf",?\s*\b{re.escape(filler)}\b\s*,?"
        text = re.sub(pattern, " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    # Clean up any leading/trailing commas or periods left behind
    text = text.strip(",. ")

    return text

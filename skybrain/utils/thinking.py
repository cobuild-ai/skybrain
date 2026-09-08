"""SkyBrain Thinking Block Utilities.

Centralizes <think>...</think> stripping for all model outputs.

Qwen 3.8 (and other reasoning models like DeepSeek-R1, Gemma 3) emit
internal chain-of-thought wrapped in <think>...</think> tags before
producing their actual answer. This module provides a single, correct
regex-based utility that handles all edge cases:

  - Complete blocks: <think>reasoning...</think>
  - Orphan closing tags from stream-truncated responses: </think>
  - Multiple / repeated think blocks in one response
  - Think blocks that contain markdown fences internally
"""

from __future__ import annotations

import re

__all__ = ["strip_thinking"]

# Compiled once at import time for performance.
# re.DOTALL makes '.' match newlines inside the think block.
_THINK_BLOCK_RE: re.Pattern[str] = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove all <think>...</think> reasoning blocks from model output.

    This is the single authoritative implementation — do NOT inline
    ``split("</think>", ...)`` anywhere else in the codebase.

    Handles the following cases correctly:

    **Case 1 — Complete block (normal output)**::

        "<think>reasoning...</think>\\n[{...}]"
        → "[{...}]"

    **Case 2 — Orphan closing tag (stream truncation)**::

        "partial reasoning...</think>\\n[{...}]"
        → "[{...}]"

    **Case 3 — Multiple blocks**::

        "<think>pass 1</think>\\n<think>pass 2</think>\\n[{...}]"
        → "[{...}]"

    **Case 4 — Think block containing markdown fences internally**::

        "<think>I'll use ```json format...</think>\\n[{...}]"
        → "[{...}]"

    **Case 5 — No think block (pass-through)**::

        "[{...}]"
        → "[{...}]"

    Args:
        text: Raw model output that may contain thinking blocks.

    Returns:
        Cleaned output with all thinking blocks removed, stripped of
        leading/trailing whitespace.
    """
    # Step 1: Remove all complete <think>...</think> blocks (greedy-off with ?).
    text = _THINK_BLOCK_RE.sub("", text)

    # Step 2: Remove any orphan </think> closing tag left by a stream-truncated
    # open block, and keep only content after it.
    text = text.split("</think>")[-1]

    return text.strip()

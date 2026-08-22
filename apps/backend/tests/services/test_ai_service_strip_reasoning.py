"""
ai_service.py's _strip_reasoning() (2026-08-22 fix) — some reasoning-tuned
free models (confirmed live on Groq's qwen/qwen3.6-27b, added to the
fallback chain the same day the two llama-* Groq models were found dead)
inline their entire chain-of-thought directly in `content` as a literal
<think>...</think> block instead of a separate reasoning field. Without
stripping it, every caller expecting clean prose or JSON (commodities'
AI insights, among many others) silently failed to parse a real, successful
model response and fell back to generic canned text.
"""
from __future__ import annotations

from app.services.ai_service import _strip_reasoning


def test_passes_through_content_with_no_think_block():
    assert _strip_reasoning('{"a": 1}') == '{"a": 1}'


def test_strips_a_closed_think_block_and_keeps_the_real_answer():
    raw = "<think>\nOkay, the user wants JSON.\n</think>\n\n{\"a\": 1}"
    assert _strip_reasoning(raw) == '{"a": 1}'


def test_case_insensitive_tag_matching():
    raw = "<THINK>reasoning here</THINK>real answer"
    assert _strip_reasoning(raw) == "real answer"


def test_unclosed_think_block_that_never_finished_returns_empty():
    raw = "<think>\nHere's a thinking process:\n\n1. Analyze the input..."
    assert _strip_reasoning(raw) == ""


def test_multiple_think_blocks_all_stripped():
    raw = "<think>first</think>answer<think>second</think>"
    assert _strip_reasoning(raw) == "answer"

"""
Regression suite — nse_provider._clip_headline, offline.

Real incident (2026-09-10): a live event's title read "Attached herewith
the newspaper advertisements pertaining to special window for transfer
and dematerialisation (demat) of physical shares published today i.e.
September 10, 2026…" -- grammatically incomplete, even though the same
row's `summary` field already held the complete sentence, and
Event.title is a String(512) column (no real storage constraint forced
the old 180-char cap). Root cause: a hard character-count cut at the
nearest WORD boundary (not a sentence boundary), with an unconditional
appended "…" -- the same defect class as content_planner.py's
_safe_event_phrase fix for question-angle article titles, here in the
raw NSE ingestion layer instead.
"""
from __future__ import annotations

from app.providers.nse_provider import _clip_headline, _MAX_HEADLINE_LEN


def test_real_reported_specimen_passes_through_complete():
    text = (
        "Attached herewith the newspaper advertisements pertaining to special "
        "window for transfer and dematerialisation (demat) of physical shares "
        "published today i.e. September 10, 2026 in the newspapers."
    )
    result = _clip_headline(text)
    assert result == text
    assert not result.endswith("…")


def test_short_text_under_cap_returned_verbatim():
    text = "NHPC Limited has informed the Exchange about a routine filing."
    assert _clip_headline(text) == text


def test_text_at_exactly_the_cap_returned_verbatim():
    text = "x" * _MAX_HEADLINE_LEN
    assert _clip_headline(text) == text


def test_long_text_with_sentence_boundary_within_budget_cuts_there_cleanly():
    first_sentence = "This is a complete announcement sentence that ends properly."
    # Deliberately punctuation-free padding (no periods/!/?) so the ONLY
    # sentence boundary anywhere in the truncation window is the real one
    # at the end of first_sentence -- isolates the behavior being tested.
    padding = "and extra unrelated trailing word after word after word " * 15
    text = first_sentence + " " + padding
    assert len(text) > _MAX_HEADLINE_LEN

    result = _clip_headline(text)

    assert result == first_sentence
    assert not result.endswith("…")
    assert result.endswith(".")


def test_long_text_with_no_sentence_boundary_falls_back_to_word_boundary_with_ellipsis():
    text = "word " * 200  # no punctuation anywhere, well over the cap
    result = _clip_headline(text)

    assert len(text) > _MAX_HEADLINE_LEN
    assert result.endswith("…")
    assert not result.endswith(" …")  # rsplit already strips the trailing space before appending
    assert "  " not in result.rstrip("…").rstrip()


def test_sentence_boundary_too_close_to_start_is_rejected_as_too_short():
    """A one-word 'sentence' near the very start of a long text is noise,
    not a real usable title -- must fall through to the word-boundary
    fallback instead of returning a near-empty clause."""
    text = "Ok. " + ("filler word " * 100)
    assert len(text) > _MAX_HEADLINE_LEN

    result = _clip_headline(text)

    assert result != "Ok."
    assert result.endswith("…")


def test_multiple_sentences_within_budget_cuts_at_the_last_one_not_the_first():
    s1 = "First sentence here."
    s2 = "Second sentence follows and is also complete."
    # Punctuation-free tail, same reasoning as the test above -- isolates
    # exactly two real sentence boundaries inside the truncation window.
    padding = "then a very long unrelated tail of extra words after words after words " * 10
    text = f"{s1} {s2} {padding}"
    assert len(text) > _MAX_HEADLINE_LEN

    result = _clip_headline(text)

    assert result == f"{s1} {s2}"

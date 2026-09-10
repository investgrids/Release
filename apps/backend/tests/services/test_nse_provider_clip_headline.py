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


# ── Abbreviation-boundary false-positives (found via the historical-repair ──
# inventory pass, 2026-09-10, before it reached production repair; these
# real specimens were producing a result SHORTER than, and no more
# complete than, the text they were meant to improve on).

def test_re_abbreviation_is_not_mistaken_for_a_sentence_end():
    text = (
        "The Board of Directors of the Company, at their meeting held on April 30, 2026, "
        "had recommended final dividend of Rs. 6/- per equity shares of face value of Re. "
        "1/- each and in this regard, as per the provisions of Regulation 42 of the Listing "
        "Regulations, the Company has fixed Monday, September 21, 2026 as the Record Date "
        "for the purpose of determining entitlement of the Members of the Company to the "
        "said final dividend, if declared at the 40th Annual General meeting of the Company."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert "face value of Re." not in result or len(result) > len("The Board of Directors of the Company, at their meeting held on April 30, 2026, had recommended final dividend of Rs. 6/- per equity shares of face value of Re.")
    assert not result.endswith("of Re.")


def test_ie_abbreviation_is_not_mistaken_for_a_sentence_end():
    text = (
        "Universal Cables Limited has informed the Exchange about change in Management i.e. "
        "Appointment of Shri Nishant Premkuar Saigal as the Chief Financial Officer (CFO), a "
        "Whole Time Key Managerial Personnel (KMP) of the Company with effect from 21st "
        "October, 2026, and resignation of Shri Gopal Agarwal, Chief Financial Officer (CFO) "
        "of the Company effective from the close of the business hours on 30th September, 2026."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert not result.endswith("Management i.e.")


def test_no_abbreviation_is_not_mistaken_for_a_sentence_end():
    text = (
        "Zaggle Prepaid Ocean Services Limited has informed that in furtherance to our "
        "announcement vide letter No. ZAGGLE/26-27/46 dated June 30, 2026, we have informed "
        "that Zaggle Prepaid Ocean Services Limited (Zaggle) has entered into an Agreement "
        "dated June 29, 2026 (Original Agreement) with APAC Financial Services Private Limited "
        "and subsequently amended that agreement on a later date as formally recorded."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert not result.endswith("letter No.")


def test_genuine_short_complete_sentence_is_still_accepted_even_when_shorter_than_original():
    """The fix must not overcorrect into refusing every early cut -- a
    REAL, complete sentence (not an abbreviation) is a good outcome even
    if it's shorter than the old buggy 180-char truncation would have
    been, per the 'correctness over specificity' principle."""
    text = (
        "Steel Strips Wheels Limited has informed the Exchange about General Updates. "
        "Pursuant to Regulation 30 of the SEBI (LODR) Regulations 2015, please find enclosed "
        "herewith the specimen copy of letter sent to those shareholders, whose e-mail address "
        "are not registered in the records of the Company/Registrar and Share Transfer Agent "
        "(RTA) of the Company / their respective Depository Participants, inter-alia, providing "
        "the web-link and the exact path to access the Notice of the 40th Annual General Meeting "
        "and the Annual Report of the FY 2025-26 on the Company's website."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert result == "Steel Strips Wheels Limited has informed the Exchange about General Updates."
    assert not result.endswith("…")


def test_pm_abbreviation_is_not_mistaken_for_a_sentence_end():
    text = (
        "The 68th Annual General Meeting ('AGM') of Saurashtra Cement Limited will be held on "
        "Wednesday the 23rd September 2026 at 4:00 p.m. (1ST) via two-way Video Conference (VC) "
        "and other audio visual means as permitted under the applicable regulatory framework for "
        "the conduct of general meetings during the relevant compliance period specified therein "
        "and subject to all other terms and conditions as may be notified by the Company in due course."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert not result.endswith("4:00 p.m.")


def test_wef_abbreviation_is_not_mistaken_for_a_sentence_end():
    """Real specimen (nse-ffc452979c) found via the historical-repair
    inventory re-run, 2026-09-10: 'w.e.f.' was not in the denylist, so the
    classifier correctly quarantined this row rather than applying a bad
    cut -- but the underlying gap was real. Confirms the fix."""
    text = (
        "IL&FS Investment Managers Limited has informed the Exchange regarding "
        "Appointment of  M/s CNK & Associates LLP as Other of the company w.e.f. "
        "August 21, 2026. Appointment  M/s C N K & Associates LLP as the Secretarial "
        "Auditor of the Company for a term of five consecutive years, in accordance "
        "with the applicable provisions of the Companies Act, 2013 and the SEBI "
        "(Listing Obligations and Disclosure Requirements) Regulations, 2015."
    )
    assert len(text) > _MAX_HEADLINE_LEN
    result = _clip_headline(text)
    assert not result.endswith("company w.e.f.")
    assert not result.endswith("w.e.f.")


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

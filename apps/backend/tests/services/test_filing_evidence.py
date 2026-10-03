from app.services.financial_facts import filing_evidence as ev


def test_exact_match_is_compared_at_the_printed_precision_not_by_percentage():
    assert ev.exact_at_printed_precision("1,043.71", "crore", 1043.71)
    assert ev.exact_at_printed_precision("104370.85", "lakh", 1043.7085)
    assert ev.exact_at_printed_precision("89913.33", "crore", 89913.33)
    assert ev.exact_at_printed_precision("1,075,675", "crore", 1075675.0)
    assert not ev.exact_at_printed_precision("104370.85", "lakh", 1050.00)      # a 0.6% tolerance would have passed this
    # the page prints 1,118.94 lakh (raw filed value 11.1894 Cr): the thumbnail misread 1,118.88 is NOT an exact match
    assert ev.exact_at_printed_precision("1,118.94", "lakh", 11.1894)
    assert not ev.exact_at_printed_precision("1,118.88", "lakh", 11.1894)
    assert not ev.exact_at_printed_precision("6,294.89", "crore", 6290.00)


def test_a_stray_ocr_space_inside_the_digits_is_normalised_but_other_junk_is_rejected():
    assert ev.parse_printed_number("29 096.38") == (29096.38, 2)
    assert ev.parse_printed_number("(1,544.43)") == (-1544.43, 2)
    assert ev.parse_printed_number("1,~75,675") is None   # garbled OCR is not a number: never a match
    assert ev.exact_at_printed_precision("29 096.38", "lakh", 290.9638)


def test_only_full_resolution_images_and_exact_text_verify():
    assert ev.status(ev.Evidence("revenue", 1.0, "image", page=3, dpi=130)) == "VERIFIED"
    assert ev.status(ev.Evidence("revenue", 1.0, "exact_text", page=3, matched="1,043.71")) == "VERIFIED"
    assert ev.status(ev.Evidence("profit", 11.19, "image", page=3, dpi=96)) == "UNVERIFIED"      # contact-sheet / thumbnail resolution
    assert ev.status(ev.Evidence("profit", 11.19, "thumbnail", page=3, dpi=60)) == "UNVERIFIED"
    assert ev.status(ev.Evidence("profit", 11.19, "tolerance_text", page=3, matched="1,120.00")) == "UNVERIFIED"
    assert ev.status(ev.Evidence("profit", 11.19, "none")) == "UNVERIFIED"

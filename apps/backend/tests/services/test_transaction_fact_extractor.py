"""
Deep Filing Evidence Phase 1C — real tests for transaction_fact_extractor.py.

Fixture text is the REAL, frozen extracted text of two real production
specimens (Deep Filing Evidence Source Reality Audit, 2026-09-17),
fetched once and embedded here verbatim -- no network required to run
these, and no risk of the real NSE archive changing/removing the
document out from under this regression suite.

ZODIAC (nse-4021315061): a real SEBI Reg 30 filing with a standardized
numbered Annexure I table -- the positive, fully-structured specimen.

PRIMO (nse-302e32d5d4): a real plain-prose disclosure letter with NO
such table and NO consideration figure disclosed anywhere -- the
negative/partial specimen. Its own real text genuinely does not state
a consideration amount; the extractor must report NOT_FOUND for that
field rather than infer one.

Phase 1C-R1 (2026-09-17) adds three more real, frozen specimens from
the unseen 10-filing cohort that first found the two false extractions
R1 fixes -- these are now permanent adversarial regression fixtures:

AUROPHARMA: real text where the consideration LABEL itself contains
the words "share swap" (as one of the enumerated options the question
lists), while the real ANSWER states "100% subscription to the share
capital in cash". Before R1 this misclassified as SHARE_SWAP. Must
resolve to CASH.

JUNIPER: real text stating "Cash consideration of Rs. 2,48,00,00,000/-
(Rupees Two Hundred Forty-Eight Crores Only)" in its own scoped
Annexure field, while a SEPARATE press-release annexure page
separately restates the same deal as "an aggregate consideration of
₹248 crore". Before R1, "Rs." wasn't recognized in the scoped field,
so extraction fell through to an unscoped whole-document search that
found the unrelated "₹248" (dropping the crore multiplier) instead of
never falling back at all. Must resolve to 2,480,000,000 INR from its
own scoped field, or NOT_FOUND -- never the bare, wrong "248".

IBULLSLTD: a genuine real share-swap deal ("issuance of upto 21 crore
fully paid-up equity shares of Indiabulls Limited") that never uses
the literal words "share swap" anywhere in its own answer text. This
is the proof R1 didn't just bias consideration_type toward CASH --
generalizing to a real, differently-worded genuine SHARE_SWAP case is
still correctly detected.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_document import EXTRACTED, SourceDocument
from app.db.models.source_registry import Source
from app.db.models.transaction_fact import (
    CONSIDERATION_AMOUNT, CONSIDERATION_TYPE, NOT_FOUND, POPULATED, STAKE_PERCENTAGE,
    TARGET_ENTITY_NAME, TransactionFact,
)
from app.db.session import AsyncSessionLocal
from app.services.warehouse.transaction_fact_extractor import extract_transaction_facts, persist_transaction_facts

ZODIAC_PAGE_1 = (
    " \n \n Date: September 15, 2026 \n \nTo, \nBSE Limited                                                                       "
    "National Stock Exchange of India Limited \nP J Towers,                                                                         "
    "“Exchange Plaza”, Bandra – Kurla Complex, \nDalal Street,                                                                         "
    "Bandra East, \nMumbai – 400 001                                                               Mumbai – 400051 \n \n"
    "Scrip Code: 543416                                                           Symbol: ZODIAC \n \nDear Sir/Madam, \n \n"
    "Sub: Disclosure pursuant to Regulation 30 of the SEBI (Listing Obligations and Disclosure Requirements) \n"
    "Regulations, 2015 regarding the Incorporation of Wholly Owned Subsidiaries \n \n"
    "Pursuant to Regulation 30 of SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015, we hereby \n"
    "inform you that the Zodiac Energy Limited (“ the Company”) has incorporated a wholly-owned subsidiary through its \n"
    "Authorized Representative, Mr. Kunjbihari Shah.  \n \nThe newly incorporated company is under the name , "
    "“ZODIAC ENERGY IPP-3 PRIVATE LIMITED, Further the \nCertificate of Incorporation dated September 14, 2026 has been "
    "issued by the Registrar of Companies, Ministry of \nCorporate Affairs."
)

ZODIAC_PAGE_2 = (
    " \n \nAnnexure- I \n \nThe Details in respect to Incorporation of Wholly Owned Subsidiaries in India , as required under "
    "Regulation 30 of \nthe SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015,  read with SEBI "
    "Circular No. \nHO/49/14/14(7)2025-CFD-POD2/I/3762/2026 dated January 30, 2026 are given as under: \n \n"
    "Sr. No. Particulars  Details \n"
    "1.  Name of the target entity, details in \nbrief such as size, turnover etc.; \n"
    "Name: ZODIAC ENERGY IPP-3 PRIVATE LIMITED \nCIN: U35100GJ2026PTC183626 \nNominal Share Capital: ₹10,00,000 \n"
    "Turnover: Nil (Company Incorporated on September 14, 2026) \n"
    "2.  Whether the acquisition would fall \nwithin related party transaction(s) and \nwhether the promoter/ promoter \n"
    "group/ group companies have any \ninterest in the entity being acquired? If \nyes, nature of interest and details \n"
    "thereof and whether the same is done \nat “arm’s length”; \n"
    "Zodiac Energy Limited is a holding company of ZODIAC \nENERGY IPP-3 PRIVATE LIMITED. \n \n"
    "Relation with Company: Wholly Owned Subsidiary  \n"
    "3.  Industry to which the entity being \nincorporated belongs;  \nSolar Power Plants & Energy \n"
    "4.  Objects and impact of acquisition \n(including but not limited to, disclosure \nof reasons for acquisition of target \n"
    "entity, if its business is outside the main \nline of business of the listed entity); \n"
    "The wholly owned subsidiary has been incorporated as a Special \nPurpose Vehicle (SPV) to undertake a projects "
    "relating to solar \npower generation, engineering, procurement and construction \n(EPC) activities.  \n \n"
    "5.  Brief details of any governmental or \nregulatory approvals required for the \nacquisition;  \nNot applicable \n"
    "6.  Indicative time period for completion \nof the acquisition \nNot applicable \n"
    "7.  Consideration - whether cash \nconsideration or share swap or any \nother form and details of the same; \n"
    "Cash Consideration \n"
    "8.  Cost of acquisition and/or the price at \nwhich the shares are acquired \n"
    "The Company has subscribed to 100% of the initial paid-up share \ncapital of ₹1,00,000 (Rupees One Lakh Only), "
    "comprising 10,000 \nequity shares of ₹10 each, thereby making the entity a wholly \nowned subsidiary of the Company. \n"
    "9.  Percentage of shareholding / control \nacquired and / or number of shares \nacquired \n"
    "Pursuant to the aforesaid investment, the Company shall hold  \n100% shareholding  and control of the paid-up "
    "share capital of \nZODIAC ENERGY IPP-3 PRIVATE LIMITED  \n"
    "10.  Brief background about the entity \nacquired in terms of products/line of \nbusiness acquired, date of \n"
    "incorporation, history of last 3 years \nturnover, country in which the \nacquired entity has presence and any \n"
    "other significant information (in brief);  \n \n"
    "ZODIAC ENERGY IPP-3 PRIVATE LIMITED is proposed to \nengaged in the business of solar power generation alongside \n"
    "engineering, procurement and construction (EPC) projects."
)

PRIMO_PAGE_1 = (
    "PRIMO\nCHEMICALS\nPCL: SEC: 2026:278 16.09.2026\nBSE Limited\n1 st Floor, New Trading Ring,\nRotunda Building, "
    "P. J. Towers,\nDalaI Street, Fort,\nMumbai-400 001\nScrip Code: 506852\nNational Stock Exchange of India Ltd.\n"
    "Exchange Plaza, 5th Floor\nPlot No. C/1. G Block.\nBandra-Kurla Complex,\nBandra (E), Mumbai – 400 001\n"
    "Scrip Code: PRIMO\nSubject: Disclosure in pursuant to Regulation 30 of the SEBI (Listing Obligations and\n"
    "Disclosure Requirements) Regulations, 2015:- Update on acquisition of Balance 51%\nEquity Stake in Flow Tech "
    "Chemicals Private Limited.\nDear Sir/Madam,\nIn continuation to our earlier disclosure vide Letter No. "
    "PCL:SEC:2026:248 dated 2-d July, 2026\nand pursuant to Regulation 30 read with Schedule III of the SEBI "
    "(Listing Obligations and\nDisclosure Requirements) Regulations, 2015 (“SEBI LODR”), we hereby inform you that, "
    "pursuant\nto the approval of the Members obtained on 5th August, 2026 through Postal Ballot by way of e-\n"
    "voting for the acquisition of the balance 51% equity stake in Flow Tech Chemicals Private Limited\n"
    "(“Flow Tech”) and to make it a wholly owned subsidiary of the Company, the Company has today,\ni.e. 16th "
    "September, 2026, executed the 2nd Supplementary Share Purchase Agreement and\nacquired the balance 51% equity "
    "stake in Flow Tech from its existing shareholders (other than\nPrimo Chemicals Limited).\nConsequent upon the "
    "aforesaid acquisition, Flow Tech Chemicals Private Limited has become a\nwholly owned subsidiary of the Company."
)

# Real cohort specimen, lettered items (a, b, c...): the consideration
# LABEL itself contains "share swap" as one of its enumerated options;
# the real ANSWER is "...in cash". Pre-R1 this misclassified SHARE_SWAP.
AUROPHARMA_PAGE_2 = (
    "Annexure ·A \nDisclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requirements) Regulations, \n2015 \n"
    "a) Name of the target entity, details in brief such \nas size, turnover etc.; \nName: A1 Biochem USA Inc \n"
    "Turnover: Not applicable as the company is yet to \ncommence business \n"
    "b) Whether the acquisition would fall within \nrelated party transaction(s) and whether the \npromoter / promoter group / group companies \n"
    "have any interest in the entity being acquired? If \nyes, nature of interest and details thereof and \nwhether the same is done at \"arms-length\"; \n"
    "A1 Biochem USA Inc  is a wholly owned subsidiary of A1 \nBiochem Labs (India) Private Limited.  A1 Biochem Labs \n"
    "India Private Limited is a subsidiary of Apitoria Pharma \nPrivate Limited, a wholly owned subsidiary of the \n"
    "Company and therefore is a related party of the \nCompany. Promoters and promoter group of the \nCompany are not interested in the transaction \n"
    "c) Industry to which the business of the target \nentity being acquired belongs; \nPharmaceuticals \n"
    "d) Objects and effects of acquisition (including \nbut not limited to, disclosure of reasons for \nacquisition of target entity, if its business is \n"
    "outside the main line of business of the listed \nentity); \nThe object of  this subsidiary is to undertake the \nContract Research and Development services business \n"
    "as part of the acquisition of A1 Biochem Group earlier \ndisclosed on July 23, 2026. \n"
    "e) Brief details of any governmental or regulatory \napprovals required for the acquisition. \nNo governmental or regulatory approvals required. \n"
    "f) Indicative time period for completion of the \nacquisition. \nNot applicable \n"
    "g) Nature of consideration - whether cash \nconsideration or share swap or any other form \nand details of the same; \n"
    "100% subscription to the share capital in cash \n"
    "h) Cost of acquisition and / or the price at which \nthe shares are acquired; New Subsidiary was \nincorporated. \n"
    "The Company has subscribed to the Initial subscription \nshare capital of USD 1,000,000 on September 11, 2026 \ndivided into 10,000 equity shares of USD 100 each. \n"
    "i) Percentage of shareholding / control acquired \nand or number of shares acquired; \n100% \n"
    "j) Brief background about the entity acquired in \nterms of products/line of business acquired, date \nof incorporation, history of last 3 years turnover, \n"
    "country in which the acquired entity has \npresence and any other significant information \n(in brief); \n"
    "This is a newly incorporated company and therefore the \nhistory of the last 3 years' turnover is not available."
)

# Real cohort specimen, number-without-period items ("7 ", "8 ", "9 "):
# the scoped field states "Rs. 2,48,00,00,000/-" (Rs., not ₹); a
# SEPARATE press-release annexure page later restates the same deal as
# "₹248 crore". Pre-R1, "Rs." wasn't recognized so the scoped match
# failed, and an unscoped whole-document fallback then grabbed the
# unrelated "₹248" (dropping "crore") from the other page.
JUNIPER_PAGE_4 = (
    "Juniper Hotels Limited (Formerly known                  Registered Office Address: off Western                      complianceofficer@juniperhotels.com \n"
    "as Juniper Hotels Private Limited)                                Express Highway, Santacruz (East)                             022-66761000/1012 \n"
    "CIN: L55101MH1985PLC152863                                 Mumbai, Maharashtra 400055, India                          www.juniperhotels.com \n"
    "parties and receipt of requisite regulatory, statutory \nand other approvals/consents, as may be required \nfrom time to time. \n"
    "7 Nature of consideration - whether cash \nconsideration or share swap or any other \nform and details of the same; \n"
    "Cash consideration of Rs. 2,48,00,00,000/- (Rupees \nTwo Hundred Forty-Eight Crores Only), subject to tax \n"
    "deduction at source, stamp duty, transaction costs \nand other adjustments, if any and subject to the \nterms and conditions mentioned in the definitive \ndocuments \n"
    "8 Cost of acquisition or the price at \nthe shares are acquired; \n"
    "Rs. 2,48,00,00,000/- (Rupees Two Hundred Forty-\nEight Crores Only), subject to tax deduction at source, \n"
    "stamp duty, transaction costs and other adjustments, \nif any and subject to the terms and conditions \nmentioned in the definitive documents \n"
    "9 Percentage of shareholding/ control \nacquired and/ or number of shares \nacquired; \n"
    "Not Applicable as no acquisition of control/ shares/ \nvoting rights is being contemplated \n"
    "10 Brief background about the entity \nacquired in terms of products/line of \nbusiness acquired, date of incorporation, \n"
    "history of last 3 years turnover, country in \nwhich the acquired entity has presence \nand any other significant information (in \nbrief); \n"
    "Not applicable to the extent no shares, voting rights \nor control in an entity are being acquired."
)

JUNIPER_PAGE_7_PRESS_RELEASE = (
    "Juniper Hotels Limited (Formerly known                  Registered Office Address: off Western                      complianceofficer@juniperhotels.com \n"
    "ANNEXURE C \nMEDIA RELEASE \nDELIVERING ON GROWTH COMMITMENT \n"
    "Juniper Hotels Announces Proposed Acquisition of Novotel Imagicaa for Rs 248 Crore \n"
    "Mumbai, September 16, 2026: Juniper Hotels Limited (“Juniper” or “the Company”), one of India's leading \n"
    "luxury hotel development and ownership companies, today announced the proposed acquisition of an \n"
    "operating hotel, Novotel Imagicaa from Imagicaaworld Entertainment Limited (formerly known as Adlabs \n"
    "Entertainment Limited) for an aggregate consideration of ₹248 crore at approximately ₹86 lakh per key, \n"
    "subject to the terms and conditions of the definitive agreements."
)

# Real cohort specimen, lettered items: a genuine share-swap deal that
# never uses the literal words "share swap" in its own answer text --
# proves R1 didn't just bias the parser toward CASH.
IBULLSLTD_PAGE_2 = (
    "“Annexure A” \nInformations pursuant to Regulation 30 of Listing Regulations read with SEBI Master Circular No. \n"
    "HO/49/14/14(7)2025-CFD-POD2/I/3762/2026 dated January 30, 2026: \n"
    "a) name of the target entity, details in \nbrief such as size, turnover etc. \n"
    "Fintech Cloud Private Limited is acting as Loan Ser-\nvice provider  (LSP) for various Regulated entities  \n"
    "(RE's) and has earned a gross revenue of Rs. 133.77 \nCr in FY 2025-26 with PBT of Rs. 30.31 Cr. \n"
    "b) whether the acquisition would fall \nwithin related party transaction(s) \nand whether the promoter/ promoter \n"
    "group/ group companies have any in-\nterest in the entity being acquired? If \nyes, nature of interest and details \n"
    "thereof and whether the same is done \nat “arm's length”; \n"
    "The Proposed Acquisition does not fall under related \nparty transaction. \n"
    "Further, the promoter/ promoter group/ group compa-\nnies do not have any interest in the entity being ac-\nquired. \n"
    "c) industry to which the entities being \nacquired belong; \nTechnology Solutions \n"
    "d) objects and effects of acquisition (in-\ncluding but not limited to, disclosure \nof reasons for acquisition of target \n"
    "entity, if its business is outside the \nmain line of business of the listed en-\ntity); \n"
    "The Proposed Acquisition will enable the Company to \nenter the fintech segment, through a business that pro-\nvides technology solutions to NBFCs. \n"
    "e) brief details of any governmental or \nregulatory approvals required for the \nacquisition; \n"
    "NCLT and SEBI/Stock Exchanges approval will be re-\nquired along with other applicable regulatory / share-\nholders' approval. \n"
    "f) indicative time period for comple-\ntion of the acquisition; \n9 -12 months \n"
    "g) consideration - whether cash consid-\neration or share swap or any other \nform and details of the same; \n"
    "Consideration will be settled through issuance of upto \n21 crore fully paid-up equity shares of Indiabulls Lim-\nited, to the shareholder(s) holding 70% shares of the \n"
    "Target Company, pursuant to an NCLT approved \nScheme of Amalgamation  to be undertaken by             \nIndiabulls Limited and the shareholder(s) holding \n"
    "70% shares of the Target Company, subject to compli-\nance with pricing regulations as per applicable regula-\ntions (including SEBI ICDR regulations) and other ap-\nplicable regulations. \n"
    "h) cost of acquisition and/or the price at \nwhich the shares are acquired; \n"
    "Rs. 1,050 crore (being 70% of the equity value of the \nTarget Company)."
)

IBULLSLTD_PAGE_3 = (
    "i) percentage of shareholding / control \nacquired and / or number of shares \nacquired; \n"
    "(i) 70% stake of the Target Company to be acquired \npursuant to an NCLT approved Scheme of Amalgam-\n"
    "ation involving the Company and the shareholder(s) \nholding 70% shares of the Target Company; and \n"
    "(ii) With immediate effect, the majority of directors of \nthe Target Company shall be appointed by Indiabulls \nLimited. \n"
    "j) brief background about the entity ac-\nquired in terms of products/line of \nbusiness acquired, date of incorpora-\n"
    "tion, history of last 3 years turnover, \ncountry in which the acquired entity \nhas presence and any other signifi-\ncant information (in brief); \n"
    "Product Line : Loan service provider (LSP) \nDate of Incorporation  : January 11, 2021 \n"
    "Turnover : \nFY 2023-24 - Nil     \nFY 2024-25 - Nil \nFY 2025-26 - Rs. 133.77 Cr. approx."
)


def _by_field(candidates):
    return {c.field_code: c for c in candidates}


# ── Pure extraction: real ZODIAC specimen (structured table) ────────────

def test_zodiac_target_entity_name_is_bound_via_its_own_table_label():
    fields = _by_field(extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.extraction_method == "sebi_reg30_annexure_table"
    assert f.value_text == "ZODIAC ENERGY IPP-3 PRIVATE LIMITED"
    assert f.page_number == 2
    assert "Name:" in f.source_span_text


def test_zodiac_stake_percentage_is_bound_to_its_own_labeled_row_not_any_stray_percent():
    """Real regression concern: item 8's own span also contains '100%'
    (the paid-up share capital subscription), a DIFFERENT real fact
    from item 9's stake/control percentage. Confirms the extractor
    binds to the field's OWN scoped span, not the first percent found
    anywhere in the document."""
    fields = _by_field(extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2]))
    f = fields[STAKE_PERCENTAGE]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 100.0
    assert f.unit == "pct"
    assert "shareholding" in f.source_span_text.lower()


def test_zodiac_consideration_type_is_cash():
    fields = _by_field(extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2]))
    f = fields[CONSIDERATION_TYPE]
    assert f.extraction_status == POPULATED
    assert f.value_text == "CASH"


def test_zodiac_consideration_amount_is_bound_to_the_cost_of_acquisition_row():
    fields = _by_field(extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 100000.0
    assert f.unit == "inr"


def test_zodiac_extraction_returns_exactly_one_row_per_known_field():
    fields = extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2])
    assert {f.field_code for f in fields} == {TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT}
    assert all(f.extraction_status == POPULATED for f in fields)


def test_every_candidate_carries_an_extraction_method_version():
    """Lets a later reader distinguish a fact produced by one version of
    a deterministic rule from a future version that reuses the same
    method name -- checked across both POPULATED and NOT_FOUND rows."""
    zodiac_fields = extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2])
    primo_fields = extract_transaction_facts([PRIMO_PAGE_1])
    assert all(f.extraction_method_version for f in zodiac_fields)
    assert all(f.extraction_method_version for f in primo_fields)


# ── Pure extraction: real PRIMO specimen (prose, negative case) ─────────

def test_primo_stake_and_target_are_bound_via_the_same_real_coherent_phrase():
    fields = _by_field(extract_transaction_facts([PRIMO_PAGE_1]))
    stake, target = fields[STAKE_PERCENTAGE], fields[TARGET_ENTITY_NAME]
    assert stake.extraction_status == POPULATED
    assert stake.value_numeric == 51.0
    assert target.extraction_status == POPULATED
    assert target.value_text == "Flow Tech Chemicals Private Limited"
    assert stake.extraction_method == "prose_stake_and_target_phrase"
    assert target.extraction_method == "prose_stake_and_target_phrase"


def test_primo_consideration_is_not_found_never_inferred():
    """The core Phase 1C negative specimen: PRIMO's real filing text
    genuinely never states a consideration figure or type anywhere.
    Both consideration fields must be NOT_FOUND, never a guessed or
    interpolated value."""
    fields = _by_field(extract_transaction_facts([PRIMO_PAGE_1]))
    assert fields[CONSIDERATION_AMOUNT].extraction_status == NOT_FOUND
    assert fields[CONSIDERATION_AMOUNT].value_numeric is None
    assert fields[CONSIDERATION_TYPE].extraction_status == NOT_FOUND
    assert fields[CONSIDERATION_TYPE].value_text is None


def test_primo_extraction_still_returns_exactly_one_row_per_known_field():
    fields = extract_transaction_facts([PRIMO_PAGE_1])
    assert {f.field_code for f in fields} == {TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT}


def test_document_with_no_recognizable_pattern_at_all_reports_every_field_not_found():
    fields = extract_transaction_facts(["This is an unrelated regulatory notice about a record date for dividend."])
    assert all(f.extraction_status == NOT_FOUND for f in fields)
    assert all(f.value_text is None and f.value_numeric is None for f in fields)


# ── Phase 1C-R1 regression: unseen-cohort false extractions ──────────────

def test_aurophama_consideration_is_cash_never_share_swap_from_the_label_text():
    """The confirmed R1 false extraction: the field's own LABEL lists
    'share swap' as an enumerated option, but the real ANSWER is '...in
    cash'. Must resolve CASH, and the label's own 'share swap' mention
    must never leak into the classified answer."""
    fields = _by_field(extract_transaction_facts([AUROPHARMA_PAGE_2]))
    f = fields[CONSIDERATION_TYPE]
    assert f.extraction_status == POPULATED
    assert f.value_text == "CASH"
    assert "share swap" not in (f.source_span_text or "").lower()


def test_aurophama_target_and_stake_still_correct_after_r1():
    """Confirms R1's boundary/label changes didn't regress the two
    fields that were already correct pre-R1 for this same specimen."""
    fields = _by_field(extract_transaction_facts([AUROPHARMA_PAGE_2]))
    assert fields[TARGET_ENTITY_NAME].value_text == "A1 Biochem USA Inc"
    assert fields[STAKE_PERCENTAGE].value_numeric == 100.0


def test_juniper_consideration_amount_is_the_real_crore_value_never_the_unrelated_248():
    """The confirmed R1 false extraction: pre-R1 this returned a bare
    248 (from an unrelated press-release page's '₹248 crore' mention,
    with the crore multiplier silently dropped) instead of the real
    2,480,000,000 stated in the filing's own scoped Annexure field."""
    fields = _by_field(extract_transaction_facts([JUNIPER_PAGE_4, JUNIPER_PAGE_7_PRESS_RELEASE]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 2_480_000_000.0
    assert f.unit == "inr"
    assert f.page_number == 1  # bound to its own Annexure field (page 4 = list index 0), never the press-release page


def test_juniper_consideration_amount_is_not_found_when_only_the_unrelated_press_release_page_exists():
    """A recognized field with an unsupported/absent value in its own
    scope must be NOT_FOUND -- never escape to a different page for a
    replacement number. With ONLY the press-release page present (no
    scoped Annexure field at all), the field must stay NOT_FOUND."""
    fields = _by_field(extract_transaction_facts([JUNIPER_PAGE_7_PRESS_RELEASE]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == NOT_FOUND
    assert f.value_numeric is None


def test_ibullsltd_genuine_share_swap_is_detected_without_the_literal_words_share_swap():
    """Proves R1 didn't simply bias the parser toward CASH: a real
    share-swap deal described as 'issuance of ... equity shares' (the
    literal words 'share swap' appear only in the label, which is
    trimmed away) must still resolve to SHARE_SWAP."""
    fields = _by_field(extract_transaction_facts([IBULLSLTD_PAGE_2, IBULLSLTD_PAGE_3]))
    f = fields[CONSIDERATION_TYPE]
    assert f.extraction_status == POPULATED
    assert f.value_text == "SHARE_SWAP"
    assert "issuance" in (f.source_span_text or "").lower()


def test_ibullsltd_stake_percentage_still_correct_after_r1():
    fields = _by_field(extract_transaction_facts([IBULLSLTD_PAGE_2, IBULLSLTD_PAGE_3]))
    assert fields[STAKE_PERCENTAGE].value_numeric == 70.0


def test_rs_prefix_is_recognized_same_as_the_rupee_symbol():
    fields = _by_field(extract_transaction_facts([
        "7 Nature of consideration - whether cash consideration or share swap or any other form and details of the same; "
        "Cash consideration of Rs. 5,00,000/-. \n8 Cost of acquisition or the price at which the shares are acquired; "
        "Rs. 5,00,000/-. \n9 Percentage of shareholding acquired; 100%"
    ]))
    assert fields[CONSIDERATION_AMOUNT].extraction_status == POPULATED
    assert fields[CONSIDERATION_AMOUNT].value_numeric == 500000.0


def test_bare_crore_amount_without_full_indian_digit_grouping_is_normalized_correctly():
    fields = _by_field(extract_transaction_facts([
        "7 Nature of consideration - whether cash consideration or share swap or any other form and details of the same; "
        "Cash consideration of ₹5 crore. \n8 Cost of acquisition or the price at which the shares are acquired; "
        "₹5 crore. \n9 Percentage of shareholding acquired; 100%"
    ]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 50_000_000.0


def test_bare_number_with_no_comma_and_no_clean_magnitude_word_is_not_found_never_a_naked_number():
    """Synthetic reproduction of the real MAITHANALL OCR-corruption
    pattern found while rerunning the frozen cohort after the first R1
    fix ("Rs. 113.3? Crore" -- a stray corrupted character breaks the
    number-to-magnitude-word adjacency). A comma-free number with no
    cleanly-attached magnitude word must never be accepted as a bare
    rupee figure -- that would be exactly the naked-number-to-INR
    inference this extractor must never make."""
    fields = _by_field(extract_transaction_facts([
        "7 Nature of consideration - whether cash consideration or share swap or any other form and details of the same; "
        "Cash Consideration \n8 Cost of acquisition or the price at which the shares are acquired; "
        "Total Cost of acquisition Rs. 113.3? Crore on 10th September, 2026 "
        "\n9 Percentage of shareholding acquired; 100%"
    ]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == NOT_FOUND
    assert f.value_numeric is None


def test_clean_decimal_crore_amount_is_still_extractable_the_same_figure_corruption_free():
    """The exact same decimal figure as the corrupted-notation test
    above (113.3), but with the magnitude word cleanly attached instead
    of separated by a stray corrupted character. Confirms the R1 safety
    fix targets the CORRUPTION specifically, not decimal-crore amounts
    in general -- a real, clean 'Rs. 113.3 Crore' must still populate."""
    fields = _by_field(extract_transaction_facts([
        "7 Nature of consideration - whether cash consideration or share swap or any other form and details of the same; "
        "Cash Consideration \n8 Cost of acquisition or the price at which the shares are acquired; "
        "Total Cost of acquisition Rs. 113.3 Crore on 10th September, 2026 "
        "\n9 Percentage of shareholding acquired; 100%"
    ]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 1_133_000_000.0


def test_comma_grouped_number_with_no_magnitude_word_is_still_accepted():
    """A genuine fully-expanded Indian-grouped figure (real commas) is a
    complete rupee amount on its own -- it must not require a magnitude
    word just because one happens to be absent."""
    fields = _by_field(extract_transaction_facts([
        "7 Nature of consideration - whether cash consideration or share swap or any other form and details of the same; "
        "Cash consideration of Rs. 1,10,00,000/-. \n8 Cost of acquisition or the price at which the shares are acquired; "
        "Rs. 1,10,00,000/-. \n9 Percentage of shareholding acquired; 100%"
    ]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == POPULATED
    assert f.value_numeric == 11_000_000.0


# ── Persistence: real DB-backed ──────────────────────────────────────────

async def _seed_source_document(db, page_texts: list[str]) -> tuple[str, str]:
    import json as _json
    source_id = f"test_source_{uuid.uuid4().hex[:8]}"
    db.add(Source(id=source_id, name="Test Source", source_type="api", collection_method="test"))
    await db.commit()

    raw_evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=raw_evidence_id, evidence_key=f"test:{uuid.uuid4().hex[:8]}", payload_hash="x",
        source_id=source_id, source_type="nse", observed_at=now, ingested_at=now,
        mime_type="application/json", quality="good",
    ))
    await db.commit()

    doc_id = str(uuid.uuid4())
    db.add(SourceDocument(
        id=doc_id, raw_evidence_id=raw_evidence_id, canonical_url="https://example.test/doc.pdf",
        content_hash=uuid.uuid4().hex, byte_size=1000, mime_type="application/pdf",
        retrieved_at=now, extraction_status=EXTRACTED, extraction_method="pypdf",
        extraction_method_version="test", page_count=len(page_texts),
        page_texts_json=_json.dumps(page_texts),
    ))
    await db.commit()
    return doc_id, raw_evidence_id


async def _cleanup(source_document_id: str, raw_evidence_id: str) -> None:
    async with AsyncSessionLocal() as db:
        source_id = (await db.execute(
            select(RawEvidence.source_id).where(RawEvidence.id == raw_evidence_id)
        )).scalar_one_or_none()
        await db.execute(delete(TransactionFact).where(TransactionFact.source_document_id == source_document_id))
        await db.execute(delete(SourceDocument).where(SourceDocument.id == source_document_id))
        await db.execute(delete(RawEvidence).where(RawEvidence.id == raw_evidence_id))
        if source_id:
            await db.execute(delete(Source).where(Source.id == source_id))
        await db.commit()


@pytest.mark.asyncio
async def test_real_zodiac_facts_persist_with_full_provenance():
    async with AsyncSessionLocal() as db:
        doc_id, raw_evidence_id = await _seed_source_document(db, [ZODIAC_PAGE_1, ZODIAC_PAGE_2])
        try:
            candidates = extract_transaction_facts([ZODIAC_PAGE_1, ZODIAC_PAGE_2])
            rows = await persist_transaction_facts(db, source_document_id=doc_id, raw_evidence_id=raw_evidence_id, candidates=candidates)
            assert len(rows) == 4
            by_field = {r.field_code: r for r in rows}
            assert by_field[STAKE_PERCENTAGE].value_numeric == 100.0
            assert by_field[STAKE_PERCENTAGE].source_document_id == doc_id
            assert by_field[STAKE_PERCENTAGE].raw_evidence_id == raw_evidence_id
            assert by_field[STAKE_PERCENTAGE].page_number == 2
            assert by_field[STAKE_PERCENTAGE].source_span_text  # real provenance text, not empty
        finally:
            await _cleanup(doc_id, raw_evidence_id)


@pytest.mark.asyncio
async def test_rerunning_extraction_replaces_the_field_row_not_duplicates_it():
    async with AsyncSessionLocal() as db:
        doc_id, raw_evidence_id = await _seed_source_document(db, [PRIMO_PAGE_1])
        try:
            candidates = extract_transaction_facts([PRIMO_PAGE_1])
            first_rows = await persist_transaction_facts(db, source_document_id=doc_id, raw_evidence_id=raw_evidence_id, candidates=candidates)
            second_rows = await persist_transaction_facts(db, source_document_id=doc_id, raw_evidence_id=raw_evidence_id, candidates=candidates)
            assert len(first_rows) == len(second_rows) == 4
            assert {r.id for r in first_rows} == {r.id for r in second_rows}  # same rows updated, not duplicated
        finally:
            await _cleanup(doc_id, raw_evidence_id)

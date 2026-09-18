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

Phase 1C-R2 + TargetFact R1 (owner design, 2026-09-18) add real, frozen
fixtures from the Assembly V2 fresh-cohort audit (2026-09-18, a
genuinely unseen cohort -- none of these specimens were used to build
or tune the original extractor):

GUJENERGY: a real filing that CRASHED extract_transaction_facts() with
an unhandled ValueError -- a shareholder tax-cost note whose "Cost of
acquisition" phrase (used generically, not as a real transaction table)
has no numbered item after it, so its span runs to the end of the page
and genuinely contains "...their respective shareholders, pursuant
to...". The incidental "rs," substring (the tail of "shareholders"
immediately followed by a comma) was misread as a currency token with
an empty numeric capture. Must never crash; must resolve NOT_FOUND.

DALBHARAT, GREENLAM, UTLSOLAR, INDIACEM: real target_entity_name
answers stated bare, with no "Name:" sub-label at all -- 4 of the 6
real misses the audit found, and the dominant recurring shape.

HMVL: a real target_entity_name answer with a "Target Entity" sub-label
(no colon) immediately before the name -- without a natural character-
class boundary, a naive corporate-suffix fallback would sweep the
sub-label itself into the captured name.
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


# TargetFact R1 (2026-09-18): real Annexure pages, verbatim, from the
# Assembly V2 fresh-cohort audit -- each demonstrates one of the two
# recurring real shapes _TABLE_NAME_FALLBACK_RE covers (bare corporate
# name, or a short sub-label with no colon before it).
DALBHARAT_PAGE_2 = (
    " \n \nAnnexure \n \nSr. \nNo. \nParticular Details \na)  Name of the target entity, details in brief such \n"
    "as size, turnover etc.; \nAMPL Green City Solutions Private Limited \n \n \nb)  Whether the acquisition would fall within \n"
    "related party transaction(s) and whether the \npromoter/ promoter group/ group companies \n"
    "have any interest in the entity being acquired? \nIf yes, nature of interest and details thereof \n"
    "and whether the same is done at “arm’s \nlength”; \nThe acquisition will not fall within related party \n"
    "transaction and the promoter/ promoter group \ncompanies have no interest in the proposed \nacquisition. \n"
    "g)  Nature of consideration - whether cash \nconsideration or share swap and details of the \nsame; \nCash Consideration \n"
    "h)  Cost of acquisition or the price at which the \nshares are acquired; \n10,000 equity shares of face value Rs. 10/- each, at par. \n"
    "i)  Percentage of shareholding / control acquired \nand/or number of shares acquired; \n100% \n"
)

HMVL_PAGE_2 = (
    "(Annexure) \n \nInformation as required under Regulation 30 of SEBI (Listing Obligations and Disclosure Requirements) \n"
    "Regulations, 2015 \n \n S.No Particulars Information \na) Name of the target entity, details in  brief such as \n"
    "size, turnover etc. \nTarget Entity \nAssetgro Fintech Private Limited \n(“StockGro”)                         \n"
    "Last 3 years’ turnover of StockGro \nFY26: Rs. 231.10 Crore \nFY25: Rs. 125.51 Crore \nFY24 : Rs. 99 Crore \n"
    "g) Consideration – whether cash  consideration or \nshare swap and details of the same \n"
    "Conversion of OCDs into equity shares "
)
HMVL_PAGE_3 = (
    "h) Cost of acquisition and/or the price at which  the \nshares are acquired \n"
    "Conversion of 8,708 OCDs into 16,02,011 equity shares \namounting to Rs. 85.00 Crore \n"
    "i) Percentage of shareholding / control acquired and \n/ or number of                shares acquired \n"
    "2.48% of equity share capital of StockGro pursuant to \nconversion of 8,708 OCDs. \n"
)

GREENLAM_PAGE_2 = (
    " \n  \nAnnexure  \n \nSl . \nNo. \nParticulars Details \na.  Name of the target entity, \ndetails in  brief such as size, \n"
    "turnover etc. \nBhadla Minigrid Solar 4 Private Limited  (Bhadla Minigrid) \nis a company incorporated in India on 31.01.2025. Bhadla \n"
    "Minigrid was incorporated to carry on, inter-alia, the business \nof renewable energy and  generation of electrical power by \n"
    "conventional and non -conventional methods, in the field of \nRenewable Energy.  \n"
    "g.  Nature of consideration – \nwhether cash consideration or \nshare swap or  any other form \n"
    "and details of the same \nCash consideration \n"
    "h.  Cost of acquisition and/or the \nprice at  which the shares are \nacquired \n \n"
    "Rs. 2,06,50,010 in aggregate for  acquisition of 20,65,001 \nequity shares of Rs. 10/- each. "
)
GREENLAM_PAGE_3 = (
    " \n  \n \nSl . \nNo. \nParticulars Details \ni.  Percentage of shareholding / \ncontrol acquired and / or \n"
    "number of shares acquired. \n \n26%. \n"
)

UTLSOLAR_PAGE_2 = (
    " \n \nAnnexure-A \nThe details, as required under the SEBI (Listing Obligations and Disclosure Requirements) \n"
    "Regulations, 2015 read with SEBI Master Circular bearing reference no. HO/49/14/14(7)2025- \n"
    "CFD-POD2/1/3762/2026 dated January 30, 2026, are as under: \n S. No. Details Particulars \n"
    "1. Name of the target entity, details in brief \nsuch as size, turnover etc. \nZayo Energy Private Limited ( “ZEPL”) \n"
    "(CIN: U27320DL2022PTC399031) is a \nprivate limited company incorporated under \nthe provisions of the Companies Act, 2013 \n"
    "having its registered Office at Plot No 4, \nRoad No 5, G/F Jai Dev Park, East Punjabi \nBagh, West Delhi, India, 110026. \n"
    "7. Nature of consideration - whether cash \nconsideration or share swap and details of \nthe same. \nCash consideration \n"
    "8. Cost of acquisition or the price at which the \nshares are acquired. \nThe Company intends to invest Rs.  \n"
    "5,00,57,469/- (Rupees Five Crore Fifty -\nSeven Thousand Four Hundred and Sixty -\nNine only)  by subscribing 833 Compulsory \n"
    "Convertible Debentures (“CCDs”) at a value \nof Rs. 60,093 (including  Face Value of Rs. \n10 and premium 60,083) \n"
)

HERANBA_PAGE_2 = (
    " \nAnnexures - I \nThe details of acquisition/ investment pursuant to allotment of equity shares as required under \n"
    "Regulation 30 read with the SEBI Master Circular  SEBYHO/CFD/PoD2/CIR/P/0155 dated \n"
    "January 30, 2026. \nSr. \nNo.  \nParticulars  Description  \n1. Name of the target entity, details in \n"
    "brief such as size, turnover etc. \nName of Entity : Mikusu India Private \nLimited, wholly owned subsidiary of the \nCompany. \n"
)
HERANBA_PAGE_3 = (
    " \n7. Consideration - whether cash  \nconsideration or share swap or any \nother form and details of the same \n \nCash \n"
    "8. Cost of acquisition and/or the price at \nwhich the shares are acquired \n"
    "Rs.24,95,00,000/- (Rupees Twenty-Four Crores \nNinety-Five Lakhs Only), of which \n"
    "Rs.12,47,50,000/- has been paid towards \napplication and allotment money. \n"
    "9. Percentage of shareholding / control \nacquired and / or number of shares \nacquired \n"
    "There will be no change in the shareholding \nstructure. Mikusu India Private Limited shall \ncontinue to remain a wholly owned subsidiary \n"
    "of the Company and the Company shall \ncontinue to hold 100% of the equity share \ncapital of Mikusu India Private Limited. \n"
)

# TargetFact R1 validation (owner instruction, 2026-09-18): fetched
# AFTER the fix was written, from a genuinely unseen fresh-validation
# cohort (NEPHROPLUS, VERTOZ, GUJTHEM, WELINV, SHANTIGOLD, RGL --
# none used to diagnose or build the fix). NEPHROPLUS is the cleanest
# direct proof: a real, bare (no sub-label) target answer the new
# fallback -- not the pre-existing "Name:" pattern -- is what resolves
# it (VERTOZ/SHANTIGOLD/RGL in this same validation cohort all used the
# pre-existing "Name:" pattern instead, already covered before this
# fix; GUJTHEM/WELINV genuinely lack a Reg 30 Annexure table at all --
# correctly stay NOT_FOUND, out of this fix's demonstrated scope).
NEPHROPLUS_PAGE_2 = (
    " \n \nANNEXURE I \n \nSr. \nNo Particulars Description \n1. Name of the target entity, details in \n"
    "brief such as size, turnover etc. \nDialysis Center Almaty LLP (“ Target Entity”), a \n"
    "limited liability partnership incorporated under \nthe laws of the Republic of Kazakhstan. The \n"
    "Target Entity is engaged in the business of \nproviding dialysis services through its dialysis \n"
    "centres in Kazakhstan. Last audited turnover of \nthe Target Entity is KZT 527.44 million (approx. \n₹10.93 crore). \n"
    "2. Whether the acquisition would fall \nwithin related party transaction(s) \n"
    "and whether the promoter/promoter \ngroup/group companies have any \ninterest in the entity being acquired? \n"
    "If yes, nature of interest and details \nthereof and whether the same is \ndone at “arm’s length”. \n"
    "The acquisition does not constitute a related \nparty transaction. \n"
)

INDIACEM_PAGE_2 = (
    " \n \nE: investor.indiacements@adityabirla.com \n \nAnnexure A \n \nSr \nNo \nParticulars Details \n"
    "a) Name of the Target Entity, details in \nbrief such as size, turnover etc \nAmplus TN One Energy Private Limited \n"
    "g) Consideration - whether cash \nconsideration or share sw ap or any \nother form and details of the same \nCash consideration \n"
    "h) Cost of acquisition and / or the price at \nwhich the shares are acquired \n"
    "Equity investment of upto Rs. 14,06,27,240/- \n(Rupees Fourteen Crore Six Lakh Twenty -Seven \nThousand Two Hundred Forty Only)   \n"
    "i) Percentage of shareholding  / control \nacquired and / or no. of shares acquired \n26% \n"
)


# Phase 1C-R2 (2026-09-18): the real, frozen text of GUJENERGY's real
# filing that crashed extract_transaction_facts() with an unhandled
# ValueError during the Assembly V2 fresh-cohort audit (2026-09-18) --
# fetched once from NSE's archive, embedded here verbatim. A generic
# shareholder tax-cost note, not a real transaction table: its "Cost of
# acquisition" phrase has no numbered item after it, so the field's own
# scoped span runs all the way to the end of the page and genuinely
# contains "...their respective shareholders, pursuant to..." -- the
# real prose that produced the incidental "rs," false currency match
# this phase's fix targets.
GUJENERGY_PAGE_1 = (
    " \n GUJARAT ENERGY LIMITED (Erstwhile Gujarat Gas Limited)  Corporate Office: Office No. 4 & 5, Ground Floor, "
    "IT Tower -2, Infocity, Gandhinagar – 382009 Gujarat  Registered Office: Gujarat Energy Bhavan, Behind Udyog "
    "Bhavan, Sector- 11, Gandhinagar, Gujarat – 382010 Tel.: +91-79-66701001 Website: www.gujarat-energy.com, "
    "CIN: L40200GJ2012SGC069118  \nGEL/SEC/2026/1617                                              5th September, "
    "2026  BSE Limited, Phiroze Jeejeebhoy Tower, Dalal Street, Mumbai  Company Code: BSE - 539336 National Stock "
    "Exchange of India Ltd, Exchange Plaza, 5th Floor, Plot No. C/1, G Block, Bandra Kurla Complex, Bandra (East), "
    "Mumbai  Company Code: NSE - GUJENERGY  Sub.: Apportionment of cost of acquisition of Shares of Gujarat Energy "
    "Limited (Erstwhile Gujarat Gas Limited) and GSPL Transmission Limited as per the provisions of Section 73 of "
    "the Income-Tax Act, 2025 (corresponding to Sections 49(2C) and 49(2D) of the Income-Tax Act, 1961)  Ref.: "
    "Composite Scheme of Amalgamation and Arrangement amongst Gujarat State Petroleum Corporation Limited "
    "(“GSPC”/ “Transferor Company 1”), Gujarat State Petronet Limited (“GSPL”/ "
    "“Transferor Company 2”), GSPC Energy Limited (“GSPC Energy”/ “Transferor Company 3”), "
    "Gujarat Gas Limited (now Gujarat Energy Limited) (“GEL”/ “Transferee Company”/ “Demerged "
    "Company”/“The Company”) and GSPL Transmission Limited (“GTL”/ “Resulting "
    "Company”) and their respective shareholders, pursuant to Sections 230-232 and other applicable provisions "
    "of the Companies Act, 2013 (the “Scheme”)  Respected Sir/Madam,  Please find enclosed communication "
    "for the attention of the shareholders of the Company for apportionment of cost of acquisition of Equity Shares "
    "of the Company and Resulting Company.  The above communication is being hosted on the website of the Company "
    "at www.gujarat-energy.com.  You are requested to take the above information on record.  Thanking you,   "
    "For, Gujarat Energy Limited    Sandeep Dave  Company Secretary  Enclosed: As above    "
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


def test_ibullsltd_target_entity_name_a_real_pre_existing_untested_gap_closed_by_targetfact_r1():
    """IBULLSLTD's real answer states the target's name bare, with no
    'Name:' sub-label -- this was silently NOT_FOUND before TargetFact
    R1 (2026-09-18), never asserted by any test until now. A genuine,
    additional real specimen the R1 fix generalizes to beyond the 6 it
    was directly diagnosed from."""
    fields = _by_field(extract_transaction_facts([IBULLSLTD_PAGE_2, IBULLSLTD_PAGE_3]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Fintech Cloud Private Limited"


# ── Phase 1C-R2 regression: GUJENERGY currency-parser crash safety ──────
# (owner design, 2026-09-18) -- a real, previously-undiscovered defect
# found by the Assembly V2 fresh-cohort audit, NOT the original 4/10
# extractor-development specimens: GUJENERGY's real filing crashed
# extract_transaction_facts() with an unhandled ValueError, taking down
# extraction of every field for the whole document, not just
# consideration_amount. Root cause: _CURRENCY_AMOUNT_RE had no lexical
# boundary before "Rs", so it matched the bare tail of an ordinary word
# ("...shareholde|rs, ...") with a capture group containing nothing but
# a comma; _is_safe_currency_match's R1 comma heuristic ("," in
# group(1)) was satisfied by that bare comma; _parse_currency_amount
# then called float("") and raised. Fixed at three independent layers
# (regex lexical boundary + digit-anchored capture group +
# _parse_currency_amount's own never-raise validation) -- this section
# proves all three, plus that R1's own fixes (JUNIPER, MAITHANALL, the
# clean decimal-crore contrast) still hold.

def test_gujenergy_consideration_amount_never_crashes_and_reports_not_found():
    """The permanent regression proof: this real filing must never
    raise, and since it genuinely states no transaction consideration
    anywhere (it's a shareholder tax-cost note, not an acquisition
    table), every field must cleanly resolve to NOT_FOUND -- not a
    fabricated amount, not an exception."""
    fields = _by_field(extract_transaction_facts([GUJENERGY_PAGE_1]))
    assert fields[CONSIDERATION_AMOUNT].extraction_status == NOT_FOUND
    assert fields[CONSIDERATION_AMOUNT].value_numeric is None
    assert fields[TARGET_ENTITY_NAME].extraction_status == NOT_FOUND
    assert fields[STAKE_PERCENTAGE].extraction_status == NOT_FOUND
    assert fields[CONSIDERATION_TYPE].extraction_status == NOT_FOUND


def test_arbitrary_prose_punctuation_is_never_interpretable_as_a_monetary_amount():
    """Generalizes the real GUJENERGY defect beyond that one document:
    ANY 'Cost of acquisition' span whose unbounded remainder (no
    numbered item follows it, so the span runs to the end of the text)
    happens to contain an ordinary word ending in 'rs' immediately
    followed by a comma -- 'shareholders,', 'directors,', 'years,' are
    all real, unremarkable English -- must never be read as a currency
    figure, regardless of which specific word produces it."""
    fields = _by_field(extract_transaction_facts([
        "Cost of acquisition of shares, pursuant to a scheme approved by the Board of Directors, "
        "will be communicated to shareholders in due course."
    ]))
    f = fields[CONSIDERATION_AMOUNT]
    assert f.extraction_status == NOT_FOUND
    assert f.value_numeric is None


def test_parse_currency_amount_never_raises_on_a_malformed_match_defense_in_depth():
    """Owner's explicit defense-in-depth requirement: even if a future
    change to _CURRENCY_AMOUNT_RE ever again allowed a punctuation-only
    capture, _parse_currency_amount itself must decline (None), never
    raise. Constructed with a deliberately permissive throwaway regex --
    never the module's own (now-hardened) _CURRENCY_AMOUNT_RE, which can
    no longer produce this shape at all -- to test this layer in true
    isolation from the upstream fix."""
    import re as _re
    from app.services.warehouse.transaction_fact_extractor import _parse_currency_amount
    fake_match = _re.compile(r"(,)()").search(",")
    assert _parse_currency_amount(fake_match) is None


# The permanent JUNIPER, MAITHANALL, and clean-decimal-crore R1
# fixtures already in this file (test_juniper_consideration_amount_is_
# the_real_crore_value_never_the_unrelated_248,
# test_bare_number_with_no_comma_and_no_clean_magnitude_word_is_not_
# found_never_a_naked_number, and
# test_clean_decimal_crore_amount_is_still_extractable_the_same_figure_
# corruption_free below) are untouched and run alongside these R2 tests
# in the same suite -- their continued passing IS the proof R2 cannot
# reopen what R1 fixed; no need to duplicate them under new names.


# ── TargetFact R1: bare/short-sub-label target names ────────────────────
# (owner design, 2026-09-18) -- a read-only classification of the 6 real
# target_entity_name NOT_FOUND misses from the Assembly V2 fresh cohort
# found ONE recurring root cause, not six unrelated shapes: the answer
# is stated either bare (4/6) or after a short sub-label with no colon
# (1/6, HMVL) -- never the "Name:" convention _TABLE_NAME_RE alone
# covers. All 6 real specimens below, plus the pre-existing IBULLSLTD
# fixture (an untested gap this same fix closes), are the permanent
# regression proof.

def test_dalbharat_target_entity_name_bare_no_sublabel():
    fields = _by_field(extract_transaction_facts([DALBHARAT_PAGE_2]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "AMPL Green City Solutions Private Limited"


def test_hmvl_target_entity_name_strips_the_target_entity_sublabel():
    """The one demonstrated case where a naive corporate-suffix search
    would sweep a short sub-label ('Target Entity', no colon) into the
    captured name -- must resolve to the real name alone."""
    fields = _by_field(extract_transaction_facts([HMVL_PAGE_2, HMVL_PAGE_3]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Assetgro Fintech Private Limited"
    assert "target entity" not in f.value_text.lower()


def test_hmvl_stake_and_consideration_amount_still_correct():
    """Confirms TargetFact R1's target-only change didn't disturb the
    other fields already correctly extracted from this same real
    specimen (stake_percentage/consideration_amount were part of the
    fresh-cohort audit's real, already-verified output)."""
    fields = _by_field(extract_transaction_facts([HMVL_PAGE_2, HMVL_PAGE_3]))
    assert fields[STAKE_PERCENTAGE].value_numeric == 2.48
    assert fields[CONSIDERATION_AMOUNT].value_numeric == 850000000.0


def test_greenlam_target_entity_name_bare_no_sublabel():
    fields = _by_field(extract_transaction_facts([GREENLAM_PAGE_2, GREENLAM_PAGE_3]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Bhadla Minigrid Solar 4 Private Limited"


def test_utlsolar_target_entity_name_bare_no_sublabel():
    fields = _by_field(extract_transaction_facts([UTLSOLAR_PAGE_2]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Zayo Energy Private Limited"


def test_heranba_target_entity_name_name_of_entity_sublabel_already_self_resolves():
    """A different real sub-label ('Name of Entity :') that already
    resolves correctly WITHOUT needing the sub-label-stripping fix --
    the colon falls outside the corporate-name character class, so the
    match naturally restarts right after it, the same way ZODIAC's own
    'Name:' already does via _TABLE_NAME_RE."""
    fields = _by_field(extract_transaction_facts([HERANBA_PAGE_2, HERANBA_PAGE_3]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Mikusu India Private Limited"


def test_nephroplus_target_entity_name_bare_no_sublabel_genuinely_unseen_validation():
    """TargetFact R1's own fresh-validation proof (owner instruction):
    fetched from a cohort assembled AFTER the fix was written, never
    used to diagnose or tune it. A real bare-answer target name ending
    in LLP (not Private Limited/Limited, the two suffixes every other
    fixture in this file happens to use) -- also confirms the fallback
    doesn't stop at the trailing parenthetical '(\"Target Entity\")'
    short-form definition that immediately follows the real name here."""
    fields = _by_field(extract_transaction_facts([NEPHROPLUS_PAGE_2]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Dialysis Center Almaty LLP"


def test_indiacem_target_entity_name_bare_no_sublabel():
    fields = _by_field(extract_transaction_facts([INDIACEM_PAGE_2]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == POPULATED
    assert f.value_text == "Amplus TN One Energy Private Limited"


def test_targetfact_r1_fallback_never_fires_when_no_real_answer_exists():
    """Negative control: a table whose target-entity label exists but
    whose answer genuinely has no corporate-suffix name at all must
    stay NOT_FOUND -- the fallback requires a real corporate suffix, it
    does not lower the bar to 'any capitalized phrase'."""
    fields = _by_field(extract_transaction_facts([
        "a) Name of the target entity, details in brief such as size, turnover etc.; "
        "Not applicable as no acquisition of control/ shares/ voting rights is being contemplated. "
        "b) Whether the acquisition would fall within related party transaction(s); No."
    ]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == NOT_FOUND
    assert f.value_text is None


def test_targetfact_r1_does_not_reopen_juniper_no_target_stated():
    """JUNIPER's real filing states no target at all ('Not Applicable as
    no acquisition of control/ shares/ voting rights is being
    contemplated') on a page this fixture set doesn't even include the
    target-entity label for -- must remain NOT_FOUND, never a false
    match against 'Juniper Hotels Limited' (the FILER's own name,
    appearing in the page header, not the answer)."""
    fields = _by_field(extract_transaction_facts([JUNIPER_PAGE_4, JUNIPER_PAGE_7_PRESS_RELEASE]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == NOT_FOUND
    assert f.value_text is None


def test_gujenergy_target_entity_name_still_not_found_after_targetfact_r1():
    """GUJENERGY genuinely never states a target entity at all (it's a
    shareholder tax-cost note, not an acquisition table) -- must stay
    NOT_FOUND after TargetFact R1 exactly as it did after R2, never a
    false match against one of the many real company names mentioned in
    its own recital clause (GSPC, GSPL, GSPC Energy, GTL, etc.)."""
    fields = _by_field(extract_transaction_facts([GUJENERGY_PAGE_1]))
    f = fields[TARGET_ENTITY_NAME]
    assert f.extraction_status == NOT_FOUND
    assert f.value_text is None


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

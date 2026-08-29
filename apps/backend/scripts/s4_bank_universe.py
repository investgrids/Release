"""
S4 — real 27-bank universe, classified by real, publicly-known bank type.
Source: app.api.companies._NSE_UNIVERSE, sector == "Banking" (27 real
matches, used in full — already spans large private/PSU/mid-small
private/small finance without needing to trim down).
"""
from __future__ import annotations

LARGE_PRIVATE = ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK"]
PSU = [
    "SBIN", "PNB", "BANKBARODA", "UNIONBANK", "CANBK", "BANKINDIA", "CENTRALBK",
    "IDBI", "INDIANB", "IOB", "MAHABANK", "UCOBANK", "PSB",
]
MID_SMALL_PRIVATE = ["FEDERALBNK", "IDFCFIRSTB", "BANDHANBNK", "RBLBANK", "CUB", "J&KBANK", "KARURVYSYA", "YESBANK"]
SMALL_FINANCE = ["AUBANK"]

ALL_BANKS = LARGE_PRIVATE + PSU + MID_SMALL_PRIVATE + SMALL_FINANCE  # 27 real symbols

BANK_TYPE = {}
for sym in LARGE_PRIVATE:
    BANK_TYPE[sym] = "Large Private"
for sym in PSU:
    BANK_TYPE[sym] = "PSU"
for sym in MID_SMALL_PRIVATE:
    BANK_TYPE[sym] = "Mid/Small Private"
for sym in SMALL_FINANCE:
    BANK_TYPE[sym] = "Small Finance"

ORIGINAL_FIVE = ["ICICIBANK", "HDFCBANK", "AXISBANK", "KOTAKBANK", "SBIN"]

assert len(ALL_BANKS) == 27, f"expected 27, got {len(ALL_BANKS)}"
assert len(BANK_TYPE) == 27

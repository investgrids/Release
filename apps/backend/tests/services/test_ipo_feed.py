from datetime import date

import pytest

import app.services.ipo_feed as f

TODAY = date(2026, 10, 11)


def test_status_comes_from_dates():
    d = lambda y, m, dd: date(y, m, dd)
    assert f._status(d(2026, 10, 13), d(2026, 10, 15), None, TODAY) == "Upcoming"
    assert f._status(d(2026, 10, 9), d(2026, 10, 13), None, TODAY) == "Ongoing"
    assert f._status(d(2026, 10, 5), d(2026, 10, 7), None, TODAY) == "Closed"
    assert f._status(d(2026, 9, 28), d(2026, 9, 30), d(2026, 10, 8), TODAY) == "Listed"
    assert f._status(d(2026, 10, 5), d(2026, 10, 7), d(2026, 10, 14), TODAY) == "Closed"   # listing date still ahead


def test_withdrawn_and_postponed_issues_are_not_awaiting_listing():
    row = {"company": "Sri Priyanka Geo Commex Limited-Issue Withdrawn", "ipoEndDate": "29-JUN-2026", "ipoStartDate": "24-JUN-2026", "issuePrice": "-", "listingDate": "-", "priceRange": "Rs.207 to Rs.212", "securityType": "SME", "symbol": "SPGCL"}
    assert f.build([], [], [row], TODAY)[0]["status"] == "Withdrawn"


def test_build_normalises_real_nse_shapes_and_drops_non_ipo_series():
    up = [{"companyName": "HD Fire Protect Limited", "issueEndDate": "15-Oct-2026", "issuePrice": "Rs.258 to Rs.271", "issueSize": "26284500", "issueStartDate": "13-Oct-2026", "series": "EQ", "status": "Forthcoming", "symbol": "HDFIRE"},
          {"companyName": "Vaibhav Vyapaar Limited", "issueEndDate": "15-Oct-2026", "issuePrice": "Rs.51 to Rs.54", "issueSize": "7796000", "issueStartDate": "13-Oct-2026", "lotSize": "2000", "priceBand": "Rs.51 to Rs.54", "series": "SME", "symbol": "LOANFRONT"}]
    past = [{"company": "Nityas Gems and Jewellery Limited", "ipoEndDate": "05-OCT-2026", "ipoStartDate": "30-SEP-2026", "issuePrice": "    75", "listingDate": "08-OCT-2026", "priceRange": "Rs.70 to Rs.75", "securityType": "BE", "symbol": "NITYAS"},
            {"company": "Some Bond", "ipoEndDate": "05-OCT-2026", "ipoStartDate": "30-SEP-2026", "issuePrice": "1000", "listingDate": "08-OCT-2026", "priceRange": "Rs.1000", "securityType": "DEBT", "symbol": "BOND"},
            {"company": "Old Co", "ipoEndDate": "05-JAN-2025", "ipoStartDate": "01-JAN-2025", "issuePrice": "10", "listingDate": "09-JAN-2025", "priceRange": "Rs.10", "securityType": "SME", "symbol": "OLD"}]
    out = f.build(up, [], past, TODAY)
    by = {i["symbol"]: i for i in out}
    assert set(by) == {"HDFIRE", "LOANFRONT", "NITYAS"}                      # bond and >120-day-old issue dropped
    assert by["HDFIRE"]["status"] == "Upcoming" and by["HDFIRE"]["type"] == "Mainboard" and (by["HDFIRE"]["priceMin"], by["HDFIRE"]["priceMax"]) == (258, 271)
    assert by["LOANFRONT"]["type"] == "SME" and by["LOANFRONT"]["lotSize"] == 2000 and by["LOANFRONT"]["sharesOffered"] == 7796000
    assert by["NITYAS"]["type"] is None and by["NITYAS"]["status"] == "Listed" and by["NITYAS"]["issuePrice"] == 75 and by["NITYAS"]["listingDate"] == "2026-10-08"
    assert all("gmp" not in i and "aiRating" not in i for i in out)           # nothing NSE does not provide


def test_no_duplicates_and_missing_fields_do_not_crash():
    row = {"companyName": "X Ltd", "symbol": "X", "issueStartDate": "13-Oct-2026", "issueEndDate": "15-Oct-2026", "series": "EQ"}
    out = f.build([row, row], [], [{"company": "-", "symbol": ""}], TODAY)
    assert len(out) == 1 and out[0]["priceMin"] is None and out[0]["issueValue"] is None


@pytest.mark.asyncio
async def test_unavailable_when_upstream_fails_and_nothing_cached(monkeypatch):
    async def boom():
        raise RuntimeError("blocked")
    monkeypatch.setattr(f, "_fetch", boom)
    monkeypatch.setitem(f._cache, "data", None)
    r = await f.get_ipos()
    assert r["ipos"] == [] and r["data_source"] == "unavailable" and r["is_mock"] is False


@pytest.mark.asyncio
async def test_serves_stale_copy_when_upstream_fails(monkeypatch):
    async def boom():
        raise RuntimeError("blocked")
    monkeypatch.setattr(f, "_fetch", boom)
    monkeypatch.setitem(f._cache, "data", {"ipos": [{"id": "a"}], "stats": {}, "as_of": "x", "data_source": "nse", "is_mock": False, "stale": False})
    monkeypatch.setitem(f._cache, "at", 1.0)   # long expired, but inside the 6h stale window only if recent: force recent
    import time
    monkeypatch.setitem(f._cache, "at", time.time() - f._TTL_S - 5)
    r = await f.get_ipos()
    assert r["stale"] is True and r["ipos"][0]["id"] == "a"

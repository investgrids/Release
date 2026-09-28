from app.services.market_data import _pct_str


def test_missing_value_is_dash_not_zero():
    assert _pct_str(None) == "—"
    assert _pct_str("") == "—"


def test_real_values_including_real_zero():
    assert _pct_str(0.477) == "47.7%"
    assert _pct_str(0) == "0.0%"
    assert _pct_str(-0.052) == "-5.2%"


def test_garbage_is_dash():
    assert _pct_str("n/a") == "—"

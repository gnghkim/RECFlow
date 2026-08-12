from datetime import date
from decimal import Decimal

from rec.models import MarketArea, RecMarketRow
from rec.validation import validate_rows


def row(**overrides) -> RecMarketRow:
    base = dict(
        trade_date=date(2026, 8, 6),
        market_area=MarketArea.TOTAL,
        trade_count=450,
        volume=Decimal("194500"),
        avg_price=Decimal("71450"),
        high_price=Decimal("72300"),
        low_price=Decimal("70200"),
        close_price=Decimal("71600"),
        trade_amount=Decimal("13897550000"),
    )
    base.update(overrides)
    return RecMarketRow(**base)


def test_valid_row_has_no_issues():
    assert validate_rows([row()]) == []


def test_avg_price_above_high_price_is_reported():
    issues = validate_rows([row(avg_price=Decimal("99999"))])
    assert len(issues) == 1
    assert "평균가" in issues[0]


def test_close_price_below_low_price_is_reported():
    issues = validate_rows([row(close_price=Decimal("100"))])
    assert len(issues) == 1
    assert "종가" in issues[0]


def test_negative_volume_is_reported():
    issues = validate_rows([row(volume=Decimal("-1"))])
    assert len(issues) == 1
    assert "거래량" in issues[0]


def test_zero_price_is_reported():
    issues = validate_rows([row(avg_price=Decimal("0"))])
    assert any("0 이하" in issue for issue in issues)


def test_none_values_are_not_violations():
    """육지 행의 종가 None은 정상이다. 값 없음과 잘못된 값을 구분한다."""
    assert validate_rows([row(market_area=MarketArea.LAND, close_price=None, trade_amount=None)]) == []


def test_high_below_low_is_reported():
    issues = validate_rows([row(high_price=Decimal("60000"), low_price=Decimal("70000"))])
    assert any("최고가" in issue for issue in issues)


def test_reports_every_violating_row():
    """총 개수가 아니라 두 행이 모두 보고되는지가 요점이다."""
    issues = validate_rows([row(volume=Decimal("-1")), row(market_area=MarketArea.LAND, avg_price=Decimal("-5"))])
    assert len(issues) == 2
    assert any("거래량" in issue for issue in issues)
    assert any("평균가" in issue for issue in issues)

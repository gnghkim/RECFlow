from datetime import date

import pytest

from rec.budget import BudgetExhausted, DailyBudget


def test_consumes_until_limit():
    budget = DailyBudget(limit=3, today=date(2026, 8, 6))
    for _ in range(3):
        budget.consume()
    assert budget.remaining == 0


def test_raises_when_exhausted():
    budget = DailyBudget(limit=1, today=date(2026, 8, 6))
    budget.consume()
    with pytest.raises(BudgetExhausted):
        budget.consume()


def test_resets_on_new_day():
    budget = DailyBudget(limit=1, today=date(2026, 8, 6))
    budget.consume()
    budget.advance_to(date(2026, 8, 7))
    assert budget.remaining == 1
    budget.consume()

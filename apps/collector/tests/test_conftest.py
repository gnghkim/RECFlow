import pytest

from tests.conftest import require_test_database


def test_require_test_database_rejects_development_database():
    dsn = "postgresql://recflow:secret@db:5432/recflow"

    with pytest.raises(
        pytest.fail.Exception,
        match=r"recflow.*전용 테스트 DB.*_test",
    ):
        require_test_database(dsn)


def test_require_test_database_accepts_test_database():
    assert require_test_database(
        "postgresql://recflow:secret@db:5432/recflow_test"
    ) == "recflow_test"

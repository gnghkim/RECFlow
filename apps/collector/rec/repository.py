"""DB 접근.

SQL만 안다. HTTP와 응답 필드명을 알지 못한다.

이 파일은 어떤 DDL도 실행하지 않는다. 테이블 생성과 변경은 Prisma
마이그레이션이 단독으로 담당한다. 스키마 정의가 두 곳에 있으면 반드시 어긋난다.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rec.models import ApiResponse, MarketArea, RecMarketRow

UPSERT_SQL = """
INSERT INTO rec_market (
    trade_date, market_area, trade_count, volume,
    avg_price, high_price, low_price, close_price, trade_amount,
    source, created_at, updated_at
) VALUES (
    %(trade_date)s, %(market_area)s, %(trade_count)s, %(volume)s,
    %(avg_price)s, %(high_price)s, %(low_price)s, %(close_price)s, %(trade_amount)s,
    %(source)s, NOW(), NOW()
)
ON CONFLICT (trade_date, market_area) DO UPDATE SET
    trade_count  = EXCLUDED.trade_count,
    volume       = EXCLUDED.volume,
    avg_price    = EXCLUDED.avg_price,
    high_price   = EXCLUDED.high_price,
    low_price    = EXCLUDED.low_price,
    close_price  = EXCLUDED.close_price,
    trade_amount = EXCLUDED.trade_amount,
    source       = EXCLUDED.source,
    updated_at   = NOW()
"""


class RecRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    # --- 실행 이력 --------------------------------------------------------

    def start_run(self, job_type: str, target_date: date | None) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collection_runs (job_type, target_date, status, attempts, rows_upserted, started_at)
                VALUES (%s::"CollectionJobType", %s, 'FAILED'::"CollectionStatus", 0, 0, NOW())
                RETURNING id
                """,
                (job_type, target_date),
            )
            return cur.fetchone()["id"]

    def finish_run(
        self,
        run_id: int,
        status: str,
        attempts: int,
        rows_upserted: int,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE collection_runs
                   SET status = %s::"CollectionStatus",
                       attempts = %s,
                       rows_upserted = %s,
                       error_message = %s,
                       finished_at = NOW()
                 WHERE id = %s
                """,
                (status, attempts, rows_upserted, error_message, run_id),
            )

    def last_successful_run(self) -> dict | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, job_type, target_date, rows_upserted, started_at, finished_at
                  FROM collection_runs
                 WHERE status = 'SUCCESS'
                 ORDER BY finished_at DESC NULLS LAST
                 LIMIT 1
                """
            )
            return cur.fetchone()

    # --- 원본 보존 --------------------------------------------------------

    def save_raw(self, run_id: int, response: ApiResponse) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rec_market_raw (trade_date, endpoint, http_status, payload, fetched_at, collection_run_id)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                RETURNING id
                """,
                (
                    response.trade_date,
                    response.endpoint,
                    response.http_status,
                    Jsonb(response.payload),
                    run_id,
                ),
            )
            return cur.fetchone()["id"]

    # --- 시세 적재 --------------------------------------------------------

    def upsert_rows(self, rows: list[RecMarketRow], source: str) -> int:
        if not rows:
            return 0
        params = [
            {
                "trade_date": row.trade_date,
                "market_area": row.market_area.value,
                "trade_count": row.trade_count,
                "volume": row.volume,
                "avg_price": row.avg_price,
                "high_price": row.high_price,
                "low_price": row.low_price,
                "close_price": row.close_price,
                "trade_amount": row.trade_amount,
                "source": source,
            }
            for row in rows
        ]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, params)
        return len(params)

    # --- 조회 -------------------------------------------------------------

    def existing_trade_dates(self, start: date, end: date) -> set[date]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT trade_date FROM rec_market WHERE trade_date BETWEEN %s AND %s",
                (start, end),
            )
            return {row["trade_date"] for row in cur.fetchall()}

    def settled_trade_dates(self, start: date, end: date) -> set[date]:
        """데이터가 있거나 휴장일로 확정된 날. 누락일 재시도 대상에서 제외한다."""
        no_data: set[date]
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT target_date
                  FROM collection_runs
                 WHERE status = 'NO_DATA' AND target_date BETWEEN %s AND %s
                """,
                (start, end),
            )
            no_data = {row["target_date"] for row in cur.fetchall() if row["target_date"]}
        return self.existing_trade_dates(start, end) | no_data

    # --- 테스트 지원 ------------------------------------------------------

    def count_market_rows(self) -> int:
        return self._scalar("SELECT COUNT(*) AS n FROM rec_market")

    def count_raw_rows(self) -> int:
        return self._scalar("SELECT COUNT(*) AS n FROM rec_market_raw")

    def fetch_avg_price(self, trade_date: date, area: MarketArea) -> Decimal | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT avg_price FROM rec_market WHERE trade_date = %s AND market_area = %s::\"MarketArea\"",
                (trade_date, area.value),
            )
            found = cur.fetchone()
            return found["avg_price"] if found else None

    def fetch_updated_at(self, trade_date: date, area: MarketArea) -> datetime | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM rec_market WHERE trade_date = %s AND market_area = %s::\"MarketArea\"",
                (trade_date, area.value),
            )
            found = cur.fetchone()
            return found["updated_at"] if found else None

    def truncate_market_tables(self) -> None:
        """테스트 격리용. 시장 데이터만 비우고 회사 데이터는 건드리지 않는다."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE rec_market_raw, rec_market, collection_runs RESTART IDENTITY CASCADE")

    def _scalar(self, sql: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            return int(cur.fetchone()["n"])

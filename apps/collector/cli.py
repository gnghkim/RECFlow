"""수집기 명령줄 인터페이스.

    python -m cli gen-fixture --years 3
    python -m cli collect --date 20260806 --source fixture
    python -m cli backfill --from 20230812 --to 20260812 --source fixture
    python -m cli probe --date 20260806
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from config import load_config
from rec.budget import DailyBudget
from rec.client import RecApiClient
from rec.fixture_client import FixtureClient, generate_fixtures
from rec.repository import RecRepository
from rec.service import CollectorService

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "api-samples"


def parse_day(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def build_source(config, source_name: str):
    if source_name == "fixture":
        return FixtureClient(config.fixture_dir)
    if not config.kpx_api_key:
        raise SystemExit("KPX_API_KEY가 비어 있다. .env에 인증키를 넣거나 --source fixture를 쓰라.")
    return RecApiClient(
        base_url=config.kpx_base_url,
        service_key=config.kpx_api_key,
        budget=DailyBudget(limit=config.kpx_daily_budget),
    )


def cmd_gen_fixture(args, config) -> int:
    end = date.today()
    # 백필 시작일이 경계에 걸려 빈 날이 생기지 않도록 2주 여유를 둔다.
    start = end - timedelta(days=365 * args.years + 14)
    written = generate_fixtures(config.fixture_dir, start, end)
    print(f"fixture {written}개를 {config.fixture_dir}에 생성했다 ({start} ~ {end})")
    return 0


def cmd_collect(args, config) -> int:
    service = CollectorService(RecRepository(config.database_url), build_source(config, args.source))
    outcome = service.collect_day(parse_day(args.date), job_type="MANUAL")
    print(f"{outcome.trade_date} {outcome.status} rows={outcome.rows_upserted}")
    for issue in outcome.issues:
        print(f"  경고: {issue}")
    return 0 if outcome.status in {"SUCCESS", "PARTIAL", "NO_DATA"} else 1


def cmd_backfill(args, config) -> int:
    service = CollectorService(RecRepository(config.database_url), build_source(config, args.source))
    outcomes = service.backfill(parse_day(args.start), parse_day(args.end))
    summary: dict[str, int] = {}
    for outcome in outcomes:
        summary[outcome.status] = summary.get(outcome.status, 0) + 1
    print(f"{len(outcomes)}개 거래일 처리: {summary}")
    return 0


def cmd_probe(args, config) -> int:
    """실 API를 1회 호출해 원본 응답을 저장한다. 키 발급 직후 가장 먼저 실행한다."""
    client = build_source(config, "api")
    response = client.fetch(parse_day(args.date))

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    target = SAMPLE_DIR / f"rec-{args.date}.json"
    target.write_text(json.dumps(response.payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"원본 응답을 {target}에 저장했다.")
    body = response.payload.get("response", {}).get("body", {})
    items = body.get("items")
    first = None
    if isinstance(items, dict):
        inner = items.get("item")
        first = inner[0] if isinstance(inner, list) and inner else inner
    if isinstance(first, dict):
        print("실제 item 필드명:")
        for key in sorted(first.keys()):
            print(f"  {key} = {first[key]!r}")
        print("\n이 목록에 맞게 rec/mapping.py의 FIELD_MAP과 AREA_MAP을 수정하라.")
    else:
        print("item이 비어 있다. 거래일이 아닌 날일 수 있으니 다른 날짜로 다시 시도하라.")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(prog="collector")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-fixture", help="화·목 시계열 fixture 생성")
    gen.add_argument("--years", type=int, default=3)
    gen.set_defaults(func=cmd_gen_fixture)

    collect = sub.add_parser("collect", help="거래일 하나 수집")
    collect.add_argument("--date", required=True, help="YYYYMMDD")
    collect.add_argument("--source", choices=["api", "fixture"], default="fixture")
    collect.set_defaults(func=cmd_collect)

    backfill = sub.add_parser("backfill", help="구간 백필")
    backfill.add_argument("--from", dest="start", required=True, help="YYYYMMDD")
    backfill.add_argument("--to", dest="end", required=True, help="YYYYMMDD")
    backfill.add_argument("--source", choices=["api", "fixture"], default="fixture")
    backfill.set_defaults(func=cmd_backfill)

    probe = sub.add_parser("probe", help="실 API 원본 응답 덤프")
    probe.add_argument("--date", required=True, help="YYYYMMDD")
    probe.set_defaults(func=cmd_probe)

    args = parser.parse_args(argv)
    return args.func(args, load_config())


if __name__ == "__main__":
    sys.exit(main())

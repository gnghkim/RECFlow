"""수집기 명령줄 인터페이스.

    python -m cli probe                     실 API 원본 응답 덤프와 필드명 출력
    python -m cli collect                   전체 수집 후 적재 (기본 --source api)
    python -m cli gen-fixture --years 3      오프라인 확인용 fixture 생성

이 API는 날짜 필터를 지원하지 않아 수집 단위가 전체다. 그래서 날짜 인자와
백필 명령이 따로 없다. collect 한 번이 곧 백필이다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta

from config import load_config
from rec.budget import DailyBudget
from rec.client import RecApiClient
from rec.fixture_client import FixtureClient, generate_fixtures
from rec.mapping import map_response
from rec.repository import RecRepository
from rec.service import CollectorService


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
    start = end - timedelta(days=365 * args.years + 14)
    written = generate_fixtures(config.fixture_dir, start, end)
    print(f"fixture 거래일 {written}일을 {config.fixture_dir}에 생성했다 ({start} ~ {end})")
    return 0


def cmd_collect(args, config) -> int:
    service = CollectorService(RecRepository(config.database_url), build_source(config, args.source))
    outcome = service.collect(job_type="MANUAL")

    print(f"상태 {outcome.status} / 거래일 {outcome.trade_dates}일 / {outcome.rows_upserted}행 적재")
    if outcome.latest_trade_date:
        print(f"최신 거래일 {outcome.latest_trade_date}")
    for issue in outcome.issues[:10]:
        print(f"  경고: {issue}")
    if len(outcome.issues) > 10:
        print(f"  … 경고 {len(outcome.issues) - 10}건 더")

    return 0 if outcome.status in {"SUCCESS", "PARTIAL", "NO_DATA"} else 1


def cmd_probe(args, config) -> int:
    """실 API를 1회 호출해 원본 응답을 저장한다. 필드가 바뀌었는지 확인하는 용도다."""
    client = build_source(config, "api")
    response = client.fetch(page=1)

    config.sample_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    target = config.sample_dir / f"rec-{stamp}.json"
    target.write_text(json.dumps(response.payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"원본 응답을 {target}에 저장했다.")

    body = response.payload.get("response", {}).get("body", {})
    print(f"totalCount = {body.get('totalCount')}")

    items = body.get("items")
    first = None
    if isinstance(items, dict):
        inner = items.get("item")
        first = inner[0] if isinstance(inner, list) and inner else inner
    if not isinstance(first, dict):
        print("item이 비어 있다. 응답을 직접 확인하라.")
        return 1

    print("\n실제 item 필드:")
    for key in sorted(first.keys()):
        print(f"  {key} = {first[key]!r}")

    rows = map_response(response)
    dates = sorted({row.trade_date for row in rows})
    print(f"\n매핑 결과: 거래일 {len(dates)}일 → {len(rows)}행")
    if dates:
        print(f"기간 {dates[0]} ~ {dates[-1]}")
    print("\n매핑이 실패하면 rec/mapping.py의 필드명 상수를 실제 응답에 맞게 수정하라.")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(prog="collector")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-fixture", help="오프라인 확인용 fixture 생성")
    gen.add_argument("--years", type=int, default=3)
    gen.set_defaults(func=cmd_gen_fixture)

    collect = sub.add_parser("collect", help="전체 수집 후 적재")
    collect.add_argument("--source", choices=["api", "fixture"], default="api")
    collect.set_defaults(func=cmd_collect)

    probe = sub.add_parser("probe", help="실 API 원본 응답 덤프")
    probe.set_defaults(func=cmd_probe)

    args = parser.parse_args(argv)
    return args.func(args, load_config())


if __name__ == "__main__":
    sys.exit(main())

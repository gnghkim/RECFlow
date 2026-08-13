"""환경변수 로딩. 기본값은 로컬 개발 기준이다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEFAULT_SAMPLE_DIR = Path(__file__).parent / "api-samples"


@dataclass(frozen=True, slots=True)
class Config:
    database_url: str
    kpx_api_key: str
    kpx_base_url: str
    kpx_daily_budget: int
    fixture_dir: Path
    sample_dir: Path
    collector_port: int


def load_config() -> Config:
    # 컨테이너에서는 compose가 환경변수를 직접 주입하므로 .env가 없다.
    # 호스트에서 직접 실행하는 경우에만 상위 디렉토리의 .env를 찾아 읽는다.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(candidate)
            break

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았다. .env를 확인하라.")

    return Config(
        database_url=database_url,
        kpx_api_key=os.environ.get("KPX_API_KEY", ""),
        kpx_base_url=os.environ.get("KPX_BASE_URL", "https://apis.data.go.kr/B552115/RecMarketInfo2"),
        kpx_daily_budget=int(os.environ.get("KPX_DAILY_BUDGET", "80")),
        fixture_dir=Path(os.environ.get("FIXTURE_DIR", DEFAULT_FIXTURE_DIR)),
        sample_dir=Path(os.environ.get("SAMPLE_DIR", DEFAULT_SAMPLE_DIR)),
        collector_port=int(os.environ.get("COLLECTOR_PORT", "8000")),
    )

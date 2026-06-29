# 카드 회귀 스냅샷 테스트 공통 설정.
import sys
from pathlib import Path

import pytest

# builder/ 를 import 경로에 추가 → `import extract_zoning` 등 추출기 모듈 직접 사용.
BUILDER = Path(__file__).resolve().parent.parent
if str(BUILDER) not in sys.path:
    sys.path.insert(0, str(BUILDER))

# Windows cp949 콘솔에서 한글 assert 메시지가 UnicodeEncodeError 로 죽지 않게 utf-8 강제.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", action="store_true", default=False,
        help="현재 카드 값으로 골든 스냅샷을 재생성한다(데이터 변경을 사람이 승인하는 절차).",
    )


@pytest.fixture(scope="session")
def update_golden(request) -> bool:
    return bool(request.config.getoption("--update-golden"))

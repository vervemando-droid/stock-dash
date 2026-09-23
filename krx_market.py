"""KRX Open API daily index adapter. No real-time quotes are implied."""
import os
from datetime import date, timedelta

import requests

BASE = "https://data-dbg.krx.co.kr/svc/apis/idx"
SERIES = {"KOSPI": "kospi_dd_trd", "KOSDAQ": "kosdaq_dd_trd"}
INDEX_LABELS = {"KOSPI": {"KOSPI", "코스피"}, "KOSDAQ": {"KOSDAQ", "코스닥"}}


class KRXError(Exception):
    pass


def _number(value):
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def parse_index(payload, name):
    if not isinstance(payload, dict) or not isinstance(payload.get("OutBlock_1"), list):
        raise KRXError("KRX 응답 형식 또는 서비스 이용 권한을 확인하세요.")
    for row in payload["OutBlock_1"]:
        if not isinstance(row, dict) or str(row.get("IDX_NM", "")).strip().upper() not in INDEX_LABELS[name]:
            continue
        close = _number(row.get("CLSPRC_IDX"))
        if close is None:
            raise KRXError("KRX 지수 종가 형식을 확인하세요.")
        return {
            "name": name,
            "date": str(row.get("BAS_DD", "")),
            "close": close,
            "change": _number(row.get("CMPPREVDD_IDX")),
            "rate": _number(row.get("FLUC_RT")),
            "source": "KRX Open API",
        }
    return None


def fetch_index(name, today=None, session=None):
    """Find the latest published daily close within seven calendar days."""
    if name not in SERIES:
        raise ValueError("지원하지 않는 지수")
    key = os.getenv("KRX_CRTFC_KEY", "").strip()
    if not key:
        raise KRXError("KRX_CRTFC_KEY 미설정")
    today = today or date.today()
    client = session or requests
    url = f"{BASE}/{SERIES[name]}"
    for offset in range(7):
        day = today - timedelta(days=offset)
        try:
            response = client.get(
                url,
                params={"basDd": day.strftime("%Y%m%d")},
                headers={"AUTH_KEY": key},
                timeout=(5, 12),
            )
            if response.status_code in (401, 403):
                raise KRXError("KRX 인증키 또는 해당 지수 API 이용 승인을 확인하세요.")
            response.raise_for_status()
            record = parse_index(response.json(), name)
        except KRXError:
            raise
        except (requests.RequestException, ValueError):
            raise KRXError("KRX 연결 또는 응답 확인에 실패했습니다.") from None
        if record:
            return record
    raise KRXError("최근 7일 안에 조회 가능한 KRX 일별 지수가 없습니다.")

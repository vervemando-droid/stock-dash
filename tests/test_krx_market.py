import os
import unittest
import sys
import types

try:
    import requests
except ModuleNotFoundError:
    requests = types.ModuleType("requests")
    requests.RequestException = type("RequestException", (Exception,), {})
    requests.Timeout = type("Timeout", (requests.RequestException,), {})
    requests.ConnectionError = type("ConnectionError", (requests.RequestException,), {})
    requests.exceptions = types.SimpleNamespace(SSLError=type("SSLError", (requests.RequestException,), {}))
    sys.modules["requests"] = requests
from datetime import date
from unittest.mock import patch

from krx_market import KRXError, fetch_index, parse_index


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class KRXTests(unittest.TestCase):
    def test_exact_index_and_numeric_fields(self):
        payload = {"OutBlock_1": [
            {"IDX_NM": "코스피 200", "CLSPRC_IDX": "333.33"},
            {"IDX_NM": "코스피", "BAS_DD": "20260922", "CLSPRC_IDX": "2,700.51",
             "CMPPREVDD_IDX": "-12.01", "FLUC_RT": "-0.44"},
        ]}
        row = parse_index(payload, "KOSPI")
        self.assertEqual(row["close"], 2700.51)
        self.assertEqual(row["name"], "KOSPI")

    def test_reject_bad_response(self):
        with self.assertRaises(KRXError):
            parse_index({"message": "not approved"}, "KOSPI")

    def test_previous_business_day_and_secret_header(self):
        session = Session([
            Response({"OutBlock_1": []}),
            Response({"OutBlock_1": [
                {"IDX_NM": "KOSPI", "BAS_DD": "20260921", "CLSPRC_IDX": "2,700.51"}
            ]}),
        ])
        with patch.dict(os.environ, {"KRX_CRTFC_KEY": "test-placeholder"}):
            result = fetch_index("KOSPI", date(2026, 9, 22), session)
        self.assertEqual(result["date"], "20260921")
        self.assertEqual(session.calls[0][1]["headers"], {"AUTH_KEY": "test-placeholder"})
        self.assertEqual(session.calls[1][1]["params"], {"basDd": "20260921"})


if __name__ == "__main__":
    unittest.main()

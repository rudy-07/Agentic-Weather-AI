import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from tools import (
    MAUSAMGRAM_ENDPOINTS,
    fetch_mausamgram_forecast,
    resolve_location,
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self._json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._json_data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, endpoint, json, headers, timeout):
        self.calls.append(
            {"method": "POST", "endpoint": endpoint, "json": json, "headers": headers, "timeout": timeout}
        )
        return self.response

    def get(self, endpoint, params, auth, timeout):
        self.calls.append(
            {"method": "GET", "endpoint": endpoint, "params": params, "auth": auth, "timeout": timeout}
        )
        return self.response


class RaisingSession:
    def post(self, endpoint, json, headers, timeout):
        raise requests.Timeout("timed out")

    def get(self, endpoint, params, auth, timeout):
        raise requests.Timeout("timed out")


class ForecastPipelineTests(unittest.TestCase):
    def test_resolve_location_exact_and_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            location_file = Path(tmpdir) / "locations.json"
            location_file.write_text(
                json.dumps(
                    [
                        {
                            "name": "Chennai",
                            "state": "Tamil Nadu",
                            "lat": 13.0827,
                            "lon": 80.2707,
                            "aliases": ["Madras"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            exact = resolve_location(place="Chennai", location_file=location_file)
            alias = resolve_location(place="madras", location_file=location_file)

        self.assertEqual(exact["name"], "Chennai")
        self.assertEqual(alias["name"], "Chennai")
        self.assertEqual(alias["source"], "locations.json")

    def test_resolve_direct_coordinates(self):
        location = resolve_location(lat="13.08", lon="80.27")
        self.assertEqual(location["source"], "coordinates")
        self.assertAlmostEqual(location["lat"], 13.08)
        self.assertAlmostEqual(location["lon"], 80.27)

    def test_unknown_location_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            location_file = Path(tmpdir) / "locations.json"
            location_file.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                resolve_location(place="Atlantis", location_file=location_file)

    def test_mausamgram_hourly_request_construction_and_json_records(self):
        session = FakeSession(FakeResponse(json_data={"forecast": [{"temp": 31}]}))
        with patch.dict(
            "os.environ",
            {"MAUSAMGRAM_USER": "user1", "MAUSAMGRAM_KEY": "secret1"},
            clear=False,
        ):
            result = fetch_mausamgram_forecast(13.0827, 80.2707, "3hr", session=session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["endpoint"], MAUSAMGRAM_ENDPOINTS["3hr"])
        self.assertEqual(result["request_method"], "POST")
        self.assertEqual(result["records"], [{"temp": 31}])
        self.assertEqual(session.calls[0]["json"]["hourly"], 3)
        self.assertEqual(session.calls[0]["headers"]["user"], "user1")
        self.assertEqual(session.calls[0]["headers"]["key"], "secret1")
        self.assertNotIn("secret1", json.dumps(result))

    def test_mausamgram_daily_uses_get_with_basic_auth(self):
        session = FakeSession(FakeResponse(json_data=[{"tmax": 33}]))
        with patch.dict(
            "os.environ",
            {"MAUSAMGRAM_USER": "user1", "MAUSAMGRAM_KEY": "secret1"},
            clear=False,
        ):
            result = fetch_mausamgram_forecast(18.4, 74.4, "daily", session=session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["endpoint"], MAUSAMGRAM_ENDPOINTS["daily"])
        self.assertEqual(result["request_method"], "GET")
        self.assertEqual(session.calls[0]["params"], {"lat": 18.4, "lon": 74.4})
        self.assertEqual(session.calls[0]["auth"], ("user1", "secret1"))
        self.assertNotIn("secret1", json.dumps(result))

    def test_mausamgram_non_json_preserves_raw_response(self):
        session = FakeSession(FakeResponse(text="plain response", json_error=True))
        with patch.dict(
            "os.environ",
            {"MAUSAMGRAM_USER": "user1", "MAUSAMGRAM_KEY": "secret1"},
            clear=False,
        ):
            result = fetch_mausamgram_forecast(13.0827, 80.2707, "1hr", session=session)

        self.assertEqual(result["status"], "parser_warning")
        self.assertEqual(result["raw_response"], "plain response")

    def test_mausamgram_http_error_returns_error_result(self):
        with patch.dict(
            "os.environ",
            {"MAUSAMGRAM_USER": "user1", "MAUSAMGRAM_KEY": "secret1"},
            clear=False,
        ):
            result = fetch_mausamgram_forecast(13.0827, 80.2707, "daily", session=RaisingSession())

        self.assertEqual(result["status"], "error")
        self.assertIn("Mausamgram request failed", result["error"])

    def test_mausamgram_missing_credentials_returns_error_result(self):
        with patch.dict("os.environ", {"MAUSAMGRAM_USER": "", "MAUSAMGRAM_KEY": ""}, clear=False):
            result = fetch_mausamgram_forecast(13.0827, 80.2707, "daily", session=RaisingSession())

        self.assertEqual(result["status"], "error")
        self.assertIn("MAUSAMGRAM_USER", result["error"])


if __name__ == "__main__":
    unittest.main()

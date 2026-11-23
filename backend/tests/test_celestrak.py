import http.client
import urllib.error

import pytest

from app.errors import BadGateway
from app.services import celestrak
from app.services.celestrak import fetch_group, parse_gp_response


def test_parse_json_list():
    assert parse_gp_response(b'[{"NORAD_CAT_ID": 25544}]', "application/json; charset=UTF-8") == [{"NORAD_CAT_ID": 25544}]


@pytest.mark.parametrize(
    "body, content_type",
    [
        (b'Invalid query: "GROUP=x&FORMAT=json" (GROUP=x not found)', "text/plain; charset=UTF-8"),
        (b"GP data has not updated since your last successful download", "text/plain"),
        (b'{"not": "a list"}', "application/json"),
        (b"<html>", "application/json"),  # claims JSON, isn't
    ],
)
def test_non_list_responses_are_bad_gateway(body, content_type):
    with pytest.raises(BadGateway) as e:
        parse_gp_response(body, content_type)
    assert e.value.code == "celestrak_unavailable"


def test_celestrak_text_reply_is_passed_on():
    with pytest.raises(BadGateway) as e:
        parse_gp_response(b"GP data has not updated since your last successful download", "text/plain")
    assert "has not updated" in e.value.message


@pytest.mark.parametrize("error", [ConnectionResetError("reset by peer"), http.client.IncompleteRead(b"[{")])
def test_connection_dropped_mid_download_is_bad_gateway(monkeypatch, error):
    class DroppedResponse:
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            raise error

    monkeypatch.setattr(celestrak.urllib.request, "urlopen", lambda *args, **kwargs: DroppedResponse())
    with pytest.raises(BadGateway):
        fetch_group("stations")


def test_network_failure_is_bad_gateway(monkeypatch):
    def offline(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(celestrak.urllib.request, "urlopen", offline)
    with pytest.raises(BadGateway) as e:
        fetch_group("stations")
    assert e.value.code == "celestrak_unavailable"

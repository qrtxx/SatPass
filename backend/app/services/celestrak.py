"""Downloads orbital elements (GP data in OMM JSON format) from CelesTrak."""

import http.client
import json
import urllib.request
from collections.abc import Callable

from app.errors import BadGateway

Fetcher = Callable[[str], list[dict]]

GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
# The "active" group (~17k satellites, ~7 MB) took 68 s to download when measured.
TIMEOUT_S = 180


def parse_gp_response(body: bytes, content_type: str) -> list[dict]:
    """CelesTrak answers problems (unknown group, too many downloads) with HTTP 200 and plain text."""
    try:
        data = json.loads(body) if "json" in content_type else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        text = body.decode("utf-8", errors="replace").strip()[:200]
        raise BadGateway("celestrak_unavailable", f"CelesTrak did not return orbital data: {text}")
    return data


def fetch_group(group: str) -> list[dict]:
    request = urllib.request.Request(f"{GP_URL}?GROUP={group}&FORMAT=json", headers={"User-Agent": "SatPass/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return parse_gp_response(response.read(), response.headers.get("Content-Type", ""))
    # OSError covers URLError, timeouts and connections reset mid-download; HTTPException covers truncated replies.
    except (OSError, http.client.HTTPException) as exc:
        raise BadGateway("celestrak_unavailable", f"Could not reach CelesTrak: {exc}") from exc


def get_fetcher() -> Fetcher:
    """FastAPI dependency, so tests can swap in a fake download."""
    return fetch_group

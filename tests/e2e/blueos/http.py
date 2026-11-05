import json
import urllib.error
import urllib.request
from typing import Any


def request(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body else None
    http_request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read() or "null")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {url} failed ({error.code}): {error.read().decode()}") from error

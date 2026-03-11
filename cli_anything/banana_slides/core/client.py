"""Base HTTP client for the Banana Slides REST API."""

import requests
from typing import Any, Dict, Optional


class APIError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: int = 0, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class BananaSlidesClient:
    """Thin wrapper around the Banana Slides REST API."""

    def __init__(self, base_url: str, access_code: str = "", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.access_code = access_code
        self.timeout = timeout
        self.session = requests.Session()
        if access_code:
            self.session.headers["X-Access-Code"] = access_code

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _raise_for_body(self, resp: requests.Response) -> Dict:
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        if not resp.ok:
            msg = (body or {}).get("error") or resp.reason or "Unknown error"
            raise APIError(str(msg), resp.status_code, body)
        return body

    def get(self, path: str, params: Optional[Dict] = None) -> Dict:
        resp = self.session.get(self._url(path), params=params, timeout=self.timeout)
        return self._raise_for_body(resp)

    def post(self, path: str, json: Optional[Dict] = None, files=None, data=None) -> Dict:
        if files:
            resp = self.session.post(self._url(path), files=files, data=data, timeout=self.timeout)
        else:
            resp = self.session.post(self._url(path), json=json, timeout=self.timeout)
        return self._raise_for_body(resp)

    def put(self, path: str, json: Optional[Dict] = None) -> Dict:
        resp = self.session.put(self._url(path), json=json, timeout=self.timeout)
        return self._raise_for_body(resp)

    def delete(self, path: str) -> Dict:
        resp = self.session.delete(self._url(path), timeout=self.timeout)
        return self._raise_for_body(resp)

    def stream_get(self, path: str, params: Optional[Dict] = None):
        """Return a streaming response (for SSE / chunked transfers)."""
        return self.session.get(
            self._url(path), params=params, stream=True, timeout=self.timeout
        )

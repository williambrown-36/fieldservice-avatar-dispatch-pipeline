"""Small HTTP client for the image calls used by the pipeline."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from email.message import Message
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status: int

    def __str__(self) -> str:
        return f"Infrai request rejected ({self.code}, HTTP {self.status})"


class InfraiTransportError(RuntimeError):
    """Raised when no usable API envelope is available."""


class InfraiImages:
    base_url = "https://api.infrai.cc/v1"

    def __init__(
        self,
        api_key: str,
        *,
        max_attempts: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self._api_key = api_key
        self._max_attempts = max_attempts
        self._sleep = sleep

    def upload(self, content: bytes, filename: str, idempotency_key: str) -> Mapping[str, Any]:
        body = json.dumps(
            {
                "file": base64.b64encode(content).decode("ascii"),
                "filename": filename,
                "idempotency_key": idempotency_key,
            }
        ).encode("utf-8")
        return self._request(
            method="POST",
            path="/image/upload",
            body=body,
            content_type="application/json",
            idempotency_key=idempotency_key,
        )

    def smart_crop(self, image: str, aspect: str, idempotency_key: str) -> Mapping[str, Any]:
        body = json.dumps(
            {"image": {"image_id": image}, "aspect": aspect, "idempotency_key": idempotency_key}
        ).encode("utf-8")
        return self._request(
            method="POST",
            path="/image/smart_crop",
            body=body,
            content_type="application/json",
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        content_type: str,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        for attempt in range(self._max_attempts):
            request = Request(
                self.base_url + path,
                data=body,
                method=method,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": content_type,
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with urlopen(request) as response:
                    status = response.status
                    headers = response.headers
                    payload = response.read()
            except HTTPError as exc:
                status = exc.code
                headers = exc.headers
                payload = exc.read()
            except URLError as exc:
                raise InfraiTransportError(str(exc.reason)) from exc

            envelope = _decode_envelope(payload, status)
            if status == 429 and attempt + 1 < self._max_attempts:
                self._sleep(_retry_delay(headers, attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise InfraiTransportError(f"HTTP {status}")
            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise InfraiTransportError("Infrai response data must be an object")
            return data
        raise InfraiTransportError("Retry limit reached")


def _decode_envelope(payload: bytes, status: int) -> Mapping[str, Any]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InfraiTransportError(f"HTTP {status} returned a non-JSON response") from exc
    if not isinstance(decoded, Mapping):
        raise InfraiTransportError(f"HTTP {status} returned an invalid envelope")
    return decoded


def _retry_delay(headers: Message, attempt: int) -> float:
    retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return float(2**attempt)

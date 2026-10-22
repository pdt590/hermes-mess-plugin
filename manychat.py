"""ManyChat Facebook sendContent client; never expose upstream error bodies."""
import asyncio
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp


@dataclass(frozen=True)
class Delivery:
    success: bool
    error: str = ""
    uncertain: bool = False
    sent_chunks: int = 0


def text_chunks(text, limit=2000):
    """Bound each text message to 2000 UTF-16 units, preserving surrogate pairs."""
    chunk, size = [], 0
    for char in text:
        units = 2 if ord(char) > 0xFFFF else 1
        if size + units > limit:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += units
    if chunk:
        yield "".join(chunk)


def retry_delay(value, attempt):
    if value is None:
        return float(2 ** attempt)
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return float(2 ** attempt)
    if not math.isfinite(seconds):
        return None
    # A long penalty is surfaced to the operator, never shortened.
    return max(0, seconds) if seconds <= 30 else None


class ManyChatClient:
    def __init__(self, session, token, *, timeout=20, base_url="https://api.manychat.com"):
        self.session = session
        self._token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.url = base_url.rstrip("/") + "/fb/sending/sendContent"

    async def send_text(self, contact_id, text):
        if not isinstance(contact_id, str) or not re.fullmatch(r"[1-9][0-9]{0,29}", contact_id):
            return Delivery(False, "invalid_contact")
        if not isinstance(text, str) or not text.strip():
            return Delivery(False, "empty_message")
        sent = 0
        for chunk in text_chunks(text):
            body = {"subscriber_id": int(contact_id), "data": {"version": "v2", "content": {"messages": [{"type": "text", "text": chunk}]}}}
            result = await self._post(body)
            if not result.success:
                return Delivery(False, result.error, result.uncertain, sent)
            sent += 1
        return Delivery(True, sent_chunks=sent)

    async def _post(self, body):
        for attempt in range(3):
            try:
                async with self.session.post(self.url, json=body, headers={"Authorization": f"Bearer {self._token}"}, timeout=self.timeout, allow_redirects=False) as response:
                    if response.status == 429:
                        delay = retry_delay(response.headers.get("Retry-After"), attempt)
                        if attempt == 2 or delay is None:
                            return Delivery(False, "rate_limited")
                    elif 400 <= response.status < 500:
                        return Delivery(False, f"http_{response.status}")
                    elif response.status != 200:
                        return Delivery(False, f"http_{response.status}", uncertain=True)
                    else:
                        # Keep unexpected upstream bodies bounded, never log them.
                        raw = bytearray()
                        async for piece in response.content.iter_chunked(8192):
                            raw.extend(piece)
                            if len(raw) > 65536:
                                return Delivery(False, "invalid_response", uncertain=True)
                        import json
                        try:
                            data = json.loads(raw)
                        except (ValueError, UnicodeError):
                            return Delivery(False, "invalid_response", uncertain=True)
                        if isinstance(data, dict) and data.get("status") == "success":
                            return Delivery(True)
                        if isinstance(data, dict) and data.get("status") == "error":
                            return Delivery(False, "api_error")
                        return Delivery(False, "invalid_response", uncertain=True)
                await asyncio.sleep(delay)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                return Delivery(False, "transport_uncertain", uncertain=True)
        return Delivery(False, "rate_limited")

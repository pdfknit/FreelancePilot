from __future__ import annotations

import httpx
from .config import API_BASE, API_KEY, TIMEOUT


async def post_chat_message(user_tg_id: int, text: str, username: str | None = None):
    url = f"{API_BASE.rstrip('/')}/chat/message/"
    headers = {"X-Telegram-ID": str(user_tg_id)}
    if username:
        headers["X-Telegram-Username"] = username

    if API_KEY:
        headers["X-API-Key"] = API_KEY

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(url, json={"message": text, "channel": "tg"}, headers=headers)
        r.raise_for_status()
        return r.json()

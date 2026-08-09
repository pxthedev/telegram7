from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.config.settings import settings

logger = logging.getLogger(__name__)

_hits: dict[int, list[float]] = {}
_lock = asyncio.Lock()


class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        user_id = getattr(user, "id", None)
        if user_id is None or settings.is_admin(user_id):
            return await handler(event, data)

        now = time.monotonic()
        window = settings.rate_limit_window
        limit = settings.rate_limit_max
        async with _lock:
            timestamps = [t for t in _hits.get(user_id, []) if now - t < window]
            if len(timestamps) >= limit:
                _hits[user_id] = timestamps
                return None
            timestamps.append(now)
            _hits[user_id] = timestamps

        return await handler(event, data)

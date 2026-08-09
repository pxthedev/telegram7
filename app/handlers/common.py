from __future__ import annotations

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.services import user_service

logger = logging.getLogger(__name__)


async def ensure_user(session: AsyncSession, from_user: TgUser) -> User:
    user = await user_service.get_user(session, from_user.id)
    if user is not None:
        return user
    user = await user_service.get_or_create_user(
        session,
        from_user.id,
        from_user.username,
        from_user.first_name,
    )
    await session.commit()
    return user


async def answer(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        pass


async def edit_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> Message | None:
    try:
        if message.photo:
            return await message.edit_caption(
                caption=text, reply_markup=reply_markup, **kwargs
            )
        return await message.edit_text(text=text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return None
        raise


async def send_or_edit_text(
    target: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    try:
        if target.photo:
            await target.answer(text, reply_markup=reply_markup)
        else:
            await edit_message(target, text, reply_markup)
    except TelegramBadRequest:
        logger.warning("Falha ao editar mensagem", exc_info=True)

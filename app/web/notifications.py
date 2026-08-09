from __future__ import annotations

import logging

from aiogram import Bot

from app.database.database import async_session_factory
from app.services import user_service
from app.utils.formatting import fmt_money

logger = logging.getLogger(__name__)


async def notify_payment_confirmed(
    bot: Bot, user_id: int, payment, credited: bool
) -> None:
    try:
        async with async_session_factory() as session:
            user = await user_service.get_user(session, user_id)
            balance = user.balance if user else None

        if credited:
            text = (
                f"✅ Pagamento confirmado!\n\n"
                f"💰 Valor: {fmt_money(payment.amount)}\n"
                f"💳 Saldo atual: {fmt_money(balance)}\n\n"
                f"Obrigado pela preferência!"
            )
        else:
            text = "✅ Pagamento já confirmado anteriormente."
        await bot.send_message(user_id, text)
    except Exception:
        logger.exception("Falha ao notificar pagamento confirmado (user_id=%s)", user_id)

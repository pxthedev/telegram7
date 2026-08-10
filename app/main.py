from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.config.settings import settings
from app.handlers import (
    admin,
    affiliate,
    balance,
    profile,
    purchases,
    shop,
    start,
)
from app.middlewares.database import DatabaseSessionMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.services.payment.provider import get_payment_provider
from app.utils.logging import setup_logging
from app.web.webhook import start_webhook_server, stop_webhook_server

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="🏠 Menu principal"),
    BotCommand(command="pix", description="💰 Adicionar saldo"),
    BotCommand(command="cancel", description="❌ Cancelar ação"),
]

ADMIN_COMMANDS = [
    BotCommand(command="admin", description="⚙️ Painel administrativo"),
    BotCommand(command="addproduto", description="➕ Adicionar produto"),
]


async def setup_commands(bot: Bot) -> None:
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in settings.admin_ids:
        await bot.set_my_commands(
            [*PUBLIC_COMMANDS, *ADMIN_COMMANDS],
            scope=BotCommandScopeChat(chat_id=admin_id),
        )


async def main() -> None:
    setup_logging()

    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN não configurado. Verifique o arquivo .env")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    session_middleware = DatabaseSessionMiddleware()
    throttling_middleware = ThrottlingMiddleware()
    dp.message.middleware(throttling_middleware)
    dp.message.middleware(session_middleware)
    dp.callback_query.middleware(throttling_middleware)
    dp.callback_query.middleware(session_middleware)

    admin.router.message.middleware(admin.AdminAccessMiddleware())
    admin.router.callback_query.middleware(admin.AdminAccessMiddleware())

    for router in (
        start.router,
        shop.router,
        profile.router,
        purchases.router,
        affiliate.router,
        balance.router,
        admin.router,
    ):
        dp.include_router(router)

    provider = get_payment_provider()
    webhook_runner = None

    async def on_startup() -> None:
        nonlocal webhook_runner
        await setup_commands(bot)
        webhook_runner = await start_webhook_server(bot)
        logger.info("Bot iniciado (polling + webhook FreePay)")

    async def on_shutdown() -> None:
        await stop_webhook_server(webhook_runner)
        await provider.close()
        await bot.session.close()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await dp.storage.close()
        await dp.storage.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())

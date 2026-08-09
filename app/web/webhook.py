from __future__ import annotations

import json
import logging

from aiohttp import web

from app.config.settings import settings
from app.database.database import async_session_factory
from app.services.payment.provider import get_payment_provider
from app.services.payment.service import PaymentService
from app.web.notifications import notify_payment_confirmed

logger = logging.getLogger(__name__)


async def freepay_webhook_handler(request: web.Request) -> web.Response:
    try:
        raw = await request.read()
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Webhook FreePay: payload inválido")
        return web.json_response({"error": "invalid_json"}, status=400)

    provider = get_payment_provider()
    if not provider.validate_webhook(dict(request.headers), payload):
        logger.warning("Webhook FreePay: estrutura inválida")
        return web.json_response({"error": "invalid_webhook"}, status=400)

    bot = request.app["bot"]
    service = PaymentService(provider)

    try:
        async with async_session_factory() as session:
            async with session.begin():
                payment, credited = await service.process_webhook(session, payload)
            user_id = payment.user_id if payment is not None else None
        if payment is not None and user_id is not None:
            await notify_payment_confirmed(bot, user_id, payment, credited)
    except Exception:
        logger.exception("Erro ao processar webhook da FreePay")
        return web.json_response({"error": "internal"}, status=500)

    return web.Response(text="ok", status=200)


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


def create_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhooks/freepay", freepay_webhook_handler)
    app.router.add_get("/health", health_handler)
    return app


async def start_webhook_server(bot) -> web.AppRunner:
    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()
    logger.info("Servidor de webhook ouvindo em %s:%s", settings.webhook_host, settings.webhook_port)
    return runner


async def stop_webhook_server(runner: web.AppRunner | None) -> None:
    if runner is not None:
        await runner.cleanup()

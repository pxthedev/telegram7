from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models.user import User
from app.exceptions import PaymentError
from app.handlers.common import answer, edit_message, ensure_user
from app.keyboards.balance import (
    balance_amounts_kb,
    cancel_fsm_kb,
    expired_payment_kb,
    payment_done_kb,
    payment_kb,
)
from app.keyboards.callbacks import BalanceCB
from app.services.payment.base import PaymentStatus
from app.services.payment.provider import get_payment_provider
from app.services.payment.service import PaymentService
from app.states.user_states import BalanceStates
from app.utils.formatting import esc, fmt_money
from app.utils.qr import make_pix_qr
from app.utils.validators import (
    parse_amount,
    validate_deposit_amount,
)

logger = logging.getLogger(__name__)

router = Router()


def _payment_caption(payment, status_label: str) -> str:
    pix = payment.pix_copy_paste or ""
    return (
        f"💰 Pagamento PIX\n\n"
        f"Valor: {fmt_money(payment.amount)}\n"
        f"Status: {status_label}\n\n"
        f"Use o QR Code acima ou copie o código abaixo:\n\n"
        f"<code>{esc(pix)}</code>"
    )


async def _send_pix_payment(
    bot: Bot,
    chat_id: int,
    payment,
) -> None:
    png = make_pix_qr(payment.pix_copy_paste or "")
    caption = _payment_caption(payment, "⏳ Aguardando pagamento...")
    await bot.send_photo(
        chat_id=chat_id,
        photo=BufferedInputFile(png, filename="pix.png"),
        caption=caption,
        reply_markup=payment_kb(payment.id),
    )


async def _create_and_show_pix(
    bot: Bot, session: AsyncSession, user: User, amount: Decimal
) -> None:
    service = PaymentService(get_payment_provider())
    telegram_id = user.telegram_id
    user_id = user.id
    try:
        async with session.begin_nested():
            payment = await service.create_deposit(session, user, amount)
    except PaymentError:
        logger.exception("Falha ao gerar PIX para user_id=%s", user_id)
        await bot.send_message(
            telegram_id,
            "❌ Não foi possível gerar o PIX.\n\n"
            "Tente novamente em alguns instantes.",
            reply_markup=payment_done_kb(),
        )
        return
    await session.commit()
    await _send_pix_payment(bot, telegram_id, payment)


@router.message(Command("pix"))
async def cmd_pix(message: Message, state: FSMContext, session: AsyncSession) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            f"💰 Para adicionar saldo, use o comando:\n\n"
            f"<code>/pix {fmt_money(settings.min_deposit_amount)}</code>\n\n"
            f"Valores entre {fmt_money(settings.min_deposit_amount)} e "
            f"{fmt_money(settings.max_deposit_amount)}.\n\n"
            f"Exemplo: /pix 50",
            reply_markup=cancel_fsm_kb(),
        )
        return
    amount = parse_amount(args[1])
    if not validate_deposit_amount(amount):
        await message.answer(
            f"❌ Valor inválido. Escolha entre "
            f"{fmt_money(settings.min_deposit_amount)} e "
            f"{fmt_money(settings.max_deposit_amount)}.",
            reply_markup=cancel_fsm_kb(),
        )
        return
    user = await ensure_user(session, message.from_user)
    await state.clear()
    await _create_and_show_pix(message.bot, session, user, amount)


@router.callback_query(BalanceCB.filter(F.action == "menu"))
async def cb_balance_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    text = (
        f"💰 Adicionar saldo\n\n"
        f"Seu saldo atual: {fmt_money(user.balance)}\n\n"
        f"Escolha um valor:"
    )
    await edit_message(callback.message, text, balance_amounts_kb())


@router.callback_query(BalanceCB.filter(F.action == "choose"))
async def cb_balance_choose(
    callback: CallbackQuery,
    callback_data: BalanceCB,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await answer(callback)
    amount = parse_amount(callback_data.value)
    if not validate_deposit_amount(amount):
        await edit_message(
            callback.message,
            f"❌ Valor inválido. Escolha entre "
            f"{fmt_money(settings.min_deposit_amount)} e "
            f"{fmt_money(settings.max_deposit_amount)}.",
            balance_amounts_kb(),
        )
        return
    user = await ensure_user(session, callback.from_user)
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _create_and_show_pix(callback.bot, session, user, amount)


@router.callback_query(BalanceCB.filter(F.action == "custom"))
async def cb_balance_custom(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await answer(callback)
    await state.set_state(BalanceStates.custom_amount)
    await edit_message(
        callback.message,
        f"💰 Digite o valor desejado:\n\n"
        f"Valores entre {fmt_money(settings.min_deposit_amount)} e "
        f"{fmt_money(settings.max_deposit_amount)}.\n\n"
        f"Exemplo: 50 ou 49,90",
        cancel_fsm_kb(),
    )


@router.message(BalanceStates.custom_amount)
async def fsm_custom_amount(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    amount = parse_amount(message.text or "")
    if not validate_deposit_amount(amount):
        await message.answer(
            f"❌ Valor inválido. Digite um valor entre "
            f"{fmt_money(settings.min_deposit_amount)} e "
            f"{fmt_money(settings.max_deposit_amount)}:",
            reply_markup=cancel_fsm_kb(),
        )
        return
    await state.update_data(balance_amount=str(amount))
    user = await ensure_user(session, message.from_user)
    await state.clear()
    await _create_and_show_pix(message.bot, session, user, amount)


@router.callback_query(BalanceCB.filter(F.action == "check"))
async def cb_balance_check(
    callback: CallbackQuery,
    callback_data: BalanceCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    service = PaymentService(get_payment_provider())
    payment = await service.get_payment(session, callback_data.payment_id)
    if payment is None or payment.user_id != user.id:
        await edit_message(
            callback.message,
            "❌ Cobrança não encontrada.",
            payment_done_kb(),
        )
        return
    try:
        async with session.begin_nested():
            await service.check_payment(session, payment)
        await session.commit()
    except PaymentError:
        await edit_message(
            callback.message,
            "❌ Não foi possível consultar o pagamento agora.\n\n"
            "Tente novamente em alguns instantes.",
            payment_kb(payment.id),
        )
        return

    if payment.status == PaymentStatus.PAID.value:
        await edit_message(
            callback.message,
            f"✅ Pagamento confirmado!\n\n"
            f"💰 Valor: {fmt_money(payment.amount)}\n\n"
            f"Seu saldo foi creditado. Obrigado!",
            payment_done_kb(),
        )
    elif payment.status == PaymentStatus.EXPIRED.value:
        await edit_message(
            callback.message,
            "⌛ Esta cobrança expirou.",
            expired_payment_kb(),
        )
    elif payment.status == PaymentStatus.CANCELLED.value:
        await edit_message(
            callback.message,
            "❌ Esta cobrança foi cancelada.",
            payment_done_kb(),
        )
    else:
        await edit_message(
            callback.message,
            _payment_caption(payment, "⏳ Aguardando pagamento..."),
            payment_kb(payment.id),
        )


@router.callback_query(BalanceCB.filter(F.action == "cancel"))
async def cb_balance_cancel(
    callback: CallbackQuery,
    callback_data: BalanceCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    service = PaymentService(get_payment_provider())
    payment = await service.get_payment(session, callback_data.payment_id)
    if payment is None or payment.user_id != user.id:
        await edit_message(
            callback.message,
            "❌ Cobrança não encontrada.",
            payment_done_kb(),
        )
        return
    if payment.status == PaymentStatus.PENDING.value:
        payment.status = PaymentStatus.CANCELLED.value
        await session.commit()
    await edit_message(
        callback.message,
        "❌ Cobrança cancelada.",
        payment_done_kb(),
    )

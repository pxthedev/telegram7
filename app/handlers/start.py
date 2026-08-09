from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models.user import User
from app.handlers.common import answer, edit_message, ensure_user
from app.keyboards.callbacks import MenuCB
from app.keyboards.main import back_to_menu_kb, main_menu_kb
from app.services import user_service
from app.utils.formatting import esc

router = Router()


def _welcome_text(user: User) -> str:
    name = user.first_name or user.username or "amigo(a)"
    return (
        f"Olá, {esc(name)}, seja bem-vindo(a) à nossa loja!\n\n"
        f"{settings.shop_description}\n\n"
        f"Escolha uma opção abaixo: 👇"
    )


def _benefits_text() -> str:
    return (
        f"🔓 Benefícios\n\n"
        f"{settings.benefits_text}\n\n"
        f"🛒 Compras qualificadas são contabilizadas automaticamente."
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    referrer_code = None
    if message.text and len(message.text.split()) > 1:
        referrer_code = message.text.split(maxsplit=1)[1].strip()
    user = await user_service.get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        referrer_code=referrer_code,
    )
    await session.commit()
    await state.clear()
    await message.answer(_welcome_text(user), reply_markup=main_menu_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ação cancelada.", reply_markup=main_menu_kb())


@router.callback_query(MenuCB.filter(F.action == "main"))
async def cb_menu_main(callback, session: AsyncSession) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    await edit_message(callback.message, _welcome_text(user), main_menu_kb())


@router.callback_query(MenuCB.filter(F.action == "benefits"))
async def cb_menu_benefits(callback) -> None:
    await answer(callback)
    await edit_message(callback.message, _benefits_text(), back_to_menu_kb())

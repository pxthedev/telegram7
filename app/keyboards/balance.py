from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import BalanceCB, MenuCB


def balance_amounts_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="R$ 15", callback_data=BalanceCB(action="choose", value="15").pack()
                ),
                InlineKeyboardButton(
                    text="R$ 25", callback_data=BalanceCB(action="choose", value="25").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="R$ 50", callback_data=BalanceCB(action="choose", value="50").pack()
                ),
                InlineKeyboardButton(
                    text="R$ 100", callback_data=BalanceCB(action="choose", value="100").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Outro valor", callback_data=BalanceCB(action="custom").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ],
        ]
    )


def payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Verificar pagamento",
                    callback_data=BalanceCB(action="check", payment_id=payment_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancelar",
                    callback_data=BalanceCB(action="cancel", payment_id=payment_id).pack(),
                )
            ],
        ]
    )


def expired_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Gerar novo PIX",
                    callback_data=BalanceCB(action="menu").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ],
        ]
    )


def payment_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ]
        ]
    )


def cancel_fsm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Cancelar", callback_data=MenuCB(action="main").pack()
                )
            ]
        ]
    )

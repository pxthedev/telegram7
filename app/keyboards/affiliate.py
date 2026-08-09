from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import AffiliateCB, MenuCB


def affiliate_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Compartilhar", callback_data=AffiliateCB(action="share").pack()
                ),
                InlineKeyboardButton(
                    text="💰 Histórico", callback_data=AffiliateCB(action="history").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ],
        ]
    )


def affiliate_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=AffiliateCB(action="panel").pack()
                )
            ]
        ]
    )


def affiliate_history_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Anterior",
                callback_data=AffiliateCB(action="history", page=page - 1).pack(),
            )
        )
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="Próximo ▶️",
                callback_data=AffiliateCB(action="history", page=page + 1).pack(),
            )
        )
    rows: list[list[InlineKeyboardButton]] = []
    if buttons:
        rows.append(buttons)
    rows.append(
        [
            InlineKeyboardButton(
                text="« Voltar", callback_data=AffiliateCB(action="panel").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

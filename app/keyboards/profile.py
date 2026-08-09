from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import AffiliateCB, BalanceCB, MenuCB, ProfileCB, PurchasesCB


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Recargas", callback_data=ProfileCB(action="rcg").pack()
                ),
                InlineKeyboardButton(
                    text="🛒 Histórico de compras",
                    callback_data=PurchasesCB(action="list").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤝 Afiliados", callback_data=AffiliateCB(action="panel").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ],
        ]
    )


def history_kb(
    prefix: str, page: int, total_pages: int, back_callback: str
) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Anterior", callback_data=f"{prefix}:{page - 1}"
            )
        )
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="Próximo ▶️", callback_data=f"{prefix}:{page + 1}"
            )
        )
    rows: list[list[InlineKeyboardButton]] = []
    if buttons:
        rows.append(buttons)
    rows.append(
        [
            InlineKeyboardButton(
                text="« Voltar", callback_data=back_callback
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

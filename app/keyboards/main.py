from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import AffiliateCB, BalanceCB, MenuCB, ProfileCB, ShopCB


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Comprar", callback_data=ShopCB(action="list").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔓 Benefícios", callback_data=MenuCB(action="benefits").pack()
                ),
                InlineKeyboardButton(
                    text="🤝 Afiliados", callback_data=AffiliateCB(action="panel").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💎 Seu Perfil", callback_data=ProfileCB(action="view").pack()
                ),
                InlineKeyboardButton(
                    text="💰 Adicionar Saldo", callback_data=BalanceCB(action="menu").pack()
                ),
            ],
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=MenuCB(action="main").pack()
                )
            ]
        ]
    )

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.database.models.user import User
from app.keyboards.callbacks import AdminCB, BalanceCB, MenuCB


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Dashboard", callback_data=AdminCB(action="dash").pack()
                ),
                InlineKeyboardButton(
                    text="👥 Usuários", callback_data=AdminCB(action="users").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛒 Produtos", callback_data=AdminCB(action="products").pack()
                ),
                InlineKeyboardButton(
                    text="💳 Pagamentos", callback_data=AdminCB(action="payments").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤝 Afiliados", callback_data=AdminCB(action="affiliates").pack()
                ),
                InlineKeyboardButton(
                    text="📦 Estoque", callback_data=AdminCB(action="stock").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Pedidos", callback_data=AdminCB(action="orders").pack()
                ),
                InlineKeyboardButton(
                    text="📜 Logs", callback_data=AdminCB(action="logs").pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Configurações", callback_data=AdminCB(action="config").pack()
                )
            ],
        ]
    )


def admin_dashboard_kb(period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Hoje",
                    callback_data=AdminCB(action="dash", period="today").pack(),
                ),
                InlineKeyboardButton(
                    text="7 dias",
                    callback_data=AdminCB(action="dash", period="7d").pack(),
                ),
                InlineKeyboardButton(
                    text="30 dias",
                    callback_data=AdminCB(action="dash", period="30d").pack(),
                ),
                InlineKeyboardButton(
                    text="Tudo",
                    callback_data=AdminCB(action="dash", period="all").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=AdminCB(action="menu").pack()
                )
            ],
        ]
    )


def admin_back_kb(action: str = "menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=AdminCB(action=action).pack()
                )
            ]
        ]
    )


def admin_zero_stock_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Confirmar", callback_data=AdminCB(action="stockzero").pack()
                ),
                InlineKeyboardButton(
                    text="❌ Cancelar", callback_data=AdminCB(action="menu").pack()
                ),
            ]
        ]
    )


def admin_products_kb(
    products: list[Product], page: int, total_pages: int
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'🟢' if p.active else '🔴'} {p.name}",
                callback_data=AdminCB(action="prod", product_id=p.id).pack(),
            )
        ]
        for p in products
    ]
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="◀️", callback_data=AdminCB(action="products", page=page - 1).pack()
            )
        )
    nav.append(
        InlineKeyboardButton(
            text="➕ Novo", callback_data=AdminCB(action="prodnew").pack()
        )
    )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                text="▶️", callback_data=AdminCB(action="products", page=page + 1).pack()
            )
        )
    rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="« Voltar", callback_data=AdminCB(action="menu").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_kb(product: Product) -> InlineKeyboardMarkup:
    toggle_label = "🚫 Desativar" if product.active else "✅ Ativar"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Alterar preço",
                    callback_data=AdminCB(action="prodprice", product_id=product.id).pack(),
                ),
                InlineKeyboardButton(
                    text="📦 Alterar estoque",
                    callback_data=AdminCB(action="prodstock", product_id=product.id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=toggle_label,
                    callback_data=AdminCB(action="prodtoggle", product_id=product.id).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑️ Excluir",
                    callback_data=AdminCB(action="proddel", product_id=product.id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=AdminCB(action="products").pack()
                )
            ],
        ]
    )


def admin_list_paginated_kb(
    action: str, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="◀️", callback_data=AdminCB(action=action, page=page - 1).pack()
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                text="▶️", callback_data=AdminCB(action=action, page=page + 1).pack()
            )
        )
    rows = [nav] if nav else []
    rows.append(
        [InlineKeyboardButton(text="« Voltar", callback_data=AdminCB(action="menu").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

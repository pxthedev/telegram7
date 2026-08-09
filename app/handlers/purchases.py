from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.common import answer, edit_message, ensure_user
from app.keyboards.callbacks import ProfileCB, PurchasesCB
from app.keyboards.profile import history_kb
from app.services import purchase_service
from app.utils.formatting import esc, fmt_money
from app.utils.pagination import paginate

router = Router()


@router.callback_query(PurchasesCB.filter(F.action == "list"))
async def cb_purchase_history(
    callback: CallbackQuery,
    callback_data: PurchasesCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    rows, total = await purchase_service.get_user_purchases(
        session, user.id, callback_data.page
    )
    page_rows, total_pages = paginate(rows, callback_data.page, per_page=5)
    if not page_rows:
        text = "🛒 Histórico de compras\n\nNenhuma compra encontrada."
    else:
        lines = []
        for purchase, product_name, _content in page_rows:
            lines.append(
                f"#{purchase.id} • {esc(product_name)}\n"
                f"Valor: {fmt_money(purchase.amount)}\n"
                f"Data: {purchase.created_at.strftime('%d/%m/%Y %H:%M')}"
            )
        text = "🛒 Histórico de compras\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        history_kb(
            "purch:list",
            callback_data.page,
            total_pages,
            ProfileCB(action="view").pack(),
        ),
    )

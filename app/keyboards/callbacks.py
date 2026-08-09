from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str


class ShopCB(CallbackData, prefix="shop"):
    action: str
    product_id: int = 0


class ProfileCB(CallbackData, prefix="prof"):
    action: str
    page: int = 1


class BalanceCB(CallbackData, prefix="bal"):
    action: str
    value: str = ""
    payment_id: int = 0


class AffiliateCB(CallbackData, prefix="aff"):
    action: str
    page: int = 1


class PurchasesCB(CallbackData, prefix="purch"):
    action: str
    page: int = 1


class AdminCB(CallbackData, prefix="adm"):
    action: str
    product_id: int = 0
    page: int = 1
    period: str = ""

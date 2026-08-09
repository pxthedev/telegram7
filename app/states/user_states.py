from aiogram.fsm.state import State, StatesGroup


class BalanceStates(StatesGroup):
    custom_amount = State()
    customer_name = State()
    customer_email = State()
    customer_phone = State()
    customer_document = State()


class ProductCreateStates(StatesGroup):
    name = State()
    description = State()
    content = State()
    price = State()
    stock = State()


class ProductEditStates(StatesGroup):
    price = State()
    stock = State()

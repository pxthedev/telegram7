from aiogram.fsm.state import State, StatesGroup


class BalanceStates(StatesGroup):
    custom_amount = State()


class ProductCreateStates(StatesGroup):
    name = State()
    description = State()
    content = State()
    price = State()
    stock = State()


class ProductCommandStates(StatesGroup):
    name = State()
    description = State()
    price = State()


class ProductEditStates(StatesGroup):
    price = State()
    stock = State()

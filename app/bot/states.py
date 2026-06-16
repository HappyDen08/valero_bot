from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    full_name = State()
    phone = State()
    salon = State()
    city = State()


class AddSale(StatesGroup):
    sale_date = State()
    product_type = State()
    fabric = State()
    doc_photo = State()

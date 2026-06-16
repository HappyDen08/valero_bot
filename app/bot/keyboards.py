from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_ADD_SALE = "➕ Додати продаж"
BTN_CABINET = "👤 Особистий кабінет"
BTN_MY_SALES = "📋 Мої продажі"
BTN_RATING = "🏆 Рейтинг"
BTN_SKIP = "Пропустити ⏭"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_ADD_SALE)],
        [KeyboardButton(text=BTN_CABINET), KeyboardButton(text=BTN_MY_SALES)],
        [KeyboardButton(text=BTN_RATING)],
    ],
    resize_keyboard=True,
)

phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Поділитися номером", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

skip_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SKIP)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

product_type_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Диван", callback_data="ptype:sofa"),
            InlineKeyboardButton(text="Ліжко", callback_data="ptype:bed"),
            InlineKeyboardButton(text="Крісло", callback_data="ptype:chair"),
        ],
    ]
)
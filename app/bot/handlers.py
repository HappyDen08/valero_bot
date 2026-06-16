import logging
from datetime import date, datetime
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from django.conf import settings

from . import db
from .keyboards import (
    BTN_ADD_SALE,
    BTN_CABINET,
    BTN_MY_SALES,
    BTN_RATING,
    BTN_SKIP,
    main_menu,
    phone_kb,
    product_type_kb,
    skip_kb,
)
from .states import AddSale, Registration

logger = logging.getLogger(__name__)
router = Router()

STATUS_EMOJI = {"Очікує перевірки": "⏳", "Підтверджено": "✅", "Відхилено": "❌"}


# ---------------------------------------------------------------- реєстрація

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    participant = await db.get_participant(message.from_user.id)
    if participant:
        await message.answer(
            f"Вітаємо, {participant.full_name}! 👋", reply_markup=main_menu
        )
        return
    await message.answer(
        "🎉 <b>VELORO — 2 роки разом!</b>\n\n"
        "Сьогодні VELORO виповнюється 2 роки. І насамперед ми хочемо сказати вам "
        "просте, але дуже важливе слово — дякуємо. ❤️\n\n"
        "Ми не ідеальні. За цей час ми робили помилки, вчилися на них і ставали кращими. "
        "Але одне залишалося незмінним — бажання створювати для вас найкращий сервіс. "
        "Ми цінуємо кожного з вас, прислухаємося до ваших відгуків і пропозицій, адже "
        "саме завдяки вам ми ростемо, розвиваємося та рухаємося вперед.\n\n"
        "Тому на знак нашої вдячності ми запускаємо святковий розіграш для всіх учасників!\n\n"
        "🎁 Головний приз — новенький iPhone 17 Pro 📱.\n\n"
        "🎉 А також на вас чекають 🚀 додаткові цінні призи 🚀, тож шанс виграти "
        "матимуть одразу кілька щасливців.\n\n"
        "<b>Як взяти участь?</b>\n"
        "Умови максимально прості:\n"
        "✔️ Зареєструйтеся в Telegram-боті.\n"
        "✔️ Вносьте свої продажі.\n"
        "✔️ Отримуйте квитки для участі в розіграші.\n\n"
        "🎲 1 підтверджений продаж = 1 квиток 🎲\n\n"
        "Чим більше продажів — тим більше квитків і тим вищі ваші шанси на перемогу. 🍀\n\n"
        "У боті ви зможете:\n"
        "🔹 стежити за кількістю своїх квитків;\n"
        "🔹 переглядати статус поданих продажів.\n\n"
        "Наприкінці розіграшу ми випадковим чином визначимо переможців додаткових призів, "
        "а головний щасливчик стане власником нового iPhone 17 Pro! 📱✨\n\n"
        "Бажаємо вам багато успішних продажів, удачі та нехай саме ваш квиток стане "
        "переможним! 🤝🍀\n\n"
        "❤️ VELORO — 2 роки розвитку, партнерства та спільних перемог. ❤️\n\n"
        "<i>IT Matters.</i>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Почнемо реєстрацію. Введіть ваші <b>прізвище та ім'я</b>:")
    await state.set_state(Registration.full_name)


@router.message(Registration.full_name, F.text)
async def reg_full_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer("Будь ласка, введіть <b>прізвище та ім'я</b>:")
        return
    await state.update_data(full_name=name)
    await message.answer(
        "Поділіться вашим номером телефону кнопкою нижче 👇", reply_markup=phone_kb
    )
    await state.set_state(Registration.phone)


@router.message(Registration.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext):
    if message.contact.user_id != message.from_user.id:
        await message.answer("Будь ласка, поділіться <b>власним</b> контактом 👇")
        return
    await state.update_data(phone=message.contact.phone_number)
    await message.answer(
        "Введіть назву вашого <b>меблевого салону</b>:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.salon)


@router.message(Registration.phone)
async def reg_phone_invalid(message: Message):
    await message.answer("Натисніть кнопку «📱 Поділитися номером» нижче 👇")


@router.message(Registration.salon, F.text)
async def reg_salon(message: Message, state: FSMContext):
    await state.update_data(salon=message.text)
    await message.answer("Введіть назву <b>фабрики</b>:")
    await state.set_state(Registration.factory)


@router.message(Registration.factory, F.text)
async def reg_factory(message: Message, state: FSMContext):
    await state.update_data(factory=message.text)
    await message.answer("Введіть ваше <b>місто</b>:")
    await state.set_state(Registration.city)


@router.message(Registration.city, F.text)
async def reg_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    data = await state.get_data()
    await db.create_participant(message.from_user.id, data)
    await state.clear()
    await message.answer(
        "✅ Реєстрацію завершено!\n\n"
        "Тепер ви можете додавати продажі та брати участь у розіграші. Успіхів! 🍀",
        reply_markup=main_menu,
    )


# ------------------------------------------------------------ подання продажу

@router.message(F.text == BTN_ADD_SALE)
async def add_sale_start(message: Message, state: FSMContext):
    participant = await db.get_participant(message.from_user.id)
    if not participant:
        await message.answer("Спочатку зареєструйтесь: /start")
        return
    campaign = await db.get_current_campaign()
    if not campaign:
        await message.answer("Наразі немає активної акції. Слідкуйте за оголошеннями!")
        return
    if date.today() > campaign.end_date:
        await message.answer(
            f"Прийом продажів за акцією «{campaign.name}» завершено "
            f"{campaign.end_date.strftime('%d.%m.%Y')}."
        )
        return
    await state.set_state(AddSale.sale_date)
    await message.answer(
        "📅 Введіть <b>дату продажу</b> у форматі ДД.ММ.РРРР (наприклад, 05.06.2026):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AddSale.sale_date, F.text)
async def sale_date_step(message: Message, state: FSMContext):
    try:
        sale_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Невірний формат. Введіть дату як ДД.ММ.РРРР:")
        return
    if sale_date > date.today():
        await message.answer("Дата продажу не може бути в майбутньому. Спробуйте ще раз:")
        return
    await state.update_data(sale_date=sale_date.isoformat())
    await state.set_state(AddSale.product_type)
    await message.answer("🛋 Оберіть <b>виріб</b>:", reply_markup=product_type_kb)


@router.callback_query(AddSale.product_type, F.data.startswith("ptype:"))
async def product_type_step(callback: CallbackQuery, state: FSMContext):
    await state.update_data(product_type=callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(AddSale.fabric)
    await callback.message.answer("🧵 Введіть <b>назву тканини Veloro</b>:")
    await callback.answer()


@router.message(AddSale.fabric, F.text)
async def fabric_step(message: Message, state: FSMContext):
    await state.update_data(fabric=message.text)
    await state.set_state(AddSale.doc_photo)
    await message.answer(
        "📄 Надішліть <b>фото замовлення або документа</b> (за бажанням) "
        "або натисніть «Пропустити»:",
        reply_markup=skip_kb,
    )


@router.message(AddSale.doc_photo, F.photo)
async def doc_photo_step(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(doc_photo_file_id=message.photo[-1].file_id)
    await submit_sale(message, state, bot)


@router.message(AddSale.doc_photo, F.text == BTN_SKIP)
async def doc_photo_skip(message: Message, state: FSMContext, bot: Bot):
    await submit_sale(message, state, bot)


@router.message(AddSale.doc_photo)
async def doc_photo_invalid(message: Message):
    await message.answer("Надішліть <b>фото</b> документа 📄 або натисніть «Пропустити»")


async def submit_sale(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    data["sale_date"] = date.fromisoformat(data["sale_date"])
    await state.clear()

    participant = await db.get_participant(message.from_user.id)
    campaign = await db.get_current_campaign()
    sale = await db.create_sale(participant, campaign, data)
    await download_photos(bot, sale, data)

    await message.answer(
        f"✅ Ваш продаж №{sale.id} прийнято!\n\n"
        f"📋 Статус: <b>⏳ Очікує перевірки</b>\n\n"
        f"Після підтвердження вам буде нараховано квиток. 🎫\n\n"
        f"⚠️ Усі результати розіграшів, інформація про переможців та важливі "
        f"оновлення публікуються в наших соцмережах:\n\n"
        f"📸 Instagram: https://www.instagram.com/veloro.textile/\n"
        f"📢 Telegram: https://t.me/velorotextile",
        reply_markup=main_menu,
        disable_web_page_preview=True,
    )


async def download_photos(bot: Bot, sale, data: dict):
    """Дублюємо фото з Telegram на диск — для адмінки та збереження доказів."""
    if not data.get("doc_photo_file_id"):
        return
    media_root = Path(settings.MEDIA_ROOT)
    (media_root / "sales").mkdir(parents=True, exist_ok=True)
    try:
        path = f"sales/{sale.id}_doc.jpg"
        await bot.download(data["doc_photo_file_id"], destination=media_root / path)
        await db.attach_photo(sale, "doc_photo", path)
    except Exception:
        logger.exception("Не вдалося завантажити фото для продажу %s", sale.id)


# ------------------------------------------------------------------- кабінет

@router.message(F.text == BTN_CABINET)
async def cabinet(message: Message):
    participant = await db.get_participant(message.from_user.id)
    if not participant:
        await message.answer("Спочатку зареєструйтесь: /start")
        return
    stats = await db.cabinet_stats(participant)
    tickets = stats["tickets"]
    tickets_text = ", ".join(tickets) if tickets else "поки немає"
    await message.answer(
        f"👤 <b>{participant.full_name}</b>\n"
        f"🏬 {participant.salon}, {participant.city}\n\n"
        f"✅ Підтверджених продажів: <b>{stats['approved']}</b>\n"
        f"🎫 Квитків: <b>{len(tickets)}</b>\n"
        f"Ваші квитки: {tickets_text}",
        reply_markup=main_menu,
    )


@router.message(F.text == BTN_MY_SALES)
async def my_sales_handler(message: Message):
    participant = await db.get_participant(message.from_user.id)
    if not participant:
        await message.answer("Спочатку зареєструйтесь: /start")
        return
    sales = await db.my_sales(participant)
    if not sales:
        await message.answer("Ви ще не подали жодного продажу.", reply_markup=main_menu)
        return
    lines = ["📋 <b>Ваші продажі</b> (останні 15):\n"]
    for s in sales:
        emoji = STATUS_EMOJI.get(s["status"], "")
        line = f"{emoji} №{s['id']} від {s['date']} — {s['product']}, {s['fabric']}"
        if s["reason"]:
            line += f"\n   └ причина: {s['reason']}"
        lines.append(line)
    await message.answer("\n".join(lines), reply_markup=main_menu)


@router.message(F.text == BTN_RATING)
async def rating(message: Message):
    participant = await db.get_participant(message.from_user.id)
    if not participant:
        await message.answer("Спочатку зареєструйтесь: /start")
        return
    data = await db.rating_view(participant)
    if not data["top"]:
        await message.answer("Рейтинг поки порожній — станьте першим! 🚀", reply_markup=main_menu)
        return
    lines = ["🏆 <b>ТОП-20 учасників</b>\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, r in enumerate(data["top"], 1):
        prefix = medals.get(i, f"{i}.")
        lines.append(f"{prefix} {r['name']} — квитків: {r['tickets']}")
    if data["my_position"]:
        lines.append(
            f"\n📍 Ваше місце: <b>№{data['my_position']}</b> "
            f"(квитків: {data['my_tickets']})"
        )
    else:
        lines.append("\n📍 У вас поки немає квитків — додайте перший продаж!")
    await message.answer("\n".join(lines), reply_markup=main_menu)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Як це працює:</b>\n\n"
        "1. Продали виріб у тканині Veloro — натисніть «➕ Додати продаж».\n"
        "2. Заповніть дані та додайте фото документа.\n"
        "3. Після перевірки вам нарахується квиток 🎫\n"
        "4. Чим більше квитків — тим більший шанс виграти приз! 🎁",
        reply_markup=main_menu,
    )


@router.message(F.text)
async def fallback(message: Message, state: FSMContext):
    if await state.get_state():
        await message.answer("Будь ласка, дотримуйтесь інструкції вище 🙂")
        return
    await message.answer("Оберіть дію з меню 👇", reply_markup=main_menu)

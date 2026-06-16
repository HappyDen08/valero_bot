# Демо-дані: 50 учасників з підтвердженими продажами і квитками.
# Запуск: docker compose exec -T web python manage.py shell < scripts/seed_demo.py
import random
from datetime import date, timedelta

from core.models import Campaign, Participant, Sale, Ticket

random.seed(42)
camp = Campaign.current()
if camp is None:
    camp = Campaign.objects.create(
        name="Розіграш iPhone 2026",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        is_active=True,
    )
    print("активної кампанії не було — створено:", camp)

first_m = ["Андрій", "Олег", "Сергій", "Володимир", "Тарас", "Максим", "Юрій",
           "Богдан", "Дмитро", "Назар", "Ігор", "Василь", "Роман", "Петро", "Олександр"]
first_f = ["Олена", "Ірина", "Наталія", "Марія", "Оксана", "Тетяна", "Юлія",
           "Анна", "Світлана", "Катерина", "Людмила", "Вікторія", "Соломія", "Дарина"]
last = ["Шевченко", "Коваленко", "Бондаренко", "Ткаченко", "Кравченко", "Мельник",
        "Поліщук", "Лисенко", "Савченко", "Руденко", "Марченко", "Петренко",
        "Іваненко", "Гончарук", "Семенюк", "Романюк", "Левчук", "Дубенко", "Хоменко", "Зайцев"]
mid_m = ["Іванович", "Петрович", "Олегович", "Андрійович", "Васильович", "Сергійович", "Богданович"]
mid_f = ["Іванівна", "Петрівна", "Олегівна", "Андріївна", "Василівна", "Сергіївна", "Богданівна"]
salons = ["Меблі Люкс", "Comfort Home", "Диван і Ко", "Меблевий Двір", "Soft Loft",
          "ВсіМеблі", "Затишок", "Меблі Стиль", "Інтер'єр Плюс", "Дім Меблів"]
factories = ["Фабрика Комфорт", "Léon", "Davidos", "Bisons", "МебліТекс", "Соната", "Прогрес"]
cities = ["Київ", "Львів", "Одеса", "Харків", "Дніпро", "Вінниця", "Тернопіль",
          "Луцьк", "Івано-Франківськ", "Рівне"]
fabrics = ["Veloro Lux", "Veloro Soft", "Veloro Velvet", "Veloro Aqua", "Veloro Nordic", "Veloro Classic"]
ptypes = ["sofa", "bed", "chair"]

max_day = (min(date.today(), camp.end_date) - camp.start_date).days
created_p = created_s = 0

for i in range(50):
    if random.random() < 0.5:
        name = f"{random.choice(last)} {random.choice(first_m)} {random.choice(mid_m)}"
    else:
        name = f"{random.choice(last)}а {random.choice(first_f)} {random.choice(mid_f)}"
    p, is_new = Participant.objects.get_or_create(
        telegram_id=900000000 + i,
        defaults=dict(
            full_name=name,
            phone=f"+38050{random.randint(1000000, 9999999)}",
            salon=random.choice(salons),
            factory=random.choice(factories),
            city=random.choice(cities),
        ),
    )
    if not is_new:
        continue
    created_p += 1
    for j in range(random.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0]):
        ptype = random.choice(ptypes)
        s = Sale.objects.create(
            participant=p,
            campaign=camp,
            sale_date=camp.start_date + timedelta(days=random.randint(0, max_day)),
            product_type=ptype,
            fabric_name=random.choice(fabrics),
            doc_photo_file_id="seed",
            amount=random.choice([None, random.randint(8, 90) * 1000]),
            status=Sale.Status.APPROVED,
            bonus_amount=Sale.BONUS_RATES.get(ptype, 0),
            moderated_by="seed",
        )
        Ticket.objects.create(sale=s, participant=p, campaign=camp)
        created_s += 1

print("створено учасників:", created_p, "| продажів+квитків:", created_s)
print("всього в БД: учасники", Participant.objects.count(), "| квитки", Ticket.objects.count())

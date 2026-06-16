"""Асинхронні обгортки над ORM для хендлерів бота."""
from functools import wraps

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from django.db.models import Count

from core import services
from core.models import Campaign, Participant, Sale, Ticket
from core.utils import normalize_text


def _public_name(full_name: str, phone: str) -> str:
    """'Шевченко Олена' + '+380501234567' -> 'Олена (···67)'."""
    parts = full_name.split()
    first_name = parts[1] if len(parts) >= 2 else parts[0]
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"{first_name} (···{digits[-2:]})"


def db_task(func):
    """ORM у паралельних потоках (а не в одному спільному, як у sync_to_async
    за замовчуванням) + закриття протухлих з'єднань перед кожним викликом."""

    @wraps(func)
    def inner(*args, **kwargs):
        close_old_connections()
        return func(*args, **kwargs)

    return sync_to_async(inner, thread_sensitive=False)


@db_task
def get_participant(telegram_id: int) -> Participant | None:
    return Participant.objects.filter(telegram_id=telegram_id).first()


@db_task
def create_participant(telegram_id: int, data: dict) -> Participant:
    participant = Participant.objects.create(
        telegram_id=telegram_id,
        full_name=normalize_text(data["full_name"]),
        phone=data["phone"],
        salon=normalize_text(data["salon"]),
        city=normalize_text(data["city"]),
    )
    services.log(f"tg:{telegram_id}", "participant_registered", participant_id=participant.id)
    return participant


@db_task
def get_current_campaign() -> Campaign | None:
    return Campaign.current()


@db_task
def create_sale(participant: Participant, campaign: Campaign, data: dict) -> Sale:
    sale = Sale.objects.create(
        participant=participant,
        campaign=campaign,
        sale_date=data["sale_date"],
        product_type=data["product_type"],
        product_name=data.get("product_name", ""),
        fabric_name=normalize_text(data["fabric"]),
        doc_photo_file_id=data.get("doc_photo_file_id", ""),
    )
    services.log(f"tg:{participant.telegram_id}", "sale_submitted", sale_id=sale.id)
    return sale


@db_task
def attach_photo(sale: Sale, field: str, relative_path: str):
    setattr(sale, field, relative_path)
    sale.save(update_fields=[field])


@db_task
def cabinet_stats(participant: Participant) -> dict:
    campaign = Campaign.current()
    tickets = list(
        Ticket.objects.filter(participant=participant, campaign=campaign).order_by("id")
    )
    approved = Sale.objects.filter(
        participant=participant, campaign=campaign, status=Sale.Status.APPROVED
    ).count()
    return {
        "approved": approved,
        "tickets": [t.code for t in tickets],
    }


@db_task
def my_sales(participant: Participant, limit: int = 15) -> list[dict]:
    qs = Sale.objects.filter(participant=participant).order_by("-created_at")[:limit]
    return [
        {
            "id": s.id,
            "date": s.sale_date.strftime("%d.%m.%Y"),
            "product": s.product_display,
            "fabric": s.fabric_name,
            "status": s.get_status_display(),
            "reason": s.reject_reason,
        }
        for s in qs
    ]


@db_task
def rating_view(participant: Participant, limit: int = 20) -> dict:
    """ТОП-N учасників за квитками + позиція самого учасника.

    Імена в топі знеособлені: лише ім'я + останні цифри телефону.
    """
    campaign = Campaign.current()
    ranked = list(
        Ticket.objects.filter(campaign=campaign)
        .values("participant_id", "participant__full_name", "participant__phone")
        .annotate(tickets=Count("id"))
        .order_by("-tickets", "participant_id")
    )
    top = [
        {
            "name": _public_name(row["participant__full_name"], row["participant__phone"]),
            "tickets": row["tickets"],
        }
        for row in ranked[:limit]
    ]
    my_position = my_tickets = None
    for i, row in enumerate(ranked, 1):
        if row["participant_id"] == participant.id:
            my_position, my_tickets = i, row["tickets"]
            break
    return {"top": top, "my_position": my_position, "my_tickets": my_tickets}



"""Бізнес-логіка: модерація продажів, нарахування квитків, розіграш.

Використовується і веб-адмінкою (синхронно), і ботом (через sync_to_async),
тому вся логіка зосереджена тут.
"""
import random

from django.db import transaction
from django.utils import timezone

from . import telegram_sync
from .models import AuditLog, Draw, Participant, Sale, Ticket


def log(actor: str, action: str, **details):
    AuditLog.objects.create(actor=actor, action=action, details=details)


@transaction.atomic
def approve_sale(sale_id: int, actor: str) -> tuple[Sale | None, Ticket | None]:
    """Підтверджує продаж і нараховує квиток.

    Повертає (None, None), якщо продаж уже змодерований кимось іншим —
    захист від подвійного натискання двома адмінами.
    """
    updated = Sale.objects.filter(id=sale_id, status=Sale.Status.PENDING).update(
        status=Sale.Status.APPROVED,
        moderated_by=actor,
        moderated_at=timezone.now(),
    )
    if not updated:
        return None, None

    sale = Sale.objects.select_related("participant", "campaign").get(id=sale_id)
    sale.bonus_amount = Sale.BONUS_RATES.get(sale.product_type, 0)
    sale.save(update_fields=["bonus_amount"])
    ticket = Ticket.objects.create(
        sale=sale, participant=sale.participant, campaign=sale.campaign
    )
    log(actor, "sale_approved", sale_id=sale.id, ticket=ticket.code,
        bonus=float(sale.bonus_amount))

    # сповіщення — після коміту, щоб HTTP до Telegram не тримав транзакцію
    chat_id = sale.participant.telegram_id
    text = (
        f"✅ Ваш продаж №{sale.id} підтверджено!\n"
        f"🎫 Нараховано квиток <b>{ticket.code}</b>. Успіхів у розіграші!"
    )
    transaction.on_commit(lambda: telegram_sync.send_message(chat_id, text))
    return sale, ticket


@transaction.atomic
def reject_sale(sale_id: int, actor: str, reason: str) -> Sale | None:
    updated = Sale.objects.filter(id=sale_id, status=Sale.Status.PENDING).update(
        status=Sale.Status.REJECTED,
        reject_reason=reason,
        moderated_by=actor,
        moderated_at=timezone.now(),
    )
    if not updated:
        return None

    sale = Sale.objects.select_related("participant").get(id=sale_id)
    log(actor, "sale_rejected", sale_id=sale.id, reason=reason)

    chat_id = sale.participant.telegram_id
    text = (
        f"❌ Ваш продаж №{sale.id} відхилено.\n"
        f"Причина: {reason}\n\n"
        f"Ви можете виправити дані та подати продаж повторно."
    )
    transaction.on_commit(lambda: telegram_sync.send_message(chat_id, text))
    return sale


class DrawError(Exception):
    pass


@transaction.atomic
def perform_draw(draw: Draw, actor: str) -> Draw:
    """Випадково обирає виграшний квиток.

    Правило «одна людина — один приз»: квитки учасників, які вже вигравали
    в цій кампанії, виключаються з пулу.
    """
    past_winner_ids = (
        Draw.objects.filter(campaign=draw.campaign, winner__isnull=False)
        .exclude(id=draw.id)
        .values_list("winner_id", flat=True)
    )
    tickets = list(
        Ticket.objects.filter(campaign=draw.campaign)
        .exclude(participant_id__in=past_winner_ids)
        .select_related("participant")
    )
    if not tickets:
        raise DrawError("Немає квитків для розіграшу в цій кампанії.")

    winning = random.SystemRandom().choice(tickets)
    draw.winning_ticket = winning
    draw.winner = winning.participant
    draw.tickets_total = len(tickets)
    draw.performed_by = actor
    draw.save()

    log(
        actor, "draw_performed",
        draw_id=draw.id, prize=draw.prize,
        ticket=winning.code, winner=winning.participant.full_name,
        tickets_total=len(tickets),
    )
    return draw


def notify_winner(draw: Draw):
    telegram_sync.send_message(
        draw.winner.telegram_id,
        f"🎉 Вітаємо! Ваш квиток <b>{draw.winning_ticket.code}</b> виграв "
        f"у розіграші «{draw.prize}»!\nЗ вами зв'яжеться представник Veloro.",
    )


def broadcast_draw_results(draw: Draw, actor: str) -> int:
    """Розсилає результат розіграшу всім учасникам кампанії (хто не заблокований)."""
    chat_ids = list(
        Participant.objects.filter(is_blocked=False).values_list("telegram_id", flat=True)
    )
    text = (
        f"🏁 Розіграш «{draw.prize}» завершено!\n\n"
        f"Виграшний квиток: <b>{draw.winning_ticket.code}</b>\n"
        f"Переможець: {draw.winner.full_name}, {draw.winner.salon} ({draw.winner.city})\n\n"
        f"Дякуємо всім за участь!"
    )
    sent = telegram_sync.broadcast(chat_ids, text)
    log(actor, "draw_broadcast", draw_id=draw.id, recipients=len(chat_ids), sent=sent)
    return sent

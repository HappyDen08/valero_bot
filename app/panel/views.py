from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core import services
from core.exports import PARTICIPANT_COLUMNS, SALE_COLUMNS, TICKET_COLUMNS, export_xlsx
from core.models import AuditLog, Campaign, Draw, Participant, Sale, Ticket

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="panel:login")


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def filter_sales(request):
    qs = Sale.objects.select_related("participant", "campaign").order_by("-created_at")
    f = request.GET
    if f.get("status"):
        qs = qs.filter(status=f["status"])
    if f.get("factory"):
        qs = qs.filter(participant__factory__icontains=f["factory"])
    if f.get("salon"):
        qs = qs.filter(participant__salon__icontains=f["salon"])
    if f.get("city"):
        qs = qs.filter(participant__city__icontains=f["city"])
    if f.get("q"):
        qs = qs.filter(
            Q(participant__full_name__icontains=f["q"]) | Q(fabric_name__icontains=f["q"])
        )
    if date_from := parse_date(f.get("date_from")):
        qs = qs.filter(sale_date__gte=date_from)
    if date_to := parse_date(f.get("date_to")):
        qs = qs.filter(sale_date__lte=date_to)
    return qs


def filter_participants(request):
    qs = (
        Participant.objects.annotate(
            tickets_count=Count("tickets", distinct=True),
            sales_approved=Count("sales", filter=Q(sales__status=Sale.Status.APPROVED), distinct=True),
            bonus_total=Sum("sales__bonus_amount", filter=Q(sales__status=Sale.Status.APPROVED)),
        )
        .order_by("-created_at")
    )
    f = request.GET
    if f.get("factory"):
        qs = qs.filter(factory__icontains=f["factory"])
    if f.get("salon"):
        qs = qs.filter(salon__icontains=f["salon"])
    if f.get("city"):
        qs = qs.filter(city__icontains=f["city"])
    if f.get("q"):
        qs = qs.filter(Q(full_name__icontains=f["q"]) | Q(phone__icontains=f["q"]))
    return qs


def paginate(request, qs, per_page=25):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


@staff_required
def dashboard(request):
    campaign = Campaign.current()
    stats = {
        "participants": Participant.objects.count(),
        "pending": Sale.objects.filter(status=Sale.Status.PENDING).count(),
        "approved": Sale.objects.filter(status=Sale.Status.APPROVED).count(),
        "tickets": Ticket.objects.count(),
        "amount_total": Sale.objects.filter(status=Sale.Status.APPROVED).aggregate(
            s=Sum("amount")
        )["s"],
        "bonus_total": Sale.objects.filter(status=Sale.Status.APPROVED).aggregate(
            s=Sum("bonus_amount")
        )["s"],
    }
    recent_sales = Sale.objects.select_related("participant").order_by("-created_at")[:8]
    recent_log = AuditLog.objects.all()[:8]
    return render(request, "panel/dashboard.html", {
        "active": "dashboard", "campaign": campaign, "stats": stats,
        "recent_sales": recent_sales, "recent_log": recent_log,
    })


@staff_required
def participants(request):
    qs = filter_participants(request)
    return render(request, "panel/participants.html", {
        "active": "participants", "page": paginate(request, qs), "total": qs.count(),
    })


@staff_required
def participants_export(request):
    return export_xlsx(filter_participants(request), PARTICIPANT_COLUMNS, "veloro_participants")


@staff_required
def sales(request):
    qs = filter_sales(request)
    return render(request, "panel/sales.html", {
        "active": "sales", "page": paginate(request, qs), "total": qs.count(),
        "statuses": Sale.Status.choices,
    })


@staff_required
def sales_export(request):
    return export_xlsx(filter_sales(request), SALE_COLUMNS, "veloro_sales")


@staff_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("participant", "campaign"), pk=pk)
    if request.method == "POST":
        actor = f"panel:{request.user.username}"
        action = request.POST.get("action")
        if action == "approve":
            approved, ticket = services.approve_sale(sale.id, actor)
            if approved:
                messages.success(request, f"Продаж №{sale.id} підтверджено, нараховано квиток {ticket.code}.")
            else:
                messages.error(request, "Цей продаж уже змодеровано.")
        elif action == "reject":
            reason = request.POST.get("reason", "").strip()
            if not reason:
                messages.error(request, "Вкажіть причину відхилення.")
                return redirect("panel:sale_detail", pk=pk)
            if services.reject_sale(sale.id, actor, reason):
                messages.success(request, f"Продаж №{sale.id} відхилено, учасника сповіщено.")
            else:
                messages.error(request, "Цей продаж уже змодеровано.")
        return redirect("panel:sale_detail", pk=pk)

    return render(request, "panel/sale_detail.html", {
        "active": "sales", "sale": sale,
    })


@staff_required
def tickets(request):
    qs = Ticket.objects.select_related("participant", "sale").order_by("-id")
    if q := request.GET.get("q"):
        qs = qs.filter(
            Q(participant__full_name__icontains=q) | Q(participant__salon__icontains=q)
        )
    return render(request, "panel/tickets.html", {
        "active": "tickets", "page": paginate(request, qs, 50), "total": qs.count(),
    })


@staff_required
def tickets_export(request):
    return export_xlsx(
        Ticket.objects.select_related("participant", "sale").order_by("id"),
        TICKET_COLUMNS, "veloro_tickets",
    )


@staff_required
def rating(request):
    campaign = Campaign.current()
    rows = (
        Participant.objects.filter(tickets__campaign=campaign)
        .annotate(
            tickets_count=Count("tickets", distinct=True),
            sales_count=Count(
                "sales", filter=Q(sales__status=Sale.Status.APPROVED, sales__campaign=campaign),
                distinct=True,
            ),
        )
        .order_by("-tickets_count", "full_name")[:20]
    )
    return render(request, "panel/rating.html", {
        "active": "rating", "rows": rows, "campaign": campaign,
    })


def draw_pool(campaign):
    """Квитки кампанії без учасників, які вже вигравали («одна людина — один приз»)."""
    past_winner_ids = Draw.objects.filter(
        campaign=campaign, winner__isnull=False
    ).values_list("winner_id", flat=True)
    return Ticket.objects.filter(campaign=campaign).exclude(
        participant_id__in=past_winner_ids
    )


@staff_required
def draw_ceremony(request):
    import json
    import random as rnd

    campaign = get_object_or_404(Campaign, pk=request.GET.get("campaign"))
    prize = request.GET.get("prize", "").strip()
    if not prize:
        messages.error(request, "Вкажіть назву призу.")
        return redirect("panel:draws")
    pool = list(draw_pool(campaign).values_list("id", flat=True))
    codes = [f"#{pk:06d}" for pk in pool]
    rnd.shuffle(codes)
    return render(request, "panel/draw_ceremony.html", {
        "campaign": campaign, "prize": prize,
        "tickets_total": len(codes),
        "codes_json": json.dumps(codes[:400]),
    })


@staff_required
def draw_perform(request):
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    campaign = get_object_or_404(Campaign, pk=request.POST.get("campaign"))
    prize = request.POST.get("prize", "").strip()
    if not prize:
        return JsonResponse({"error": "Вкажіть назву призу."}, status=400)
    draw = Draw(campaign=campaign, prize=prize)
    try:
        services.perform_draw(draw, f"panel:{request.user.username}")
    except services.DrawError as e:
        return JsonResponse({"error": str(e)}, status=400)
    services.notify_winner(draw)
    return JsonResponse({
        "draw_id": draw.pk,
        "ticket": draw.winning_ticket.code,
        "winner": draw.winner.full_name,
        "salon": draw.winner.salon,
        "city": draw.winner.city,
        "tickets_total": draw.tickets_total,
        "performed_at": timezone.localtime(draw.performed_at).strftime("%d.%m.%Y %H:%M:%S"),
    })


@staff_required
def draws(request):
    campaigns = Campaign.objects.order_by("-start_date")
    if request.method == "POST":
        actor = f"panel:{request.user.username}"
        if request.POST.get("action") == "draw":
            campaign = get_object_or_404(Campaign, pk=request.POST.get("campaign"))
            prize = request.POST.get("prize", "").strip()
            if not prize:
                messages.error(request, "Вкажіть назву призу.")
                return redirect("panel:draws")
            draw = Draw(campaign=campaign, prize=prize)
            try:
                services.perform_draw(draw, actor)
            except services.DrawError as e:
                messages.error(request, str(e))
                return redirect("panel:draws")
            services.notify_winner(draw)
            messages.success(
                request,
                f"Розіграш проведено! Виграшний квиток {draw.winning_ticket.code} — "
                f"{draw.winner.full_name}. Переможця сповіщено.",
            )
        elif request.POST.get("action") == "broadcast":
            draw = get_object_or_404(Draw, pk=request.POST.get("draw_id"), winner__isnull=False)
            sent = services.broadcast_draw_results(draw, actor)
            messages.success(request, f"Результати «{draw.prize}» розіслано {sent} учасникам.")
        return redirect("panel:draws")

    all_draws = Draw.objects.select_related("campaign", "winner", "winning_ticket").order_by("-performed_at")
    tickets_in_pool = Ticket.objects.filter(campaign=Campaign.current()).count()
    return render(request, "panel/draws.html", {
        "active": "draws", "draws": all_draws, "campaigns": campaigns,
        "tickets_in_pool": tickets_in_pool,
    })
